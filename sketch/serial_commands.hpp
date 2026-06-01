/**
 * @file      serial_commands.hpp
 * @brief     Транспортно-независимая обработка команд устройства.
 * @details   Ядро разбора команд вынесено в ProcessCommand — оно не знает о транспорте.
 *            Serial-канал: HandleSerialCommands читает строку и вызывает ProcessCommand.
 *            BLE-канал: ble_config.cpp вызывает ProcessCommand с BLE-нотификационным колбэком.
 *
 *            Поддерживаемые команды:
 *              - download           — вывести CSV в Serial
 *              - clear              — очистить CSV
 *              - rebind             — сбросить привязку датчиков (требуется перезагрузка)
 *              - config show        — вывести текущую конфигурацию
 *              - config set key=val — установить параметр конфигурации
 *              - config reset       — сбросить конфигурацию к значениям по умолчанию
 */

#pragma once

#include <Arduino.h>

/// Колбэк вывода одной строки ответа на транспортный канал (Serial, BLE notify и т.п.).
using Responder = void(*)( const String& );

/**
 * @brief Разбирает и выполняет команду; ответ направляется через колбэк.
 * @param cmd     Текст команды (как по Serial, без завершающего '\n').
 * @param respond Функция вывода строки ответа — не накапливает, вызывается на каждую строку.
 * @note  Команды download/clear/rebind выводят основные данные в Serial независимо от канала;
 *        через respond передаётся только статус завершения.
 */
void ProcessCommand( const String& cmd, Responder respond );

/**
 * @brief Считывает строку из Serial и передаёт её в ProcessCommand.
 * @details Вызывать в каждой итерации loop().
 */
void HandleSerialCommands();
