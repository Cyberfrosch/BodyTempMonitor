/**
 * @file      sketch.ino
 * @brief     Мониторинг температуры тела с двумя датчиками DS18B20.
 * @details   Периодическая запись в CSV (LittleFS), отправка на HTTP-сервер,
 *            Serial-команды "download" и "clear".
 *            Заглушка RTC DS3231 — раскомментировать при наличии модуля.
 */

#include "temperature_monitor.hpp"

void setup()
{
     Serial.begin( 115200 );
     pinMode( STATUS_LED, OUTPUT );
     digitalWrite( STATUS_LED, LOW );

     sensors.begin();

     InitSensorBinding();
     InitStorage();
     InitWiFi();
}

void loop()
{
     static unsigned long lastSave = 0;

     HandleSerialCommands();

     if( millis() - lastSave >= SAVE_INTERVAL_MS )
     {
          lastSave = millis();

          SensorReading reading = ReadSensors();
          LogReading( reading );
          SendToServer( reading );
     }
}
