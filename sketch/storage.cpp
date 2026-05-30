/**
 * @file      storage.cpp
 * @brief     Реализация хранилища данных: LittleFS и CSV-журнал.
 */

#include "storage.hpp"
#include "clock_rtc.hpp"

#include <LittleFS.h>
#include <cstdio>

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

     unsigned long ts = CurrentTimestamp();
     char line[CSV_LINE_SIZE];
     snprintf( line, sizeof( line ), "%lu,%.2f,%.2f", ts, reading.temp0, reading.temp1 );
     f.println( line );
     f.close();

     Serial.printf( "Logged: %lu, %.2f, %.2f\n", ts, reading.temp0, reading.temp1 );
}

void DownloadCSV()
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

void ClearCSV()
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
