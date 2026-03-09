/**
 * @file      temperature_monitor.cpp
 * @brief     Реализация модуля мониторинга температуры (два датчика DS18B20).
 * @details   Определения глобальных объектов, реализация функций:
 *            - чтение датчиков,
 *            - определение режима (гипотермия, норма, лихорадка, критический, ошибка),
 *            - управление светодиодами,
 *            - обновление LCD-дисплея.
 */

#include "temperature_monitor.h"

#include <algorithm> // std::max
#include <array>     // std::array
#include <cstring>   // strcpy, strlen

LiquidCrystal_I2C lcd( LCD_ADDR, LCD_COLS, LCD_ROWS );
OneWire oneWire( TEMP_SENSOR_PIN );
DallasTemperature sensors( &oneWire );

bool IsValidTemp( float t )
{
     return ( t > -50.0f && t < 100.0f );
}

void ReadSensors( SystemState& state )
{
     sensors.requestTemperatures();
     state.temp1 = sensors.getTempCByIndex( 0 );
     state.temp2 = sensors.getTempCByIndex( 1 );
     state.valid1 = IsValidTemp( state.temp1 );
     state.valid2 = IsValidTemp( state.temp2 );
     state.maxTemp = -100.0f;
     if( state.valid1 )
          state.maxTemp = state.temp1;
     if( state.valid2 )
          state.maxTemp = std::max( state.maxTemp, state.temp2 );
}

OperatingMode DetermineMode( const SystemState& state )
{
     if( !state.valid1 && !state.valid2 )
     {
          return OperatingMode::SENSOR_ERROR;
     }
     else if( state.maxTemp < HYPOTHERMIA_THRESHOLD )
     {
          return OperatingMode::HYPOTHERMIA;
     }
     else if( state.maxTemp <= NORMAL_THRESHOLD )
     {
          return OperatingMode::NORMAL;
     }
     else if( state.maxTemp <= FEVER_THRESHOLD )
     {
          return OperatingMode::FEVER;
     }
     else
     {
          return OperatingMode::CRITICAL;
     }
}

const char* ModeToString( OperatingMode mode )
{
     switch( mode )
     {
          case OperatingMode::HYPOTHERMIA:
               return "HYPOTHERMIA";
          case OperatingMode::NORMAL:
               return "NORMAL";
          case OperatingMode::FEVER:
               return "FEVER";
          case OperatingMode::CRITICAL:
               return "CRITICAL!";
          case OperatingMode::SENSOR_ERROR:
               return "SENSOR ERR";
          default:
               return "UNKNOWN";
     }
}

void LcdPrintRow( uint8_t row, const char* text )
{
     lcd.setCursor( 0, row );
     lcd.print( text );
     // Fill the rest of the line with spaces
     for( int i = strlen( text ); i < LCD_COLS; ++i )
     {
          lcd.print( ' ' );
     }
}

void UpdateLcd( const SystemState& state, OperatingMode mode )
{
     // Use fixed-size buffers instead of std::string to avoid heap allocation
     std::array<char, LCD_COLS + 1> buffer; // +1 for null terminator

     // Row 0: T1
     if( state.valid1 )
     {
          snprintf( buffer.data(), buffer.size(), "T1=%.1f%cC", state.temp1, 0xDF );
     }
     else
     {
          snprintf( buffer.data(), buffer.size(), "T1=INV" );
     }
     LcdPrintRow( 0, buffer.data() );

     // Row 1: T2
     if( state.valid2 )
     {
          snprintf( buffer.data(), buffer.size(), "T2=%.1f%cC", state.temp2, 0xDF );
     }
     else
     {
          snprintf( buffer.data(), buffer.size(), "T2=INV" );
     }
     LcdPrintRow( 1, buffer.data() );

     // Row 2: status
     snprintf( buffer.data(), buffer.size(), "STATUS:%s", ModeToString( mode ) );
     LcdPrintRow( 2, buffer.data() );

     // Row 3: max temperature or error
     if( state.valid1 || state.valid2 )
     {
          snprintf( buffer.data(), buffer.size(), "Max: %.1f%cC", state.maxTemp, 0xDF );
     }
     else
     {
          snprintf( buffer.data(), buffer.size(), "Check sensors!" );
     }
     LcdPrintRow( 3, buffer.data() );
}

void UpdateOutputs( OperatingMode mode, AlarmState& alarmState, bool& blinkState, unsigned long& lastBlink )
{
     bool heaterOn = false;
     bool fanOn = false;
     bool alarm = ( mode == OperatingMode::CRITICAL || mode == OperatingMode::SENSOR_ERROR );

     if( !alarm )
     {
          // Normal operation
          switch( mode )
          {
               case OperatingMode::HYPOTHERMIA:
                    heaterOn = true;
                    break;
               case OperatingMode::FEVER:
                    fanOn = true;
                    break;
               default:
                    break;
          }
          digitalWrite( HEATER_LED, heaterOn ? HIGH : LOW );
          digitalWrite( FAN_LED, fanOn ? HIGH : LOW );
          // Reset blink state
          if( alarmState == AlarmState::ALARM )
          {
               blinkState = false;
               alarmState = AlarmState::NORMAL;
          }
     }
     else
     {
          // Alarm mode: blink both LEDs
          alarmState = AlarmState::ALARM;
          unsigned long now = millis();
          if( now - lastBlink >= BLINK_INTERVAL_MS )
          {
               lastBlink = now;
               blinkState = !blinkState;
               digitalWrite( HEATER_LED, blinkState );
               digitalWrite( FAN_LED, blinkState );
          }
     }
}
