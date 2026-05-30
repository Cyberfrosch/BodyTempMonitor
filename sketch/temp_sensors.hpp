/**
 * @file      temp_sensors.hpp
 * @brief     Датчики температуры DS18B20: инициализация, привязка адресов и чтение.
 * @details   Привязка адресов хранится в NVS namespace "sensors", ключи "addr0"/"addr1".
 */

#pragma once

#include <cstdint>

#include <DallasTemperature.h>

/// @name Аппаратные параметры датчиков
///@{
constexpr uint8_t TEMP_SENSOR_PIN      = 4;  ///< Пин OneWire
constexpr int     MIN_SENSORS_REQUIRED = 2;  ///< Минимум датчиков для работы
constexpr size_t  DEVICE_ADDR_SIZE     = 8;  ///< Размер адреса устройства OneWire (байт)
constexpr size_t  SENSOR_ADDR_STR_LEN = 17; ///< Длина строкового адреса: 16 hex-символов + '\0'
///@}

/**
 * @struct SensorReading
 * @brief  Показания двух датчиков за один цикл измерения.
 */
struct SensorReading
{
     float temp0 = DEVICE_DISCONNECTED_C; ///< Температура датчика 0
     float temp1 = DEVICE_DISCONNECTED_C; ///< Температура датчика 1
};

/**
 * @brief Инициализирует датчики DS18B20.
 * @details Загружает сохранённые адреса из NVS namespace "sensors". Если адреса отсутствуют,
 *          сканирует шину и сохраняет новую привязку. Если сохранённые датчики не найдены
 *          на шине — очищает NVS и возвращает false.
 * @return true если датчики найдены и готовы к работе.
 */
bool InitSensors();

/**
 * @brief Считывает температуру по сохранённым адресам датчиков.
 * @return SensorReading с актуальными значениями.
 */
SensorReading ReadSensors();

/**
 * @brief Проверяет, что оба датчика доступны на шине.
 * @return true если оба датчика отвечают.
 */
bool AreSensorsConnected();

/**
 * @brief Очищает привязку датчиков в NVS namespace "sensors".
 * @details После вызова требуется перезагрузка для повторного сканирования шины.
 */
void ClearSensorBinding();
