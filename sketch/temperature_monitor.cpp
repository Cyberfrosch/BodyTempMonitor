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

// Адреса датчиков, загруженные из NVS
static DeviceAddress sensorAddr[2];
static bool          bindingOK = false;

void InitRTC()
{
     if( !rtc.begin() )
     {
          Serial.println( "RTC not found" );
          rtcOK = false;
          return;
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
}

static void AddrToStr( const DeviceAddress addr, char* buf, size_t len )
{
     snprintf( buf, len, "%02X%02X%02X%02X%02X%02X%02X%02X",
               addr[0], addr[1], addr[2], addr[3],
               addr[4], addr[5], addr[6], addr[7] );
}

void InitSensorBinding()
{
     prefs.begin( "sensors", false );

     // Пробуем загрузить сохранённые адреса
     size_t s0 = prefs.getBytes( "addr0", sensorAddr[0], DEVICE_ADDR_SIZE );
     size_t s1 = prefs.getBytes( "addr1", sensorAddr[1], DEVICE_ADDR_SIZE );

     if( s0 == DEVICE_ADDR_SIZE && s1 == DEVICE_ADDR_SIZE )
     {
          bindingOK = true;
          char buf[17];
          AddrToStr( sensorAddr[0], buf, sizeof( buf ) );
          Serial.printf( "Sensor 0: %s (from NVS)\n", buf );
          AddrToStr( sensorAddr[1], buf, sizeof( buf ) );
          Serial.printf( "Sensor 1: %s (from NVS)\n", buf );
          prefs.end();
          return;
     }

     // Адресов нет — сканируем шину
     Serial.println( "Scanning 1-Wire bus for sensor binding..." );
     sensors.begin();
     int found = sensors.getDeviceCount();
     Serial.printf( "Found %d sensor(s)\n", found );

     if( found < MIN_SENSORS_REQUIRED )
     {
          Serial.println( "Need at least 2 sensors for binding" );
          prefs.end();
          return;
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

void InitStorage()
{
     if( !LittleFS.begin( true ) )
     {
          Serial.println( "LittleFS Mount Failed" );
          return;
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

     // При каждом старте без RTC добавляем маркер сброса
     if( !rtcOK )
     {
          File f = LittleFS.open( CSV_PATH, FILE_APPEND );
          if( f )
          {
               f.println( "RESET,0,0" );
               f.close();
               Serial.println( "Reset marker written" );
          }
     }
}

void LogReading( const SensorReading& reading )
{
     File f = LittleFS.open( CSV_PATH, FILE_APPEND );
     if( !f ) return;

     char line[48];
     if( rtcOK )
     {
          snprintf( line, sizeof( line ), "%lu,%.2f,%.2f",
                    rtc.now().unixtime(),
                    reading.temp0,
                    reading.temp1 );
     }
     else
     {
          snprintf( line, sizeof( line ), "%lu,%.2f,%.2f",
                    millis() / 1000,
                    reading.temp0,
                    reading.temp1 );
     }
     f.println( line );
     f.close();

     Serial.print( "Logged: " );
     Serial.print( reading.temp0 );
     Serial.print( ", " );
     Serial.println( reading.temp1 );
}

void InitWiFi()
{
     WiFi.begin( WIFI_SSID, WIFI_PASS );
     Serial.print( "Connecting to WiFi" );
     int attempts = 0;
     while( WiFi.status() != WL_CONNECTED && attempts < WIFI_CONNECT_ATTEMPTS )
     {
          delay( WIFI_RETRY_DELAY_MS );
          Serial.print( '.' );
          ++attempts;
     }
     Serial.println();
     if( WiFi.status() == WL_CONNECTED )
     {
          Serial.print( "Wi-Fi connected. IP: " );
          Serial.println( WiFi.localIP() );

          // Синхронизация времени по NTP
          Serial.print( "Syncing time with NTP..." );
          configTime( GMT_OFFSET_SEC, DAYLIGHT_OFFSET_SEC, NTP_SERVER );

          struct tm timeinfo;
          if( getLocalTime( &timeinfo, 10000 ) )
          {
               Serial.println( " OK" );
               Serial.printf( "NTP time: %04d-%02d-%02d %02d:%02d:%02d\n",
                              timeinfo.tm_year + 1900, timeinfo.tm_mon + 1, timeinfo.tm_mday,
                              timeinfo.tm_hour, timeinfo.tm_min, timeinfo.tm_sec );

               // Если RTC доступен, обновляем его время
               if( rtcOK )
               {
                    rtc.adjust( DateTime( timeinfo.tm_year + 1900, timeinfo.tm_mon + 1, timeinfo.tm_mday,
                                          timeinfo.tm_hour, timeinfo.tm_min, timeinfo.tm_sec ) );
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
     if( reading.temp0 == DEVICE_DISCONNECTED_C || reading.temp1 == DEVICE_DISCONNECTED_C ) return;

     HTTPClient http;
     http.setTimeout( HTTP_TIMEOUT_MS );
     http.begin( SERVER_URL );
     http.addHeader( "Content-Type", "application/json" );

     char payload[64];
     snprintf( payload, sizeof( payload ),
               "{\"temp0\":%.2f,\"temp1\":%.2f}",
               reading.temp0, reading.temp1 );

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
          // Retry once on connection error
          Serial.printf( "Connection error: %d, retrying...\n", httpCode );
          delay( HTTP_RETRY_DELAY_MS );
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
}
