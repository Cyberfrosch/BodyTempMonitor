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
 * @brief Размер буфера URL конфигурации устройства (байт).
 * @details URL выводится из server_url заменой хвоста "/api/data" → "/api/config".
 *          128 (server_url) - 9 ("/api/data") + 11 ("/api/config") + 1 (NUL) = 131 → 144 с запасом.
 */
constexpr size_t CONFIG_URL_SIZE = 144;

/**
 * @brief Подключается к Wi-Fi, синхронизирует время по NTP и корректирует RTC.
 */
void InitWiFi();

/**
 * @brief Отправляет показания датчиков на HTTP-сервер методом POST (JSON).
 * @param reading Показания датчиков.
 */
void SendToServer( const SensorReading& reading );
