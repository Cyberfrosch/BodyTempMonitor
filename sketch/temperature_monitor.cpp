/**
 * @file      temperature_monitor.cpp
 * @brief     Реализация модуля мониторинга температуры (два датчика DS18B20).
 * @details   Чтение датчиков, запись CSV в LittleFS, отправка на HTTP-сервер,
 *            обработка Serial-команд.
 */

#include "temperature_monitor.hpp"

#include <cstdio> // snprintf

OneWire           oneWire( TEMP_SENSOR_PIN );
DallasTemperature sensors( &oneWire );
Preferences       prefs;

RTC_DS3231 rtc;
bool rtcOK = false;

Config config;

// Адреса датчиков, загруженные из NVS
static DeviceAddress sensorAddr[2];
static bool          bindingOK = false;

void LoadConfig()
{
     prefs.begin( "config", true );

     size_t len = prefs.getString( "wifi_ssid", config.wifi_ssid, sizeof( config.wifi_ssid ) );
     if( len == 0 )
     {
          prefs.end();
          ResetConfig();
          return;
     }

     prefs.getString( "wifi_pass", config.wifi_pass, sizeof( config.wifi_pass ) );
     prefs.getString( "server_url", config.server_url, sizeof( config.server_url ) );
     prefs.getString( "ntp_server", config.ntp_server, sizeof( config.ntp_server ) );

     config.gmt_offset_sec      = prefs.getLong( "gmt_offset", config.gmt_offset_sec );
     config.daylight_offset_sec = prefs.getInt( "daylight", config.daylight_offset_sec );
     config.save_interval_ms    = prefs.getULong( "save_int", config.save_interval_ms );
     config.http_timeout_ms     = prefs.getULong( "http_tout", config.http_timeout_ms );
     config.http_retry_delay_ms = prefs.getULong( "http_delay", config.http_retry_delay_ms );
     config.wifi_connect_attempts = prefs.getInt( "wifi_att", config.wifi_connect_attempts );

     config.valid = true;
     prefs.end();
}

void SaveConfig()
{
     prefs.begin( "config", false );

     prefs.putString( "wifi_ssid", config.wifi_ssid );
     prefs.putString( "wifi_pass", config.wifi_pass );
     prefs.putString( "server_url", config.server_url );
     prefs.putString( "ntp_server", config.ntp_server );

     prefs.putLong( "gmt_offset", config.gmt_offset_sec );
     prefs.putInt( "daylight", config.daylight_offset_sec );
     prefs.putULong( "save_int", config.save_interval_ms );
     prefs.putULong( "http_tout", config.http_timeout_ms );
     prefs.putULong( "http_delay", config.http_retry_delay_ms );
     prefs.putInt( "wifi_att", config.wifi_connect_attempts );

     prefs.end();
     config.valid = true;
}

void ResetConfig()
{
     strcpy( config.wifi_ssid, "" );
     strcpy( config.wifi_pass, "" );
     strcpy( config.server_url, "" );
     strcpy( config.ntp_server, "pool.ntp.org" );
     config.gmt_offset_sec      = 7 * 3600;
     config.daylight_offset_sec = 0;
     config.save_interval_ms    = 10 * 1000;
     config.http_timeout_ms     = 5000;
     config.http_retry_delay_ms = 1000;
     config.wifi_connect_attempts = 20;
     config.valid = false;
}

bool InitRTC()
{
     if( !rtc.begin() )
     {
          Serial.println( "[FATAL] RTC not found" );
          rtcOK = false;
          return false;
     }

     if( rtc.lostPower() )
     {
          Serial.println( "RTC lost power, setting time to compile time" );
          rtc.adjust( DateTime( F(__DATE__), F(__TIME__) ) );
     }

     rtcOK = true;
     DateTime now = rtc.now();
     Serial.printf( "RTC initialized: %04d-%02d-%02d %02d:%02d:%02d\n",
                    now.year(), now.month(), now.day(),
                    now.hour(), now.minute(), now.second() );
     return true;
}

static void AddrToStr( const DeviceAddress addr, char* buf, size_t len )
{
     snprintf( buf, len, "%02X%02X%02X%02X%02X%02X%02X%02X",
               addr[0], addr[1], addr[2], addr[3],
               addr[4], addr[5], addr[6], addr[7] );
}

