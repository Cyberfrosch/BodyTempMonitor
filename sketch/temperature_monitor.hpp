/**
 * @file      temperature_monitor.hpp
 * @brief     Заголовочный файл модуля мониторинга температуры (два датчика DS18B20).
 * @details   Содержит объявления глобальных объектов, аппаратных констант,
 *            структур состояния и прототипов функций.
 */

#pragma once

#include <cstdint>

#include <DallasTemperature.h>
#include <HTTPClient.h>
#include <LittleFS.h>
#include <OneWire.h>
#include <Preferences.h>
#include <WiFi.h>

// Учетные данные (WIFI_SSID, WIFI_PASS, SERVER_URL)
#include "credential.hpp"

extern OneWire           oneWire;  ///< Глобальный объект шины OneWire
extern DallasTemperature sensors;  ///< Глобальный объект датчиков DS18B20

/// @name Аппаратные выводы
///@{
constexpr uint8_t TEMP_SENSOR_PIN = 4; ///< Пин OneWire
constexpr uint8_t STATUS_LED      = 2; ///< Встроенный светодиод (Wi-Fi статус)
///@}

/// @name Хранилище
///@{
constexpr char     CSV_PATH[]            = "/temper.csv";
constexpr unsigned long SAVE_INTERVAL_MS = 60 * 1000; ///< Интервал записи (мс)
///@}

/// @name Заглушка RTC (раскомментировать при наличии DS3231)
///@{
// #include <RTClib.h>
// extern RTC_DS3231 rtc;
extern bool rtcOK; ///< "rtcOK = true" когда RTC подключён и инициализирован
///@}

/**
 * @struct SensorReading
 * @brief  Показания двух датчиков за один цикл.
 */
struct SensorReading
{
     float temp0 = DEVICE_DISCONNECTED_C; ///< Температура датчика 0
     float temp1 = DEVICE_DISCONNECTED_C; ///< Температура датчика 1
};

/**
 * @brief Инициализирует привязку датчиков: читает адреса из NVS или сканирует шину
 *        и сохраняет привязку «канал 0 – адрес, канал 1 – адрес» в NVS.
 */
void InitSensorBinding();

/**
 * @brief Считывает температуру по сохранённым адресам.
 * @return SensorReading с актуальными значениями.
 */
SensorReading ReadSensors();

/**
 * @brief Инициализирует LittleFS, создаёт CSV с заголовком если файла нет,
 *        и записывает маркер RESET при старте без RTC.
 */
void InitStorage();

/**
 * @brief Дописывает одну строку в CSV.
 * @param reading Показания датчиков.
 */
void LogReading( const SensorReading& reading );

/**
 * @brief Подключается к Wi-Fi.
 */
void InitWiFi();

/**
 * @brief Отправляет показания на HTTP-сервер POST JSON.
 * @param reading Показания датчиков.
 */
void SendToServer( const SensorReading& reading );

/**
 * @brief Обрабатывает команды из Serial:
 *        "download" — вывести CSV в Serial,
 *        "clear"    — очистить CSV,
 *        "rebind"   — сбросить привязку датчиков (требуется перезагрузка).
 */
void HandleSerialCommands();
