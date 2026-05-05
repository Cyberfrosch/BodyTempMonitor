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

bool rtcOK = false;
// RTC_DS3231 rtc;

SensorReading ReadSensors()
{
     SensorReading reading;
     sensors.requestTemperatures();
     int count = sensors.getDeviceCount();
     if( count > 0 ) reading.temp0 = sensors.getTempCByIndex( 0 );
     if( count > 1 ) reading.temp1 = sensors.getTempCByIndex( 1 );
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
     // Когда будет RTC: snprintf( line, sizeof(line), "%lu,%.2f,%.2f", rtc.now().unixtime(), ... );
     snprintf( line, sizeof( line ), "%lu,%.2f,%.2f",
               millis() / 1000,
               reading.temp0,
               reading.temp1 );
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
     while( WiFi.status() != WL_CONNECTED && attempts < 20 )
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
     else
     {
          digitalWrite( STATUS_LED, !digitalRead( STATUS_LED ) );
          Serial.printf( "Server error: %d\n", httpCode );
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
}
