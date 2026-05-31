/**
 * @file      config_store.hpp
 * @brief     Конфигурация устройства: структура данных и операции с NVS.
 * @details   Хранит параметры в NVS namespace "config". Ключи NVS фиксированы -
 *            их изменение ломает совместимость с уже прошитыми устройствами.
 */

#pragma once

#include <Arduino.h>

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
     bool valid                        = false; ///< Флаг успешной загрузки из NVS
};

extern Config config; ///< Глобальный объект конфигурации

/**
 * @brief Загружает конфигурацию из NVS. При отсутствии ключей вызывает ResetConfig().
 */
void LoadConfig();

/**
 * @brief Сохраняет текущую конфигурацию в NVS.
 */
void SaveConfig();

/**
 * @brief Очищает NVS namespace "config" и сбрасывает конфигурацию к значениям по умолчанию.
 */
void ResetConfig();

/**
 * @brief Применяет пару ключ=значение к структуре Config (без сохранения в NVS).
 * @details Используется как Serial-командой «config set», так и HTTP-каналом веб-конфига.
 *          Сохранение в NVS - ответственность вызывающего кода (SaveConfig()).
 * @param key  Имя параметра (совпадает с ключом Serial-протокола).
 * @param val  Строковое значение для присваивания.
 * @return true если ключ известен и применён, false если ключ неизвестен.
 */
bool ApplyConfigKey( const String& key, const String& val );
