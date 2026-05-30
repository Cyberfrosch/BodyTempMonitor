/**
 * @file      clock_rtc.cpp
 * @brief     Реализация модуля часов реального времени DS3231.
 */

#include "clock_rtc.hpp"

#include <Wire.h>

static RTC_DS3231 rtc;
static bool       rtcOK = false;

bool InitRTC()
{
     if( !rtc.begin() )
     {
          Serial.println( "[FATAL] RTC not found" );
          rtcOK = false;
          return false;
     }

     if( rtc.lostPower() )
     {
          Serial.println( "RTC lost power, setting time to compile time" );
          rtc.adjust( DateTime( F( __DATE__ ), F( __TIME__ ) ) );
     }

     rtcOK = true;
     DateTime now = rtc.now();
     Serial.printf( "RTC initialized: %04d-%02d-%02d %02d:%02d:%02d\n",
                    now.year(), now.month(), now.day(),
                    now.hour(), now.minute(), now.second() );
     return true;
}

bool IsRTCconnected()
{
     Wire.beginTransmission( RTC_I2C_ADDR );
     return ( Wire.endTransmission() == 0 );
}

unsigned long CurrentTimestamp()
{
     return rtcOK ? (unsigned long)rtc.now().unixtime() : millis() / 1000;
}

bool AdjustRTC( time_t t )
{
     if( !rtcOK ) return false;
     rtc.adjust( DateTime( (uint32_t)t ) );
     return true;
}
