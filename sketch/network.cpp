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

// ------------------------------------------------------------------ NVS для web-ETag

/// ETag хранится отдельно от основного конфига (namespace "webconf", ключ "etag"),
/// чтобы не затрагивать LoadConfig()/SaveConfig().
static String LoadWebETag()
{
    Preferences p;
    p.begin( "webconf", true );
    String etag = p.getString( "etag", "" );
    p.end();
    return etag;
}

static void SaveWebETag( const String& etag )
{
    Preferences p;
    p.begin( "webconf", false );
    p.putString( "etag", etag );
    p.end();
}

// ------------------------------------------------------------------ построение URL

/**
 * @brief Извлекает host:port из значения server_url.
 * @details Поддерживает как новый формат («host:port»), так и легаси-полный URL
 *          («http://host:port/path»): срезает схему и путь.
 *          Это обеспечивает работу уже прошитых устройств до их перенастройки.
 * @param src  Значение поля config.server_url из NVS.
 * @param out  Выходной буфер для «host:port».
 * @param size Размер выходного буфера (байт).
 */
static void ExtractHostPort( const char* src, char* out, size_t size )
{
    const char* start = src;
    if     ( strncmp( src, "https://", 8 ) == 0 ) start = src + 8;
    else if( strncmp( src, "http://",  7 ) == 0 ) start = src + 7;

    strncpy( out, start, size - 1 );
    out[size - 1] = '\0';

    char* slash = strchr( out, '/' );
    if( slash ) *slash = '\0';
}

/**
 * @brief Строит полный HTTP-URL: «http://{host:port}{path}».
 * @param out        Выходной буфер (минимум HTTP_URL_SIZE байт).
 * @param size       Размер буфера.
 * @param server_url Значение config.server_url (host:port или легаси-URL).
 * @param path       Путь API — API_DATA_PATH или API_CONFIG_PATH.
 */
static void BuildUrl( char* out, size_t size, const char* server_url, const char* path )
{
    char hostport[128];
    ExtractHostPort( server_url, hostport, sizeof( hostport ) );
    snprintf( out, size, "http://%s%s", hostport, path );
}

// ------------------------------------------------------------------ web-конфиг

/**
 * @brief Сравнивает ETag сервера с локальным и при расхождении получает новый конфиг.
 * @details Выполняет ровно один GET /api/config при изменении ETag;
 *          при совпадении - никаких HTTP-запросов (Serial-правки не затираются).
 *          Применяет только ключи из allow-list (связочные жёстко игнорируются).
 * @param serverETag ETag из заголовка X-Config-ETag ответа POST /api/data.
 */
static void MaybeFetchWebConfig( const String& serverETag )
{
    if( serverETag.length() == 0 ) return;

    String storedETag = LoadWebETag();
    if( serverETag == storedETag ) return;

    char configUrl[HTTP_URL_SIZE];
    BuildUrl( configUrl, HTTP_URL_SIZE, config.server_url, API_CONFIG_PATH );
    if( configUrl[0] == '\0' || strncmp( configUrl, "http", 4 ) != 0 ) return;

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
        Serial.printf( "Web config updated (etag %s → %s)\n",
                       storedETag.c_str(), serverETag.c_str() );
    }

    SaveWebETag( serverETag );
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

     char dataUrl[HTTP_URL_SIZE];
     BuildUrl( dataUrl, HTTP_URL_SIZE, config.server_url, API_DATA_PATH );

     // Запрашиваем ETag несвязочного конфига из ответа сервера
     static const char* etagHeader[] = { "X-Config-ETag" };

     char payload[HTTP_PAYLOAD_SIZE];
     snprintf( payload, sizeof( payload ),
               "{\"temp0\":%.2f,\"temp1\":%.2f,\"timestamp\":%lu}",
               reading.temp0, reading.temp1, CurrentTimestamp() );

     HTTPClient http;
     http.setTimeout( config.http_timeout_ms );
     http.begin( dataUrl );
     http.addHeader( "Content-Type", "application/json" );
     http.collectHeaders( etagHeader, 1 );

     int httpCode = http.POST( payload );
     if( httpCode == 200 )
     {
          // Событийная проверка конфига: GET /api/config только при смене ETag
          MaybeFetchWebConfig( http.header( "X-Config-ETag" ) );

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
          http.end();
          delay( config.http_retry_delay_ms );

          http.begin( dataUrl );
          http.addHeader( "Content-Type", "application/json" );
          http.collectHeaders( etagHeader, 1 );

          httpCode = http.POST( payload );
          if( httpCode == 200 )
          {
               MaybeFetchWebConfig( http.header( "X-Config-ETag" ) );

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
