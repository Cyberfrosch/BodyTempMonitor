/**
 * @file      clock_rtc.hpp
 * @brief     Часы реального времени DS3231: инициализация, время, коррекция от NTP.
 */

#pragma once

#include <RTClib.h>
#include <cstdint>
#include <ctime>

constexpr uint8_t RTC_I2C_ADDR = 0x68; ///< I2C-адрес DS3231

/**
 * @brief Инициализирует RTC DS3231.
 * @return true если RTC инициализирован успешно, false при ошибке.
 */
bool InitRTC();

/**
 * @brief Проверяет подключение RTC через I2C.
 * @return true если RTC отвечает на шине.
 */
bool IsRTCconnected();

/**
 * @brief Возвращает текущую метку времени.
 * @return Unix-время от RTC если модуль доступен, иначе millis()/1000.
 */
unsigned long CurrentTimestamp();

/**
 * @brief Корректирует время RTC.
 * @param t Новое время (Unix-time).
 * @return true если RTC был доступен и время скорректировано, false иначе.
 */
bool AdjustRTC( time_t t );
