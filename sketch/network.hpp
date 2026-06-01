/**
 * @file      network.hpp
 * @brief     Сетевые функции: Wi-Fi, синхронизация NTP, HTTP-отправка показаний.
 */

#pragma once

#include "temp_sensors.hpp"

constexpr unsigned long NTP_TIMEOUT_MS      = 10000; ///< Таймаут ожидания NTP-ответа (мс)
constexpr unsigned long WIFI_RETRY_DELAY_MS = 500;   ///< Задержка между попытками подключения Wi-Fi (мс)
constexpr size_t        HTTP_PAYLOAD_SIZE   = 96;    ///< Размер буфера HTTP-payload (байт)

/**
 * @brief Размер буфера полного HTTP-URL (байт).
 * @details "http://" (7) + host:port (макс. 48) + путь (макс. 12) + NUL = ~68;
 *          160 байт оставляет запас для длинных имён хостов.
 */
constexpr size_t HTTP_URL_SIZE = 160;

/// Путь эндпоинта отправки показаний датчиков (POST).
constexpr const char* API_DATA_PATH   = "/api/data";

/// Путь эндпоинта получения конфигурации устройства (GET).
constexpr const char* API_CONFIG_PATH = "/api/config";

/**
 * @brief Размер буфера ETag в NVS (байт).
 * @details ETag — первые 16 hex-символов SHA-256 несвязочного конфига + NUL.
 */
constexpr size_t WEB_ETAG_NVS_SIZE = 17;

/**
 * @brief Подключается к Wi-Fi, синхронизирует время по NTP и корректирует RTC.
 */
void InitWiFi();

/**
 * @brief Отправляет показания датчиков на HTTP-сервер методом POST (JSON).
 * @param reading Показания датчиков.
 */
void SendToServer( const SensorReading& reading );
