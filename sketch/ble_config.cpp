/**
 * @file      ble_config.cpp
 * @brief     Реализация BLE GATT-сервиса конфигурации.
 * @details   Транспорт: встроенная библиотека BLEDevice (Arduino ESP32, Bluedroid).
 *            Безопасность: LE Secure Connections, MITM (Passkey Entry), бондинг.
 *            Passkey задаётся в sketch/ble_secret.hpp (не в репозитории).
 *
 *            Схема работы:
 *              1. Клиент подключается и проходит паринг: вводит passkey из Serial Monitor.
 *              2. Клиент записывает команду в характеристику CMD_CHAR (напр. "config show").
 *              3. Устройство выполняет команду через ProcessCommand и отправляет ответ
 *                 нотификациями в RSP_CHAR, разбивая на чанки BLE_CHUNK_SIZE байт.
 *              4. После disconnect реклама перезапускается автоматически (через UpdateBLE).
 */

#include "ble_config.hpp"
#include "ble_secret.hpp"
#include "serial_commands.hpp"

#include <Arduino.h>
#include <BLE2902.h>
#include <BLEDevice.h>
#include <BLESecurity.h>
#include <BLEServer.h>
#include <esp_gap_ble_api.h>

// ------------------------------------------------------------------ UUIDs / constants

static constexpr const char* SERVICE_UUID    = "4fa9c0de-b7f2-4f1d-84be-02e3890f7af8";
static constexpr const char* CMD_CHAR_UUID   = "4fa9c0df-b7f2-4f1d-84be-02e3890f7af8";
static constexpr const char* RSP_CHAR_UUID   = "4fa9c0e0-b7f2-4f1d-84be-02e3890f7af8";

/// Имя устройства в BLE-эфире.
static constexpr const char* BLE_DEVICE_NAME = "BodyTempMonitor";

/**
 * @brief Размер чанка notify-ответа (байт).
 * @details Выбран для MTU ≥ 185 (автоматически запрашиваемый nRF Connect на Android).
 *          При согласованном MTU 185 полезная нагрузка = 185 - 3 = 182 байта.
 *          При дефолтном MTU 23 (20 байт payload) данные разбиваются на более мелкие чанки
 *          автоматически — каждая строка конфига < 60 байт влезает в 3 нотификации.
 */
static constexpr size_t BLE_CHUNK_SIZE = 182;

// ------------------------------------------------------------------ module state

static BLECharacteristic* g_pResponseChar = nullptr;
static volatile bool      g_needRestartAdv = false;

// ------------------------------------------------------------------ BLE responder

/**
 * @brief Отправляет строку через BLE Notify, разбивая на чанки при необходимости.
 * @details Вызывается как Responder-колбэк из ProcessCommand.
 *          Каждый чанк — отдельная notify-нотификация. Короткая пауза между чанками
 *          предотвращает переполнение буферов BLE-стека.
 * @param line Строка ответа (без завершающего '\n' — добавляется здесь).
 */
static void BleRespond( const String& line )
{
    if( !g_pResponseChar ) return;

    String data = line + "\n";
    size_t len  = (size_t)data.length();

    for( size_t i = 0; i < len; i += BLE_CHUNK_SIZE )
    {
        String chunk = data.substring( (int)i, (int)( i + BLE_CHUNK_SIZE ) );
        g_pResponseChar->setValue( chunk.c_str() );
        g_pResponseChar->notify();
        if( len > BLE_CHUNK_SIZE ) delay( 20 ); // пауза только при реальном разрезании
    }
}

// ------------------------------------------------------------------ BLE callbacks

class BleServerCallbacks : public BLEServerCallbacks
{
    void onConnect( BLEServer* ) override
    {
        Serial.println( "BLE: client connected" );
    }

    void onDisconnect( BLEServer* ) override
    {
        Serial.println( "BLE: client disconnected" );
        g_needRestartAdv = true; // перезапуск в UpdateBLE(), а не в callback
    }
};

class CommandCallbacks : public BLECharacteristicCallbacks
{
    void onWrite( BLECharacteristic* pChar ) override
    {
        // Вызывается только если клиент прошёл аутентификацию (ESP_GATT_PERM_WRITE_ENC_MITM).
        String value = pChar->getValue();
        if( value.length() == 0 ) return;

        String cmd = value;
        cmd.trim();
        Serial.printf( "BLE cmd: %s\n", cmd.c_str() );
        ProcessCommand( cmd, BleRespond );
    }
};

class BleSecurityCallbacks : public BLESecurityCallbacks
{
    /// Вызывается когда устройство должно ввести passkey (роль Keyboard — не наш случай).
    uint32_t onPassKeyRequest() override
    {
        return BLE_PASSKEY;
    }

    /**
     * @brief Вызывается когда устройство должно "отобразить" passkey (роль Display Only).
     * @details Для статического passkey значение всегда равно BLE_PASSKEY.
     *          Выводим в Serial, чтобы пользователь мог его прочитать и ввести в nRF Connect.
     */
    void onPassKeyNotify( uint32_t pass_key ) override
    {
        Serial.printf( "BLE Passkey: %06lu\n", (unsigned long)pass_key );
    }