bool InitSensors()
{
     prefs.begin( "sensors", false );

     // Пробуем загрузить сохранённые адреса
     size_t s0 = prefs.getBytes( "addr0", sensorAddr[0], DEVICE_ADDR_SIZE );
     size_t s1 = prefs.getBytes( "addr1", sensorAddr[1], DEVICE_ADDR_SIZE );

     if( s0 == DEVICE_ADDR_SIZE && s1 == DEVICE_ADDR_SIZE )
     {
          // Проверяем, что датчики действительно на шине
          sensors.begin();
          if( !sensors.isConnected( sensorAddr[0] ) || !sensors.isConnected( sensorAddr[1] ) )
          {
               Serial.println( "Saved sensors not found on bus, rescanning..." );
               prefs.clear();
               prefs.end();
               return false;
          }

          bindingOK = true;
          char buf[17];
          AddrToStr( sensorAddr[0], buf, sizeof( buf ) );
          Serial.printf( "Sensor 0: %s (from NVS)\n", buf );
          AddrToStr( sensorAddr[1], buf, sizeof( buf ) );
          Serial.printf( "Sensor 1: %s (from NVS)\n", buf );
          prefs.end();
          return true;
     }

     // Адресов нет — сканируем шину
     Serial.println( "Scanning 1-Wire bus for sensor binding..." );
     sensors.begin();
     int found = sensors.getDeviceCount();
     Serial.printf( "Found %d sensor(s)\n", found );

     if( found < MIN_SENSORS_REQUIRED )
     {
          Serial.printf( "[FATAL] Need at least %d sensors, found %d\n",
                         MIN_SENSORS_REQUIRED, found );
          prefs.end();
          return false;
     }

     sensors.getAddress( sensorAddr[0], 0 );
     sensors.getAddress( sensorAddr[1], 1 );

     prefs.putBytes( "addr0", sensorAddr[0], DEVICE_ADDR_SIZE );
     prefs.putBytes( "addr1", sensorAddr[1], DEVICE_ADDR_SIZE );
     prefs.end();

     bindingOK = true;
     char buf[17];
     AddrToStr( sensorAddr[0], buf, sizeof( buf ) );
     Serial.printf( "Sensor 0: %s (saved to NVS)\n", buf );
     AddrToStr( sensorAddr[1], buf, sizeof( buf ) );
     Serial.printf( "Sensor 1: %s (saved to NVS)\n", buf );
     return true;
}

SensorReading ReadSensors()
{
     SensorReading reading;
     sensors.requestTemperatures();

     if( bindingOK )
     {
          reading.temp0 = sensors.getTempC( sensorAddr[0] );
          reading.temp1 = sensors.getTempC( sensorAddr[1] );
     }
     else
     {
          // Fallback: по индексу если привязка не удалась
          int count = sensors.getDeviceCount();
          if( count > 0 ) reading.temp0 = sensors.getTempCByIndex( 0 );
          if( count > 1 ) reading.temp1 = sensors.getTempCByIndex( 1 );
     }
     return reading;
}

bool IsRTCconnected()
{
     Wire.beginTransmission( RTC_I2C_ADDR );
     return ( Wire.endTransmission() == 0 );
}

void CheckDevices()
{
     if( !sensors.isConnected( sensorAddr[0] ) || !sensors.isConnected( sensorAddr[1] ) )
     {
          HaltWithError( "Sensors DS18B20 not connected" );
     }
     if( !IsRTCconnected() )
     {
          HaltWithError( "RTC DS3231 not connected" );
     }
}

bool InitStorage()
{
     if( !LittleFS.begin( true ) )
     {
          Serial.println( "[FATAL] LittleFS mount failed" );
          return false;
     }
     Serial.println( "LittleFS ready." );

     if( !LittleFS.exists( CSV_PATH ) )
     {
          File f = LittleFS.open( CSV_PATH, FILE_WRITE );
          if( f )
          {
               f.println( "reltime,temp0,temp1" );
               f.close();
          }
     }
     return true;
}

