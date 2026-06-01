/**
 * @file      ble_secret.example.hpp
 * @brief     Пример файла с BLE passkey.
 * @details   Скопируйте этот файл в ble_secret.hpp и задайте собственный 6-значный PIN.
 *            ble_secret.hpp добавлен в .gitignore и не попадает в репозиторий.
 */

#pragma once

#include <cstdint>

/// 6-значный passkey для BLE-паринга. Устройство "показывает" его в Serial Monitor.
constexpr uint32_t BLE_PASSKEY = 123456;
