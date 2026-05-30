/**
 * @file      system.cpp
 * @brief     Реализация аварийной остановки устройства.
 */

#include "system.hpp"

#include <Arduino.h>

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