void LogReading( const SensorReading& reading )
{
     File f = LittleFS.open( CSV_PATH, FILE_APPEND );
     if( !f ) return;

     unsigned long timestamp = rtcOK ? rtc.now().unixtime() : millis() / 1000;

     char line[48];
     snprintf( line, sizeof( line ), "%lu,%.2f,%.2f",
               timestamp,
               reading.temp0,
               reading.temp1 );
     f.println( line );
     f.close();

     Serial.printf( "Logged: %lu, %.2f, %.2f\n", timestamp, reading.temp0, reading.temp1 );
}

void InitWiFi()
{
     if( !config.valid || strlen( config.wifi_ssid ) == 0 )
     {
          Serial.println( "WiFi not configured" );
          return;
     }

     WiFi.begin( config.wifi_ssid, config.wifi_pass );
     Serial.print( "Connecting to WiFi" );
     int attempts = 0;
     while( WiFi.status() != WL_CONNECTED && attempts < config.wifi_connect_attempts )
     {
          delay( 500 );
          Serial.print( '.' );
          ++attempts;
     }
     Serial.println();
     if( WiFi.status() == WL_CONNECTED )
     {
          Serial.print( "Wi-Fi connected. IP: " );
          Serial.println( WiFi.localIP() );

          Serial.print( "Syncing time with NTP..." );
          configTime( config.gmt_offset_sec, config.daylight_offset_sec, config.ntp_server );

          struct tm timeinfo;
          if( getLocalTime( &timeinfo, 10000 ) )
          {
               Serial.println( " OK" );
               Serial.printf( "NTP time: %04d-%02d-%02d %02d:%02d:%02d\n",
                              timeinfo.tm_year + 1900, timeinfo.tm_mon + 1, timeinfo.tm_mday,
                              timeinfo.tm_hour, timeinfo.tm_min, timeinfo.tm_sec );

               if( rtcOK )
               {
                    time_t now;
                    time( &now );
                    rtc.adjust( DateTime( now ) );
                    Serial.println( "RTC time updated from NTP" );
               }
          }
          else
          {
               Serial.println( " Failed" );
          }
     }
     else
     {
          Serial.println( "Wi-Fi not connected. Running offline" );
     }
}

void SendToServer( const SensorReading& reading )
{
     if( WiFi.status() != WL_CONNECTED ) return;
     if( strlen( config.server_url ) == 0 ) return;
     if( reading.temp0 == DEVICE_DISCONNECTED_C || reading.temp1 == DEVICE_DISCONNECTED_C ) return;

     HTTPClient http;
     http.setTimeout( config.http_timeout_ms );
     http.begin( config.server_url );
     http.addHeader( "Content-Type", "application/json" );

     char payload[96];
     snprintf( payload, sizeof( payload ),
               "{\"temp0\":%.2f,\"temp1\":%.2f,\"timestamp\":%lu}",
               reading.temp0, reading.temp1,
               rtcOK ? rtc.now().unixtime() : millis() / 1000 );

     int httpCode = http.POST( payload );
     if( httpCode == 200 )
     {
          digitalWrite( STATUS_LED, HIGH );
          Serial.println( "Sent to server OK" );
     }
     else if( httpCode > 0 )
     {
          digitalWrite( STATUS_LED, !digitalRead( STATUS_LED ) );
          Serial.printf( "Server HTTP error: %d\n", httpCode );
     }
     else
     {
          Serial.printf( "Connection error: %d, retrying...\n", httpCode );
          delay( config.http_retry_delay_ms );
          httpCode = http.POST( payload );
          if( httpCode == 200 )
          {
               digitalWrite( STATUS_LED, HIGH );
               Serial.println( "Sent to server OK (retry)" );
          }
          else
          {
               digitalWrite( STATUS_LED, LOW );
               Serial.printf( "Retry failed: %d\n", httpCode );
          }
     }
     http.end();
}

