/**
 * @file      storage.hpp
 * @brief     Хранилище данных измерений: LittleFS и CSV-журнал.
 */

#pragma once

#include "temp_sensors.hpp"

constexpr char   CSV_PATH[]    = "/temper.csv"; ///< Путь к файлу журнала в LittleFS
constexpr size_t CSV_LINE_SIZE = 48;            ///< Максимальная длина строки CSV (байт)

/**
 * @brief Инициализирует LittleFS; создаёт CSV с заголовком если файла нет.
 * @return true если LittleFS инициализирована успешно.
 */
bool InitStorage();

/**
 * @brief Дописывает одну строку с показаниями датчиков в CSV.
 * @param reading Показания датчиков.
 */
void LogReading( const SensorReading& reading );

/**
 * @brief Выводит содержимое CSV в Serial (команда "download").
 */
void DownloadCSV();

/**
 * @brief Очищает CSV и записывает заголовок (команда "clear").
 */
void ClearCSV();
