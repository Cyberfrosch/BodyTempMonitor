/**
 * @file      sketch.ino
 * @brief     Мониторинг температуры тела с двумя датчиками DS18B20.
 * @details   Управление на основе максимальной температуры с учётом медицинских диапазонов.
 *            Вывод на LCD 20x4 (I2C):
 *            - Row 0: T1
 *            - Row 1: T2
 *            - Row 2: status
 *            - Row 3: maximum temperature / error
 */

#include "temperature_monitor.h"

void setup()
{
     Serial.begin( 115200 );
     pinMode( FAN_LED, OUTPUT );
     pinMode( HEATER_LED, OUTPUT );
     digitalWrite( FAN_LED, LOW );
     digitalWrite( HEATER_LED, LOW );

     sensors.begin();

     // Scan 1-Wire bus for devices (debug only)
     std::array<uint8_t, 8> addr;
     int numDevices = 0;
     while( oneWire.search( addr.data() ) )
     {
          ++numDevices;
     }
     oneWire.reset_search();
     Serial.print( "Sensors found: " );
     Serial.println( numDevices );

     lcd.init();
     lcd.backlight();

     // Welcome message
     LcdPrintRow( 0, "Temp Monitor" );
     LcdPrintRow( 1, "Two sensors" );
     LcdPrintRow( 2, "Initializing..." );
     LcdPrintRow( 3, "" );
     delay( 2000 );
     lcd.clear();

     if( numDevices < 2 )
     {
          LcdPrintRow( 0, "ERROR: <2 sens" );
          LcdPrintRow( 1, "Check wiring!" );
          while( true ); // Halt
     }
}

void loop()
{
     static SystemState state;
     static unsigned long lastMeasureTime = 0;
     static AlarmState alarmState = AlarmState::NORMAL;
     static bool blinkState = false;
     static unsigned long lastBlink = 0;

     unsigned long now = millis();

     // Periodic measurement
     if( now - lastMeasureTime >= MEASURE_INTERVAL_MS )
     {
          lastMeasureTime = now;

          // 1. Read sensors
          ReadSensors( state );

          // 2. Serial output (debug)
          Serial.print( "T1: " );
          if( state.valid1 )
               Serial.print( state.temp1 );
          else
               Serial.print( "INV" );
          Serial.print( " C  T2: " );
          if( state.valid2 )
               Serial.print( state.temp2 );
          else
               Serial.print( "INV" );
          Serial.print( " C  Max: " );
          if( state.valid1 || state.valid2 )
               Serial.print( state.maxTemp );
          else
               Serial.print( "N/A" );
          Serial.println();

          // 3. Determine mode
          OperatingMode mode = DetermineMode( state );

          // 4. Control outputs
          UpdateOutputs( mode, alarmState, blinkState, lastBlink );

          // 5. Update LCD
          UpdateLcd( state, mode );
     }

     // If we are in alarm mode, blinking must continue even between measurements
     if( alarmState == AlarmState::ALARM )
     {
          UpdateOutputs( OperatingMode::CRITICAL, alarmState, blinkState, lastBlink ); // re‑trigger blinking
     }
}