void HandleSerialCommands()
{
     if( !Serial.available() ) return;

     String cmd = Serial.readStringUntil( '\n' );
     cmd.trim();

     if( cmd == "download" )
     {
          File f = LittleFS.open( CSV_PATH, FILE_READ );
          if( !f )
          {
               Serial.println( "File not found" );
               return;
          }
          Serial.println( "--- BEGIN FILE ---" );
          while( f.available() ) Serial.write( f.read() );
          Serial.println( "\n--- END FILE ---" );
          f.close();
     }
     else if( cmd == "clear" )
     {
          LittleFS.remove( CSV_PATH );
          File f = LittleFS.open( CSV_PATH, FILE_WRITE );
          if( f )
          {
               f.println( "reltime,temp0,temp1" );
               f.close();
          }
          Serial.println( "File cleared" );
     }
     else if( cmd == "rebind" )
     {
          prefs.begin( "sensors", false );
          prefs.clear();
          prefs.end();
          Serial.println( "Sensor binding cleared. Reboot to rescan." );
     }
     else if( cmd == "config show" )
     {
          Serial.println( "--- CONFIG ---" );
          Serial.printf( "wifi_ssid=%s\n", config.wifi_ssid );
          Serial.printf( "wifi_pass=%s\n", strlen(config.wifi_pass) > 0 ? "***" : "" );
          Serial.printf( "server_url=%s\n", config.server_url );
          Serial.printf( "ntp_server=%s\n", config.ntp_server );
          Serial.printf( "gmt_offset=%ld\n", config.gmt_offset_sec );
          Serial.printf( "daylight=%d\n", config.daylight_offset_sec );
          Serial.printf( "save_interval=%lu\n", config.save_interval_ms );
          Serial.printf( "http_timeout=%lu\n", config.http_timeout_ms );
          Serial.printf( "http_delay=%lu\n", config.http_retry_delay_ms );
          Serial.printf( "wifi_attempts=%d\n", config.wifi_connect_attempts );
          Serial.println( "--- END CONFIG ---" );
     }
     else if( cmd.startsWith( "config set " ) )
     {
          String kv = cmd.substring( 11 );
          int eq = kv.indexOf( '=' );
          if( eq < 0 ) { Serial.println( "Usage: config set key=value" ); return; }

          String key = kv.substring( 0, eq );
          String val = kv.substring( eq + 1 );

          if( key == "wifi_ssid" ) strncpy( config.wifi_ssid, val.c_str(), sizeof(config.wifi_ssid)-1 );
          else if( key == "wifi_pass" ) strncpy( config.wifi_pass, val.c_str(), sizeof(config.wifi_pass)-1 );
          else if( key == "server_url" ) strncpy( config.server_url, val.c_str(), sizeof(config.server_url)-1 );
          else if( key == "ntp_server" ) strncpy( config.ntp_server, val.c_str(), sizeof(config.ntp_server)-1 );
          else if( key == "gmt_offset" ) config.gmt_offset_sec = val.toInt();
          else if( key == "daylight" ) config.daylight_offset_sec = val.toInt();
          else if( key == "save_interval" ) config.save_interval_ms = val.toInt();
          else if( key == "http_timeout" ) config.http_timeout_ms = val.toInt();
          else if( key == "http_delay" ) config.http_retry_delay_ms = val.toInt();
          else if( key == "wifi_attempts" ) config.wifi_connect_attempts = val.toInt();
          else { Serial.printf( "Unknown key: %s\n", key.c_str() ); return; }

          SaveConfig();
          Serial.printf( "Set: %s=%s\n", key.c_str(), key == "wifi_pass" ? "***" : val.c_str() );
     }
     else if( cmd == "config reset" )
     {
          prefs.begin( "config", false );
          prefs.clear();
          prefs.end();
          ResetConfig();
          Serial.println( "Config reset to defaults" );
     }
}

[[noreturn]] void HaltWithError( const char* component )
{
     Serial.printf( "\n========================================\n" );
     Serial.printf( "SYSTEM HALTED: %s\n", component );
     Serial.printf( "Fix the issue and reboot the device.\n" );
     Serial.printf( "========================================\n" );

     pinMode( STATUS_LED, OUTPUT );
     for( ;; )
     {
          digitalWrite( STATUS_LED, HIGH );
          delay( 200 );
          digitalWrite( STATUS_LED, LOW );
          delay( 200 );
     }
}
