/**
 * @file      system.hpp
 * @brief     Системные константы и аварийная остановка устройства.
 */

#pragma once

#include <cstdio>

constexpr uint8_t       STATUS_LED         = 2;    ///< Встроенный светодиод (статус Wi-Fi)
constexpr unsigned long SERIAL_BAUD_RATE   = 115200;
constexpr size_t        SERIAL_RX_BUF_SIZE = 1024;

/**
 * @brief Останавливает работу устройства при критической ошибке инициализации.
 * @details Выводит сообщение в Serial и входит в бесконечный цикл с миганием светодиода.
 *          Выход только по перезагрузке.
 * @param component Название компонента, инициализация которого не удалась.
 */
[[noreturn]] void HaltWithError( const char* component );
