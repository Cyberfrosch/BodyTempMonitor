/**
 * @file      temperature_monitor.h
 * @brief     Заголовочный файл модуля мониторинга температуры (два датчика DS18B20).
 * @details   Содержит объявления глобальных объектов, аппаратных констант,
 *            структур состояния, перечислений режимов и прототипов функций.
 */

#pragma once

#include <cstdint>

#include <DallasTemperature.h>
#include <LiquidCrystal_I2C.h>
#include <OneWire.h>
#include <Wire.h>

extern LiquidCrystal_I2C lcd;     ///< Глобальный объект LCD-дисплея (I2C, адрес 0x27, 20x4)
extern OneWire oneWire;           ///< Глобальный объект шины OneWire для подключения датчиков DS18B20
extern DallasTemperature sensors; ///< Глобальный объект для управления датчиками температуры DS18B20

/// @name Аппаратные выводы (pin definitions)
///@{
constexpr uint8_t TEMP_SENSOR_PIN = 4; ///< Пин для датчиков температуры (OneWire)
constexpr uint8_t FAN_LED = 18;        ///< Пин светодиода/вентилятора
constexpr uint8_t HEATER_LED = 19;     ///< Пин светодиода/нагревателя
///@}

/// @name Настройки LCD
///@{
constexpr uint8_t LCD_ADDR = 0x27; ///< I2C‑адрес LCD
constexpr uint8_t LCD_COLS = 20;   ///< Количество столбцов
constexpr uint8_t LCD_ROWS = 4;    ///< Количество строк
///@}

/// @name Температурные пороги (медицинские диапазоны)
///@{
constexpr float HYPOTHERMIA_THRESHOLD = 35.0f; ///< Ниже – гипотермия
constexpr float NORMAL_THRESHOLD = 37.5f;      ///< Выше – повышенная
constexpr float FEVER_THRESHOLD = 40.0f;       ///< Выше – лихорадка
///@}

/// @name Временные интервалы
///@{
constexpr unsigned long MEASURE_INTERVAL_MS = 2000; ///< Период измерений (мс)
constexpr unsigned long BLINK_INTERVAL_MS = 500;    ///< Период мигания в аварийном режиме (мс)
///@}

/**
 * @struct SystemState
 * @brief  Текущее состояние системы (температуры и флаги валидности).
 */
struct SystemState
{
     float temp1 = 0.0f;      ///< Значение с первого датчика
     float temp2 = 0.0f;      ///< Значение со второго датчика
     bool valid1 = false;     ///< Флаг, что первый датчик отвечает корректно
     bool valid2 = false;     ///< Флаг, что второй датчик отвечает корректно
     float maxTemp = -100.0f; ///< Максимальная из двух валидных температур
};

/**
 * @enum AlarmState
 * @brief Состояние сигнализации (мигание светодиодов).
 */
enum class AlarmState
{
     NORMAL, ///< Обычный режим (нет мигания)
     ALARM   ///< Аварийный режим (мигание)
};

/**
 * @enum OperatingMode
 * @brief Режим работы устройства на основе измеренной температуры.
 */
enum class OperatingMode
{
     HYPOTHERMIA, ///< Гипотермия (t < 35)
     NORMAL,      ///< Норма (35 ≤ t ≤ 37.5)
     FEVER,       ///< Лихорадка (37.5 < t ≤ 40)
     CRITICAL,    ///< Критическая гипертермия (t > 40)
     SENSOR_ERROR ///< Ошибка датчиков (оба невалидны)
};

/**
 * @brief Проверяет, находится ли температура в допустимом диапазоне.
 * @param t Значение температуры.
 * @return true если -50 < t < 100, иначе false.
 */
bool IsValidTemp( float t );

/**
 * @brief Опрашивает датчики и обновляет состояние.
 * @param state Ссылка на структуру SystemState для записи результатов.
 */
void ReadSensors( SystemState& state );

/**
 * @brief Определяет режим работы по текущему состоянию.
 * @param state Текущее состояние (температуры).
 * @return Режим OperatingMode.
 */
OperatingMode DetermineMode( const SystemState& state );

/**
 * @brief Преобразует режим работы в строку для вывода на LCD.
 * @param mode Режим.
 * @return Указатель на статическую строку.
 */
const char* ModeToString( OperatingMode mode );

/**
 * @brief Выводит строку в заданную строку LCD, дополняя пробелами до конца.
 * @param row  Номер строки (0–3).
 * @param text Текст для вывода.
 */
void LcdPrintRow( uint8_t row, const char* text );

/**
 * @brief Обновляет содержимое LCD.
 * @param state Текущее состояние.
 * @param mode  Текущий режим.
 */
void UpdateLcd( const SystemState& state, OperatingMode mode );

/**
 * @brief Управляет выходами (светодиоды) в зависимости от режима.
 * @param mode       Текущий режим.
 * @param alarmState Состояние аварийной сигнализации (изменяется).
 * @param blinkState Текущее состояние мигания (изменяется).
 * @param lastBlink  Время последнего переключения мигания (изменяется).
 */
void UpdateOutputs( OperatingMode mode, AlarmState& alarmState, bool& blinkState, unsigned long& lastBlink );
