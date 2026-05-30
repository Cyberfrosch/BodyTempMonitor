/**
 * @file      system.cpp
 * @brief     Реализация LED-индикации и аварийного перезапуска.
 */

#include "system.hpp"

#include <Arduino.h>

void IndicateFault()
{
     unsigned long start = millis();
     while( millis() - start < FAULT_REBOOT_DELAY_MS )
     {
          digitalWrite( STATUS_LED, HIGH );
          delay( FAULT_BLINK_PERIOD_MS );
          digitalWrite( STATUS_LED, LOW );
          delay( FAULT_BLINK_PERIOD_MS );
     }
}

void IndicateServerError()
{
     for( int i = 0; i < 3; ++i )
     {
          digitalWrite( STATUS_LED, HIGH ); delay( SERVER_ERR_BLINK_PERIOD_MS );
          digitalWrite( STATUS_LED, LOW );  delay( SERVER_ERR_BLINK_PERIOD_MS );
          digitalWrite( STATUS_LED, HIGH ); delay( SERVER_ERR_BLINK_PERIOD_MS );
          digitalWrite( STATUS_LED, LOW );  delay( SERVER_ERR_BLINK_PERIOD_MS * 3 );
     }
}

[[noreturn]] void FaultReboot( const char* component )
{
     Serial.printf( "\n========================================\n" );
     Serial.printf( "FAULT: %s\n", component );
     Serial.printf( "Rebooting in %lu s...\n", FAULT_REBOOT_DELAY_MS / 1000 );
     Serial.printf( "========================================\n" );

     pinMode( STATUS_LED, OUTPUT );
     IndicateFault();
     ESP.restart();
     for( ;; ) {}
}
