/**
 * @file      sketch.ino
 * @brief     Мониторинг температуры тела с двумя датчиками DS18B20.
 * @details   Периодическая запись в CSV (LittleFS), отправка на HTTP-сервер,
 *            обработка Serial-команд и BLE-команд конфигурации.
 *
 * @note      Partition scheme: выберите «Huge APP (3MB No OTA)» или «Minimal SPIFFS»
 *            (Arduino IDE: Инструменты → Partition Scheme). Wi-Fi + BLE + LittleFS
 *            не вмещаются в дефолтную схему разделов («Default 4MB with spiffs»).
 */

#include "system.hpp"
#include "config_store.hpp"
#include "temp_sensors.hpp"
#include "clock_rtc.hpp"
#include "storage.hpp"
#include "network.hpp"
#include "serial_commands.hpp"
#include "ble_config.hpp"

static void CheckDevices()
{
     if( !AreSensorsConnected() ) FaultReboot( "Sensors DS18B20 not connected" );
     if( !IsRTCconnected() )      FaultReboot( "RTC DS3231 not connected" );
}

void setup()
{
     Serial.setRxBufferSize( SERIAL_RX_BUF_SIZE );
     Serial.begin( SERIAL_BAUD_RATE );
     pinMode( STATUS_LED, OUTPUT );
     digitalWrite( STATUS_LED, LOW );

     LoadConfig();

     if( !InitRTC() )      FaultReboot( "RTC DS3231 init failed" );
     if( !InitSensors() )  FaultReboot( "Sensors DS18B20 init failed" );
     if( !InitStorage() )  FaultReboot( "LittleFS init failed" );

     InitWiFi();
     InitBLE();
}

void loop()
{
     static unsigned long lastSave = 0;

     HandleSerialCommands();
     UpdateBLE();

     if( millis() - lastSave >= config.save_interval_ms )
     {
          lastSave = millis();

          CheckDevices();

          SensorReading reading = ReadSensors();
          LogReading( reading );
          SendToServer( reading );
     }
}
