/**
 * @file      network.cpp
 * @brief     Реализация сетевых функций: Wi-Fi, NTP, HTTP.
 */

#include "network.hpp"
#include "clock_rtc.hpp"
#include "config_store.hpp"
#include "system.hpp"

#include <HTTPClient.h>
#include <WiFi.h>
#include <cstdio>
#include <ctime>

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
          delay( WIFI_RETRY_DELAY_MS );
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
          if( getLocalTime( &timeinfo, NTP_TIMEOUT_MS ) )
          {
               Serial.println( " OK" );
               Serial.printf( "NTP time: %04d-%02d-%02d %02d:%02d:%02d\n",
                              timeinfo.tm_year + 1900, timeinfo.tm_mon + 1, timeinfo.tm_mday,
                              timeinfo.tm_hour, timeinfo.tm_min, timeinfo.tm_sec );

               time_t now;
               time( &now );
               if( AdjustRTC( now ) )
                    Serial.println( "RTC time updated from NTP" );
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

     char payload[HTTP_PAYLOAD_SIZE];
     snprintf( payload, sizeof( payload ),
               "{\"temp0\":%.2f,\"temp1\":%.2f,\"timestamp\":%lu}",
               reading.temp0, reading.temp1, CurrentTimestamp() );

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
