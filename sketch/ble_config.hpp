/**
 * @file      ble_config.hpp
 * @brief     BLE GATT-сервис для удалённого управления конфигурацией устройства.
 * @details   Экспонирует одну характеристику команды (Write) и одну характеристику
 *            ответа (Notify + Read). Доступ разрешён только зашифрованным и
 *            аутентифицированным клиентам (LE Secure Connections + MITM + бондинг).
 *
 *            UUID сервиса:  4fa9c0de-b7f2-4f1d-84be-02e3890f7af8
 *            UUID команды:  4fa9c0df-b7f2-4f1d-84be-02e3890f7af8
 *            UUID ответа:   4fa9c0e0-b7f2-4f1d-84be-02e3890f7af8
 *
 * @note      Partition scheme: «Huge APP (3MB No OTA)» или «Minimal SPIFFS» —
 *            Wi-Fi + BLE + LittleFS не вмещаются в дефолтную схему разделов.
 */

#pragma once

/**
 * @brief Инициализирует BLE-устройство, GATT-сервис и параметры безопасности.
 * @details После вызова устройство видно в эфире как «BodyTempMonitor».
 *          Характеристики доступны только после успешного паринга с passkey.
 *          Вызывать один раз в setup() после LoadConfig().
 */
void InitBLE();

/**
 * @brief Обновляет состояние BLE: перезапускает рекламу после disconnect.
 * @details Вызывать в каждой итерации loop(). Операции тяжелее флага не выполняются —
 *          overhead пренебрежимо мал.
 */
void UpdateBLE();
