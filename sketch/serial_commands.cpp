/**
 * @file      serial_commands.cpp
 * @brief     Реализация диспетчера Serial-команд.
 */

#include "serial_commands.hpp"
#include "config_store.hpp"
#include "storage.hpp"
#include "temp_sensors.hpp"

void HandleSerialCommands()
{
     if( !Serial.available() ) return;

     String cmd = Serial.readStringUntil( '\n' );
     cmd.trim();

     if( cmd == "download" )
     {
          DownloadCSV();
     }
     else if( cmd == "clear" )
     {
          ClearCSV();
     }
     else if( cmd == "rebind" )
     {
          ClearSensorBinding();
          Serial.println( "Sensor binding cleared. Reboot to rescan." );
     }
     else if( cmd == "config show" )
     {
          Serial.println( "--- CONFIG ---" );
          Serial.printf( "wifi_ssid=%s\n", config.wifi_ssid );
          Serial.printf( "wifi_pass=%s\n", strlen( config.wifi_pass ) > 0 ? "***" : "" );
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
          int    eq = kv.indexOf( '=' );
          if( eq < 0 ) { Serial.println( "Usage: config set key=value" ); return; }

          String key = kv.substring( 0, eq );
          String val = kv.substring( eq + 1 );

          if     ( key == "wifi_ssid" )     strncpy( config.wifi_ssid,  val.c_str(), sizeof( config.wifi_ssid  ) - 1 );
          else if( key == "wifi_pass" )     strncpy( config.wifi_pass,  val.c_str(), sizeof( config.wifi_pass  ) - 1 );
          else if( key == "server_url" )    strncpy( config.server_url, val.c_str(), sizeof( config.server_url ) - 1 );
          else if( key == "ntp_server" )    strncpy( config.ntp_server, val.c_str(), sizeof( config.ntp_server ) - 1 );
          else if( key == "gmt_offset" )    config.gmt_offset_sec        = val.toInt();
          else if( key == "daylight" )      config.daylight_offset_sec   = val.toInt();
          else if( key == "save_interval" ) config.save_interval_ms      = val.toInt();
          else if( key == "http_timeout" )  config.http_timeout_ms       = val.toInt();
          else if( key == "http_delay" )    config.http_retry_delay_ms   = val.toInt();
          else if( key == "wifi_attempts" ) config.wifi_connect_attempts = val.toInt();
          else { Serial.printf( "Unknown key: %s\n", key.c_str() ); return; }

          SaveConfig();
          Serial.printf( "Set: %s=%s\n", key.c_str(), key == "wifi_pass" ? "***" : val.c_str() );
     }
     else if( cmd == "config reset" )
     {
          ResetConfig();
          Serial.println( "Config reset to defaults" );
     }
}
