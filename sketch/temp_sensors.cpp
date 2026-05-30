/**
 * @file      temp_sensors.cpp
 * @brief     Реализация работы с датчиками DS18B20.
 */

#include "temp_sensors.hpp"

#include <OneWire.h>
#include <Preferences.h>
#include <cstdio>

static OneWire           oneWire( TEMP_SENSOR_PIN );
static DallasTemperature sensors( &oneWire );
static DeviceAddress     sensorAddr[2];
static bool              bindingOK = false;

static void AddrToStr( const DeviceAddress addr, char* buf, size_t len )
{
     snprintf( buf, len, "%02X%02X%02X%02X%02X%02X%02X%02X",
               addr[0], addr[1], addr[2], addr[3],
               addr[4], addr[5], addr[6], addr[7] );
}

bool InitSensors()
{
     Preferences p;
     p.begin( "sensors", false );

     size_t s0 = p.getBytes( "addr0", sensorAddr[0], DEVICE_ADDR_SIZE );
     size_t s1 = p.getBytes( "addr1", sensorAddr[1], DEVICE_ADDR_SIZE );

     if( s0 == DEVICE_ADDR_SIZE && s1 == DEVICE_ADDR_SIZE )
     {
          sensors.begin();
          if( !sensors.isConnected( sensorAddr[0] ) || !sensors.isConnected( sensorAddr[1] ) )
          {
               Serial.println( "Saved sensors not found on bus, rescanning..." );
               p.clear();
               p.end();
               return false;
          }

          bindingOK = true;
          char buf[SENSOR_ADDR_STR_LEN];
          AddrToStr( sensorAddr[0], buf, sizeof( buf ) );
          Serial.printf( "Sensor 0: %s (from NVS)\n", buf );
          AddrToStr( sensorAddr[1], buf, sizeof( buf ) );
          Serial.printf( "Sensor 1: %s (from NVS)\n", buf );
          p.end();
          return true;
     }

     Serial.println( "Scanning 1-Wire bus for sensor binding..." );
     sensors.begin();
     int found = sensors.getDeviceCount();
     Serial.printf( "Found %d sensor(s)\n", found );

     if( found < MIN_SENSORS_REQUIRED )
     {
          Serial.printf( "[FATAL] Need at least %d sensors, found %d\n",
                         MIN_SENSORS_REQUIRED, found );
          p.end();
          return false;
     }

     sensors.getAddress( sensorAddr[0], 0 );
     sensors.getAddress( sensorAddr[1], 1 );

     p.putBytes( "addr0", sensorAddr[0], DEVICE_ADDR_SIZE );
     p.putBytes( "addr1", sensorAddr[1], DEVICE_ADDR_SIZE );
     p.end();

     bindingOK = true;
     char buf[SENSOR_ADDR_STR_LEN];
     AddrToStr( sensorAddr[0], buf, sizeof( buf ) );
     Serial.printf( "Sensor 0: %s (saved to NVS)\n", buf );
     AddrToStr( sensorAddr[1], buf, sizeof( buf ) );
     Serial.printf( "Sensor 1: %s (saved to NVS)\n", buf );
     return true;
}

SensorReading ReadSensors()
{
     SensorReading reading;
     sensors.requestTemperatures();

     if( bindingOK )
     {
          reading.temp0 = sensors.getTempC( sensorAddr[0] );
          reading.temp1 = sensors.getTempC( sensorAddr[1] );
     }
     else
     {
          int count = sensors.getDeviceCount();
          if( count > 0 ) reading.temp0 = sensors.getTempCByIndex( 0 );
          if( count > 1 ) reading.temp1 = sensors.getTempCByIndex( 1 );
     }
     return reading;
}

bool AreSensorsConnected()
{
     return sensors.isConnected( sensorAddr[0] ) && sensors.isConnected( sensorAddr[1] );
}

void ClearSensorBinding()
{
     Preferences p;
     p.begin( "sensors", false );
     p.clear();
     p.end();
}
