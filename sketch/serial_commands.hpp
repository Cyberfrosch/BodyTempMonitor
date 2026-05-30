/**
 * @file      serial_commands.hpp
 * @brief     Диспетчер Serial-команд устройства.
 */

#pragma once

/**
 * @brief Считывает команду из Serial и выполняет её.
 * @details Поддерживаемые команды:
 *          - download       — вывести CSV в Serial
 *          - clear          — очистить CSV
 *          - rebind         — сбросить привязку датчиков (требуется перезагрузка)
 *          - config show    — вывести текущую конфигурацию
 *          - config set k=v — установить параметр конфигурации
 *          - config reset   — сбросить конфигурацию к значениям по умолчанию
 */
void HandleSerialCommands();
