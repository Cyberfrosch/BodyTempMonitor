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
#include <RTClib.h>
#include <WiFi.h>

// Учетные данные (WIFI_SSID, WIFI_PASS, SERVER_URL)
#include "credential.hpp"

extern OneWire           oneWire;  ///< Глобальный объект шины OneWire
extern DallasTemperature sensors;  ///< Глобальный объект датчиков DS18B20
extern Preferences       prefs;    ///< Глобальный объект для работы с NVS

/// @name Аппаратные выводы
///@{
constexpr uint8_t TEMP_SENSOR_PIN = 4; ///< Пин OneWire
constexpr uint8_t STATUS_LED      = 2; ///< Встроенный светодиод (Wi-Fi статус)
///@}

/// @name Serial
///@{
constexpr unsigned long SERIAL_BAUD_RATE   = 115200; ///< Скорость UART
constexpr size_t        SERIAL_RX_BUF_SIZE = 1024;   ///< RX-буфер
///@}

/// @name Хранилище
///@{
constexpr char CSV_PATH[] = "/temper.csv"; ///< Путь к файлу журнала в LittleFS
///@}

/**
 * @struct Config
 * @brief  Конфигурация устройства (хранится в NVS).
 */
struct Config
{
     char wifi_ssid[64]                = "";
     char wifi_pass[64]                = "";
     char server_url[128]              = "";
     char ntp_server[64]               = "pool.ntp.org";
     long gmt_offset_sec               = 7 * 3600; ///< UTC+7 по умолчанию
     int daylight_offset_sec           = 0;
     unsigned long save_interval_ms    = 10 * 1000;
     unsigned long http_timeout_ms     = 5000;
     unsigned long http_retry_delay_ms = 1000;
     int wifi_connect_attempts         = 20;
     bool valid                        = false; ///< Флаг загрузки из NVS
};

extern Config config;

/**
 * @brief Загружает конфигурацию из NVS.
 */
void LoadConfig();

/**
 * @brief Сохраняет конфигурацию в NVS.
 */
void SaveConfig();

/**
 * @brief Сбрасывает конфигурацию к значениям по умолчанию.
 */
void ResetConfig();

/// @name Датчики
///@{
constexpr int MIN_SENSORS_REQUIRED = 2; ///< Минимум датчиков для работы
constexpr size_t DEVICE_ADDR_SIZE  = 8; ///< Размер адреса устройства OneWire (байт)
///@}

/// @name Заглушка RTC
///@{
constexpr uint8_t RTC_I2C_ADDR = 0x68; ///< I2C-адрес DS3231
extern RTC_DS3231 rtc;
extern bool rtcOK;
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
 * @brief Инициализирует RTC DS3231.
 * @return true если RTC инициализирован успешно, false при ошибке.
 */
bool InitRTC();

/**
 * @brief Инициализирует датчики температуры DS18B20.
 * @details Загружает сохранённые адреса датчиков из NVS и проверяет их наличие на шине.
 *          Если адреса не найдены или датчики отключены, выполняет сканирование шины
 *          и сохраняет новую привязку каналов к адресам в NVS.
 * @return true если датчики найдены и инициализированы, false при ошибке.
 */
bool InitSensors();

/**
 * @brief Считывает температуру по сохранённым адресам.
 * @return SensorReading с актуальными значениями.
 */
SensorReading ReadSensors();

/**
 * @brief Проверяет подключение RTC через I2C.
 * @return true если RTC отвечает на шине, false иначе.
 */
bool IsRTCconnected();

/**
 * @brief Проверяет, что все устройства подключены.
 */
void CheckDevices();

/**
 * @brief Инициализирует LittleFS, создаёт CSV с заголовком если файла нет.
 * @return true если LittleFS инициализирована успешно, false при ошибке.
 */
bool InitStorage();

/**
 * @brief Дописывает одну строку в CSV.
 * @param reading Показания датчиков.
 */
void LogReading( const SensorReading& reading );

/**
 * @brief Подключается к Wi-Fi и синхронизирует время по NTP.
 */
void InitWiFi();

/**
 * @brief Отправляет показания на HTTP-сервер POST JSON.
 * @param reading Показания датчиков.
 */
void SendToServer( const SensorReading& reading );

/**
 * @brief Обрабатывает команды из Serial:
 *        `download` — вывести CSV в Serial,
 *        `clear`    — очистить CSV,
 *        `rebind`   — сбросить привязку датчиков (требуется перезагрузка).
 */
void HandleSerialCommands();

/**
 * @brief Останавливает работу устройства при критической ошибке инициализации.
 * @details Выводит сообщение об ошибке в Serial и входит в бесконечный цикл
 *          с миганием светодиода. Выход только по перезагрузке.
 * @param component Название компонента, инициализация которого не удалась.
 */
[[noreturn]] void HaltWithError( const char* component );