    /// Вызывается при Numeric Comparison (LE SC). Не применимо при Passkey Entry.
    bool onConfirmPIN( uint32_t ) override
    {
        return true;
    }

    /// Разрешаем входящие запросы паринга.
    bool onSecurityRequest() override
    {
        return true;
    }

    void onAuthenticationComplete( esp_ble_auth_cmpl_t auth_cmpl ) override
    {
        if( auth_cmpl.success )
            Serial.println( "BLE: authentication OK — bonded" );
        else
            Serial.printf( "BLE: authentication failed (reason %d)\n", auth_cmpl.fail_reason );
    }
};

// ------------------------------------------------------------------ public API

void InitBLE()
{
    BLEDevice::init( BLE_DEVICE_NAME );

    // Запрашиваем максимальный MTU; реально согласуется минимум из server+client.
    // nRF Connect на Android поддерживает до 517 байт (514 байт payload).
    BLEDevice::setMTU( 517 );

    // --- Безопасность -------------------------------------------------------
    // LE Secure Connections + MITM + бондинг. Статический passkey, Display Only:
    // peripheral "показывает" passkey → пользователь вводит его на телефоне.
    BLEDevice::setSecurityCallbacks( new BleSecurityCallbacks() );

    BLESecurity* pSecurity = new BLESecurity();
    pSecurity->setAuthenticationMode( ESP_LE_AUTH_REQ_SC_MITM_BOND );
    pSecurity->setCapability( ESP_IO_CAP_OUT );                               // Display Only
    pSecurity->setInitEncryptionKey( ESP_BLE_ENC_KEY_MASK | ESP_BLE_ID_KEY_MASK );
    pSecurity->setRespEncryptionKey( ESP_BLE_ENC_KEY_MASK | ESP_BLE_ID_KEY_MASK );
    pSecurity->setKeySize( 16 );

    // BLESecurity::setStaticPin отсутствует в этой версии библиотеки —
    // устанавливаем статический passkey напрямую через GAP.
    uint32_t pin = BLE_PASSKEY;
    esp_ble_gap_set_security_param( ESP_BLE_SM_SET_STATIC_PASSKEY, &pin, sizeof( pin ) );

    // --- GATT-сервер --------------------------------------------------------
    BLEServer* pServer = BLEDevice::createServer();
    pServer->setCallbacks( new BleServerCallbacks() );

    BLEService* pService = pServer->createService( SERVICE_UUID );

    // Характеристика команды: Write, требует шифрования + MITM.
    // Неспаренный клиент получает ATT error 0x0F (Insufficient Authorization).
    BLECharacteristic* pCmdChar = pService->createCharacteristic(
        CMD_CHAR_UUID,
        BLECharacteristic::PROPERTY_WRITE
    );
    pCmdChar->setAccessPermissions( ESP_GATT_PERM_WRITE_ENC_MITM );
    pCmdChar->setCallbacks( new CommandCallbacks() );

    // Характеристика ответа: Notify + Read, требует шифрования + MITM.
    BLECharacteristic* pRspChar = pService->createCharacteristic(
        RSP_CHAR_UUID,
        BLECharacteristic::PROPERTY_READ | BLECharacteristic::PROPERTY_NOTIFY
    );
    pRspChar->setAccessPermissions( ESP_GATT_PERM_READ_ENC_MITM );

    // CCCD (0x2902) — дескриптор подписки на notify. Требуем аутентификацию и для него,
    // чтобы неспаренный клиент не мог подписаться на нотификации.
    BLE2902* p2902 = new BLE2902();
    p2902->setAccessPermissions( ESP_GATT_PERM_READ_ENC_MITM | ESP_GATT_PERM_WRITE_ENC_MITM );
    pRspChar->addDescriptor( p2902 );

    g_pResponseChar = pRspChar;

    // --- Реклама ------------------------------------------------------------
    pService->start();

    BLEAdvertising* pAdv = BLEDevice::getAdvertising();
    pAdv->addServiceUUID( SERVICE_UUID );
    pAdv->setScanResponse( true );
    pAdv->setMinPreferred( 0x06 ); // минимальный интервал соединения (7.5 мс) — для iOS
    pAdv->setMaxPreferred( 0x12 ); // максимальный интервал (22.5 мс)
    BLEDevice::startAdvertising();

    Serial.printf( "BLE: advertising as '%s'\n", BLE_DEVICE_NAME );
    Serial.printf( "BLE: passkey for pairing: %06lu\n", (unsigned long)BLE_PASSKEY );
}

void UpdateBLE()
{
    if( g_needRestartAdv )
    {
        g_needRestartAdv = false;
        BLEDevice::startAdvertising();
        Serial.println( "BLE: advertising restarted" );
    }
}
