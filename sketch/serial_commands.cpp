/**
 * @file      serial_commands.cpp
 * @brief     Реализация обработчика команд устройства.
 */

#include "serial_commands.hpp"
#include "config_store.hpp"
#include "storage.hpp"
#include "temp_sensors.hpp"

void ProcessCommand( const String& cmd, Responder respond )
{
    if( cmd == "download" )
    {
        DownloadCSV(); // данные идут в Serial независимо от транспорта
        respond( "download: done" );
    }
    else if( cmd == "clear" )
    {
        ClearCSV();
        respond( "CSV cleared" );
    }
    else if( cmd == "rebind" )
    {
        ClearSensorBinding();
        respond( "Binding cleared. Reboot to rescan." );
    }
    else if( cmd == "config show" )
    {
        char buf[128];
        respond( "--- CONFIG ---" );
        snprintf( buf, sizeof( buf ), "wifi_ssid=%s", config.wifi_ssid );
        respond( String( buf ) );
        snprintf( buf, sizeof( buf ), "wifi_pass=%s", strlen( config.wifi_pass ) > 0 ? "***" : "" );
        respond( String( buf ) );
        snprintf( buf, sizeof( buf ), "server_url=%s", config.server_url );
        respond( String( buf ) );
        snprintf( buf, sizeof( buf ), "ntp_server=%s", config.ntp_server );
        respond( String( buf ) );
        snprintf( buf, sizeof( buf ), "gmt_offset=%ld", config.gmt_offset_sec );
        respond( String( buf ) );
        snprintf( buf, sizeof( buf ), "daylight=%d", config.daylight_offset_sec );
        respond( String( buf ) );
        snprintf( buf, sizeof( buf ), "save_interval=%lu", config.save_interval_ms );
        respond( String( buf ) );
        snprintf( buf, sizeof( buf ), "http_timeout=%lu", config.http_timeout_ms );
        respond( String( buf ) );
        snprintf( buf, sizeof( buf ), "http_delay=%lu", config.http_retry_delay_ms );
        respond( String( buf ) );
        snprintf( buf, sizeof( buf ), "wifi_attempts=%d", config.wifi_connect_attempts );
        respond( String( buf ) );
        respond( "--- END CONFIG ---" );
    }
    else if( cmd.startsWith( "config set " ) )
    {
        String kv = cmd.substring( 11 );
        int    eq = kv.indexOf( '=' );
        if( eq < 0 )
        {
            respond( "Usage: config set key=value" );
            return;
        }
        String key = kv.substring( 0, eq );
        String val = kv.substring( eq + 1 );

        if( !ApplyConfigKey( key, val ) )
        {
            respond( "Unknown key: " + key );
            return;
        }
        SaveConfig();
        respond( "Set: " + key + "=" + ( key == "wifi_pass" ? String( "***" ) : val ) );
    }
    else if( cmd == "config reset" )
    {
        ResetConfig();
        respond( "Config reset to defaults" );
    }
    else if( cmd.length() > 0 )
    {
        respond( "Unknown command: " + cmd );
    }
}

void HandleSerialCommands()
{
    if( !Serial.available() ) return;

    String cmd = Serial.readStringUntil( '\n' );
    cmd.trim();
    ProcessCommand( cmd, []( const String& s ) { Serial.println( s ); } );
}
