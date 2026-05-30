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
 * @brief Подключается к Wi-Fi, синхронизирует время по NTP и корректирует RTC.
 */
void InitWiFi();

/**
 * @brief Отправляет показания датчиков на HTTP-сервер методом POST (JSON).
 * @param reading Показания датчиков.
 */
void SendToServer( const SensorReading& reading );
