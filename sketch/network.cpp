/**
 * @file      network.cpp
 * @brief     Реализация сетевых функций: Wi-Fi, NTP, HTTP.
 */

#include "network.hpp"
#include "clock_rtc.hpp"
#include "config_store.hpp"
#include "system.hpp"

#include <HTTPClient.h>
#include <Preferences.h>
#include <WiFi.h>
#include <cstdio>
#include <ctime>

// ------------------------------------------------------------------ allow-list

/// Ключи, разрешённые к обновлению через веб-канал.
/// Связочные параметры (wifi_ssid, wifi_pass, server_url) намеренно исключены.
static const char* const WEB_ALLOWED_KEYS[] = {
    "ntp_server", "gmt_offset", "daylight",
    "save_interval", "http_timeout", "http_delay", "wifi_attempts"
};
static constexpr size_t WEB_ALLOWED_COUNT =
    sizeof( WEB_ALLOWED_KEYS ) / sizeof( WEB_ALLOWED_KEYS[0] );

static bool IsWebAllowed( const String& key )
{
    for( size_t i = 0; i < WEB_ALLOWED_COUNT; ++i )
        if( key == WEB_ALLOWED_KEYS[i] ) return true;
    return false;
}

// ------------------------------------------------------------------ NVS для web-ревизии

/// NVS-ревизия хранится отдельно от основного конфига,
/// чтобы не затрагивать LoadConfig()/SaveConfig().
static unsigned long LoadWebRevision()
{
    Preferences p;
    p.begin( "webconf", true );
    unsigned long rev = p.getULong( "rev", 0 );
    p.end();
    return rev;
}

static void SaveWebRevision( unsigned long rev )
{
    Preferences p;
    p.begin( "webconf", false );
    p.putULong( "rev", rev );
    p.end();
}

// ------------------------------------------------------------------ URL конфига

/// Строит URL конфигурации из server_url, заменяя хвост "/api/data" → "/api/config".
/// Допущение задокументировано в network.hpp (CONFIG_URL_SIZE).
static void BuildConfigUrl( char* out, size_t size )
{
    strncpy( out, config.server_url, size - 1 );
    out[size - 1] = '\0';
    char* tail = strstr( out, "/api/data" );
    if( tail != nullptr )
        strncpy( tail, "/api/config", size - static_cast<size_t>( tail - out ) - 1 );
}

// ------------------------------------------------------------------ web-конфиг

/**
 * @brief Сравнивает ревизию сервера с локальной и при расхождении получает новый конфиг.
 * @details Выполняет ровно один GET /api/config при изменении ревизии;
 *          при совпадении - никаких HTTP-запросов.
 *          Применяет только ключи из allow-list (связочные игнорируются).
 * @param serverRev Ревизия, полученная из заголовка X-Config-Revision ответа POST /api/data.
 */
static void MaybeFetchWebConfig( unsigned long serverRev )
{
    unsigned long storedRev = LoadWebRevision();
    if( serverRev == storedRev ) return;

    char configUrl[CONFIG_URL_SIZE];
    BuildConfigUrl( configUrl, CONFIG_URL_SIZE );
    if( configUrl[0] == '\0' || strstr( configUrl, "http" ) != configUrl ) return;

    HTTPClient cfgHttp;
    cfgHttp.setTimeout( config.http_timeout_ms );
    cfgHttp.begin( configUrl );
    int code = cfgHttp.GET();

    if( code != 200 )
    {
        Serial.printf( "Web config fetch failed: %d\n", code );
        cfgHttp.end();
        return;
    }

    String body = cfgHttp.getString();
    cfgHttp.end();

    bool changed = false;
    int  pos     = 0;

    while( pos < (int)body.length() )
    {
        int nl   = body.indexOf( '\n', pos );
        String line = ( nl >= 0 ) ? body.substring( pos, nl ) : body.substring( pos );
        pos = ( nl >= 0 ) ? nl + 1 : (int)body.length();
        line.trim();

        int eq = line.indexOf( '=' );
        if( eq < 0 ) continue;

        String key = line.substring( 0, eq );
        String val = line.substring( eq + 1 );

        if( !IsWebAllowed( key ) ) continue;   // защита от связочных и служебных ключей
        if( ApplyConfigKey( key, val ) ) changed = true;
    }

    if( changed )
    {
        SaveConfig();
        Serial.printf( "Web config updated (rev %lu → %lu)\n", storedRev, serverRev );
    }

    SaveWebRevision( serverRev );
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

     // Запрашиваем заголовок ревизии конфига из ответа сервера
     static const char* revHeader[] = { "X-Config-Revision" };
     http.collectHeaders( revHeader, 1 );

     char payload[HTTP_PAYLOAD_SIZE];
     snprintf( payload, sizeof( payload ),
               "{\"temp0\":%.2f,\"temp1\":%.2f,\"timestamp\":%lu}",
               reading.temp0, reading.temp1, CurrentTimestamp() );

     int httpCode = http.POST( payload );
     if( httpCode == 200 )
     {
          // Событийная проверка конфига: GET /api/config только при смене ревизии
          String revStr = http.header( "X-Config-Revision" );
          if( revStr.length() > 0 )
               MaybeFetchWebConfig( (unsigned long)revStr.toInt() );

          digitalWrite( STATUS_LED, HIGH );
          Serial.println( "Sent to server OK" );
     }
     else if( httpCode > 0 )
     {
          Serial.printf( "Server HTTP error: %d\n", httpCode );
          IndicateServerError();
     }
     else
     {
          Serial.printf( "Connection error: %d, retrying...\n", httpCode );
          http.end();   // сбрасываем упавшее соединение перед повтором
          delay( config.http_retry_delay_ms );

          http.begin( config.server_url );
          http.addHeader( "Content-Type", "application/json" );
          http.collectHeaders( revHeader, 1 );

          httpCode = http.POST( payload );
          if( httpCode == 200 )
          {
               String revStr = http.header( "X-Config-Revision" );
               if( revStr.length() > 0 )
                    MaybeFetchWebConfig( (unsigned long)revStr.toInt() );

               digitalWrite( STATUS_LED, HIGH );
               Serial.println( "Sent to server OK (retry)" );
          }
          else
          {
               Serial.printf( "Retry failed: %d\n", httpCode );
               IndicateServerError();
          }
     }
     http.end();
}
