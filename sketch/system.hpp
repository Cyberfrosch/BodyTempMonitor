/**
 * @file      system.hpp
 * @brief     Системные константы, LED-индикация и аварийный перезапуск.
 */

#pragma once

#include <cstdio>

/// @name Аппаратные выводы и Serial
///@{
constexpr uint8_t       STATUS_LED         = 2;    ///< Встроенный светодиод (статус)
constexpr unsigned long SERIAL_BAUD_RATE   = 115200;
constexpr size_t        SERIAL_RX_BUF_SIZE = 1024;
///@}

/// @name Параметры LED-индикации
///@{
constexpr unsigned long FAULT_BLINK_PERIOD_MS      = 200;   ///< Период мигания при аппаратном сбое (мс)
constexpr unsigned long FAULT_REBOOT_DELAY_MS      = 10000; ///< Окно индикации перед ребутом (мс)
constexpr unsigned long SERVER_ERR_BLINK_PERIOD_MS = 150;   ///< Единица паттерна двойной вспышки при ошибке сервера (мс)
///@}

/**
 * @brief Индикирует аппаратный сбой быстрым миганием в течение FAULT_REBOOT_DELAY_MS.
 * @details Блокирует вызывающий поток на ~FAULT_REBOOT_DELAY_MS мс. Вызывается из
 *          FaultReboot() перед ESP.restart().
 */
void IndicateFault();

/**
 * @brief Индикирует ошибку соединения с сервером тремя двойными вспышками.
 * @details Не блокирует надолго (~2.7 с). Паттерн двойных вспышек визуально
 *          отличим от быстрого мигания аппаратного сбоя.
 */
void IndicateServerError();

/**
 * @brief Индицирует аппаратный сбой и перезагружает устройство.
 * @details Выводит сообщение в Serial, вызывает IndicateFault() (~10 с),
 *          затем ESP.restart(). Устройство самостоятельно восстановится,
 *          когда неисправный модуль снова окажется на связи.
 * @param component Название компонента, инициализация или проверка которого не удалась.
 */
[[noreturn]] void FaultReboot( const char* component );
