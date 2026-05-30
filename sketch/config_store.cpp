/**
 * @file      config_store.cpp
 * @brief     Реализация хранения конфигурации в NVS.
 * @details   Каждая функция открывает и закрывает Preferences самостоятельно,
 *            поэтому объект не нужно хранить в глобальной области.
 */

#include "config_store.hpp"

#include <Preferences.h>

Config config;

void LoadConfig()
{
     Preferences p;
     p.begin( "config", true );

     size_t len = p.getString( "wifi_ssid", config.wifi_ssid, sizeof( config.wifi_ssid ) );
     if( len == 0 )
     {
          p.end();
          ResetConfig();
          return;
     }

     p.getString( "wifi_pass",   config.wifi_pass,   sizeof( config.wifi_pass ) );
     p.getString( "server_url",  config.server_url,  sizeof( config.server_url ) );
     p.getString( "ntp_server",  config.ntp_server,  sizeof( config.ntp_server ) );

     config.gmt_offset_sec        = p.getLong(  "gmt_offset", config.gmt_offset_sec );
     config.daylight_offset_sec   = p.getInt(   "daylight",   config.daylight_offset_sec );
     config.save_interval_ms      = p.getULong( "save_int",   config.save_interval_ms );
     config.http_timeout_ms       = p.getULong( "http_tout",  config.http_timeout_ms );
     config.http_retry_delay_ms   = p.getULong( "http_delay", config.http_retry_delay_ms );
     config.wifi_connect_attempts = p.getInt(   "wifi_att",   config.wifi_connect_attempts );

     config.valid = true;
     p.end();
}

void SaveConfig()
{
     Preferences p;
     p.begin( "config", false );

     p.putString( "wifi_ssid",  config.wifi_ssid );
     p.putString( "wifi_pass",  config.wifi_pass );
     p.putString( "server_url", config.server_url );
     p.putString( "ntp_server", config.ntp_server );

     p.putLong(  "gmt_offset", config.gmt_offset_sec );
     p.putInt(   "daylight",   config.daylight_offset_sec );
     p.putULong( "save_int",   config.save_interval_ms );
     p.putULong( "http_tout",  config.http_timeout_ms );
     p.putULong( "http_delay", config.http_retry_delay_ms );
     p.putInt(   "wifi_att",   config.wifi_connect_attempts );

     p.end();
     config.valid = true;
}

void ResetConfig()
{
     Preferences p;
     p.begin( "config", false );
     p.clear();
     p.end();
     config = Config{};
}
