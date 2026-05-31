# BodyTempMonitor

Мониторинг температуры тела с использованием двух датчиков DS18B20. Устройство периодически считывает температуру, сохраняет данные в CSV-файл на LittleFS и отправляет их на HTTP-сервер по Wi-Fi.

<img src="wiring-diagram.png" width="640" alt="Схема подключения"/>

## Особенности

- Измерение температуры двумя независимыми датчиками DS18B20.
- Периодическая запись показаний в CSV-файл (`/temper.csv`) на LittleFS.
- Отправка данных на HTTP-сервер (POST JSON) при наличии Wi-Fi.
- Поддержка модуля реального времени DS3231 для абсолютных меток времени.
- Синхронизация времени по NTP при подключении к Wi-Fi.
- Встроенный светодиод (пин 2) сигнализирует о статусе отправки на сервер.
- Serial-команды для работы с журналом:
  - `download` - вывести содержимое CSV в Serial Monitor.
  - `clear` - очистить CSV и пересоздать с заголовком.

## Аппаратное обеспечение

- Микроконтроллер: ESP32 (поддержка LittleFS, Wi-Fi).
- Датчики: 2 × DS18B20 (шина OneWire, пин 4).
- Резистор 4.7 кОм для подтяжки шины OneWire.
- Обязательно: модуль RTC DS3231 для абсолютных меток времени.
- Опционально: модуль DS3231 с батарейкой для сохранения времени при отключении.

## Схема подключения

| Компонент      | Пин ESP32 | Примечание                        |
|----------------|-----------|-----------------------------------|
| DS18B20 (DATA) | 4         | Подтяжка к 3.3В резистором 4.7кОм |
| STATUS LED     | 2         | Встроенный светодиод ESP32        |
| DS3231 (SDA)   | 21        | I2C шина                           |
| DS3231 (SCL)   | 22        | I2C шина                           |

## Установка и настройка

### Требования

- **Arduino IDE** или **PlatformIO**.
- Библиотеки (менеджер библиотек):
  - **OneWire** (Paul Stoffregen)
  - **DallasTemperature** (Miles Burton)
  - **RTClib** (Adafruit)

### Сборка и загрузка

1. Клонируйте репозиторий:
   ```bash
   git clone https://github.com/Cyberfrosch/BodyTempMonitor.git
   ```
2. Откройте `sketch.ino` в Arduino IDE.
3. В `sketch/credential.hpp` укажите свои `WIFI_SSID`, `WIFI_PASS` и `SERVER_URL`.
4. Выберите плату **ESP32** и порт, нажмите **Загрузить**.

### Структура проекта

- `sketch.ino` - главный файл, `setup()` и `loop()`.
- `temperature_monitor.hpp` - константы, структура `SensorReading`, прототипы функций.
- `temperature_monitor.cpp` - реализация: чтение датчиков, LittleFS, Wi-Fi, HTTP, Serial-команды.
- `sketch/credential.hpp` - учетные данные Wi-Fi и URL сервера (не включён в git).

### Конфигурация

Все параметры в `temperature_monitor.hpp`:

#### Аппаратные выводы
- `TEMP_SENSOR_PIN` - пин OneWire (по умолчанию 4).
- `STATUS_LED` - пин светодиода (по умолчанию 2).

#### Хранилище
- `CSV_PATH` - путь к файлу журнала (по умолчанию `/temper.csv`).
- `SAVE_INTERVAL_MS` - интервал записи в мс (по умолчанию 10 сек).

#### HTTP
- `HTTP_TIMEOUT_MS` - таймаут HTTP-запроса (по умолчанию 5000 мс).
- `HTTP_RETRY_DELAY_MS` - задержка перед повторной попыткой (по умолчанию 1000 мс).

#### Wi-Fi
- `WIFI_CONNECT_ATTEMPTS` - максимум попыток подключения (по умолчанию 20).
- `WIFI_RETRY_DELAY_MS` - задержка между попытками (по умолчанию 500 мс).

#### NTP
- `NTP_SERVER` - адрес NTP сервера (по умолчанию `pool.ntp.org`).
- `GMT_OFFSET_SEC` - смещение часового пояса (по умолчанию 7*3600 для UTC+7).
- `DAYLIGHT_OFFSET_SEC` - смещение летнего времени (по умолчанию 0).

#### Датчики
- `MIN_SENSORS_REQUIRED` - минимум датчиков (по умолчанию 2).
- `DEVICE_ADDR_SIZE` - размер адреса OneWire (по умолчанию 8 байт).

#### Учетные данные (из `credential.hpp`)
- `WIFI_SSID` - имя Wi-Fi сети.
- `WIFI_PASS` - пароль Wi-Fi.
- `SERVER_URL` - адрес HTTP-сервера для POST.

## Использование

После загрузки прошивки:

1. В Serial Monitor (115200) появится статус инициализации RTC, LittleFS и Wi-Fi.
2. Каждые `SAVE_INTERVAL_MS` секунд в CSV записывается строка `unixtime,temp0,temp1`.
3. При наличии Wi-Fi данные отправляются POST-запросом на `SERVER_URL` с Unix timestamp.
4. Встроенный светодиод горит при успешной отправке, мигает при ошибке.

### Serial-команды

Введите команду в Serial Monitor и нажмите Enter:

| Команда    | Действие                              |
|------------|---------------------------------------|
| `download` | Вывести содержимое CSV в Serial       |
| `clear`    | Очистить CSV, пересоздать с заголовком |
| `rebind`   | Сбросить привязку датчиков (требуется перезагрузка) |

### Формат CSV

```
reltime,temp0,temp1
1735123456,36.60,37.20
1735123516,36.65,37.15
```

- `unixtime` - Unix timestamp от RTC (абсолютное время).
- При отсутствии RTC используется `millis() / 1000` (относительное время).

## Серверная часть (ПК)

### Зависимости

```bash
pip install flask pyserial
```

### server.py - приём данных по Wi-Fi

Flask-сервер принимает POST-запросы с ESP32 и сохраняет данные в `sensor_data.db`.

```bash
python server/server.py
```

- `POST /api/data` - принимает JSON `{"temp0": float, "temp1": float, "timestamp": int}`.
- `GET /dashboard` - веб-дашборд с графиком и заметками.
- `GET /api/chart-data` - JSON-данные для графика.
- `POST /api/notes` - добавление заметки.

Адрес сервера укажите в `sketch/credential.hpp` в поле `SERVER_URL`.

### logger.py - загрузка CSV через Serial

Если Wi-Fi недоступен, данные можно выгрузить напрямую с ESP32 через USB.

**Режим загрузки CSV:**
```bash
python server/logger.py
```

1. Скрипт отправляет команду `download` в Serial Monitor.
2. Считывает CSV между маркерами `--- BEGIN FILE ---` и `--- END FILE ---`.
3. Проверяет валидность значений (исключает -127 и значения вне диапазона).
4. Пропускает дубликаты, уже записанные сервером.
5. Сохраняет результат в `sensor_data.db`.

**Режим мониторинга в реальном времени:**
```bash
python server/logger.py --monitor
```

Отслеживает вывод Serial в реальном времени и автоматически сохраняет данные в БД при обнаружении строки `Logged: ...`. Остановка - Ctrl+C.

**Очистка CSV на ESP32:**
```bash
python server/logger.py --clear
```

Настройки в начале файла:

| Параметр      | Описание                          |
|---------------|-----------------------------------|
| `SERIAL_PORT` | COM-порт ESP32 (например, `COM5`) |
| `BAUD_RATE`   | Скорость (по умолчанию 115200)    |
| `DATABASE`    | Путь к SQLite-файлу               |

### config_tool.py - управление конфигурацией ESP32

Утилита читает и записывает параметры NVS-хранилища устройства через Serial.

**Показать текущую конфигурацию:**
```bash
python server/config_tool.py --show
```

**Установить один параметр:**
```bash
python server/config_tool.py --set wifi_ssid=MyNetwork
```

**Загрузить конфигурацию из `server/config.json` или по явномму пути:**
```bash
python server/config_tool.py --upload
python server/config_tool.py --upload --file /path/to/config
```

**Сброс к значениям по умолчанию:**
```bash
python server/config_tool.py --reset
```

**Интерактивный режим:**
```bash
python server/config_tool.py --interactive
```

#### config.json - файл конфигурации

Файл `server/config.json` содержит параметры, которые будут загружены на устройство командой `--upload`. Поддерживаемые ключи:

| Ключ            | Описание                                          |
|-----------------|---------------------------------------------------|
| `wifi_ssid`     | Имя Wi-Fi сети                                    |
| `wifi_pass`     | Пароль Wi-Fi (при выводе маскируется как `***`)   |
| `server_url`    | Адрес сервера `host:port` (например, `192.168.1.100:5000`) |
| `ntp_server`    | Адрес NTP-сервера (например, `pool.ntp.org`)      |
| `gmt_offset`    | Смещение часового пояса в секундах (UTC+7 = 25200)|
| `daylight`      | Смещение летнего времени в секундах               |
| `save_interval` | Интервал записи в CSV, мс                         |
| `http_timeout`  | Таймаут HTTP-запроса, мс                          |
| `http_delay`    | Задержка перед повторной HTTP-попыткой, мс        |
| `wifi_attempts` | Максимум попыток подключения к Wi-Fi              |

Ключи, отсутствующие в файле, пропускаются. Неизвестные ключи вызывают предупреждение и также пропускаются.

Настройки в начале файла:

| Параметр      | Описание                          |
|---------------|-----------------------------------|
| `SERIAL_PORT` | COM-порт ESP32 (например, `COM5`) |
| `BAUD_RATE`   | Скорость (по умолчанию 115200)    |

### Структура БД

Оба скрипта используют одинаковую схему таблицы `temperatures`:

| Поле          | Тип     | Описание                  |
|---------------|---------|---------------------------|
| `id`          | INTEGER | Первичный ключ            |
| `timestamp`   | TEXT    | Дата и время записи       |
| `sensor_id`   | INTEGER | 0 - первый датчик, 1 - второй |
| `temperature` | REAL    | Температура в °C          |

### Валидация данных

- Значения `-127` (ошибка датчика DS18B20) игнорируются.
- Температуры вне диапазона -50°C..+100°C игнорируются.
- Дубликаты (одинаковые timestamp + sensor_id) не вставляются.

## Сборка и развёртывание бинарей

> **Важно:** PyInstaller не поддерживает кросс-компиляцию. Бинарь для Windows нужно
> собирать на Windows, для Linux - на Linux.

### Состав поставки

После сборки в `dist/` окажутся три standalone-бинаря:

| Файл / папка                    | Назначение                                               |
|---------------------------------|----------------------------------------------------------|
| `BodyTempMonitor-server(.exe)`  | HTTP-сервер (REST API + веб-дашборд + веб-конфиг)       |
| `BodyTempMonitor-cli(.exe)`     | CLI-утилита: `config` + `log`                            |
| `BodyTempMonitor-gui(.exe)`     | Десктоп-GUI на PySide6 (сервер + конфиг + логгер)       |
| `config.json`                   | Файл конфигурации - отредактируйте перед первым запуском |

Файлы, создаваемые автоматически рядом с бинарём при первом запуске:

| Файл                 | Создаётся                           | Назначение                            |
|----------------------|-------------------------------------|---------------------------------------|
| `sensor_data.db`     | `BodyTempMonitor-server` / `-gui`   | SQLite-база данных с показаниями      |
| `device_config.json` | `BodyTempMonitor-server` / `-gui`   | Желаемый конфиг устройства (веб-канал)|

Все три бинаря живут в одной папке `dist/` и при запуске оттуда используют
**одну и ту же** `sensor_data.db` и `device_config.json`.

### Зависимости

`requirements.txt` содержит runtime-зависимости: `flask`, `pyserial`, `PySide6`.
`requirements-build.txt` содержит `pyinstaller`.

> **Примечание:** `PySide6` - тяжёлая зависимость (~100 MB). Если GUI не нужен,
> удалите строку `PySide6` из `requirements.txt` перед установкой - это ускорит
> сборку `BodyTempMonitor-server` и `BodyTempMonitor-cli` и уменьшит размер venv.

### Сборка на Windows

```powershell
.\build.ps1
```

### Сборка на Linux

```bash
bash build.sh
```

Скрипты создают venv, устанавливают зависимости из `requirements.txt` и
`requirements-build.txt`, затем запускают все три spec-файла.

### Запуск бинарей

**Windows:**
```
dist\BodyTempMonitor-server.exe
dist\BodyTempMonitor-cli.exe config --show      # показать конфигурацию ESP32
dist\BodyTempMonitor-cli.exe config --upload    # загрузить config.json на устройство
dist\BodyTempMonitor-cli.exe log                # выгрузить CSV-журнал в БД
dist\BodyTempMonitor-cli.exe log --monitor      # мониторинг Serial в реальном времени
dist\BodyTempMonitor-gui.exe
```

**Linux:**
```bash
dist/BodyTempMonitor-server
dist/BodyTempMonitor-cli config --show
dist/BodyTempMonitor-cli log --monitor
dist/BodyTempMonitor-gui
```

### Онлайн-запуск (без сборки)

Прямые запуски Python-скриптов по-прежнему работают без сборки:

```bash
python server/server.py
python server/gui.py
python server/tool.py config --show
python server/tool.py log --monitor
```

### Замечания по BodyTempMonitor-gui (PySide6)

- **Крупный бинарь:** `BodyTempMonitor-gui(.exe)` весит значительно больше остальных, потому
  что содержит Qt-рантайм и все необходимые плагины.
- **Медленный старт onefile:** при каждом запуске Qt-библиотеки распаковываются во временную
  папку. Если это критично, замените `--onefile` на `--onedir` в `gui.spec`:
  ```
  # в gui.spec уберите a.binaries, a.datas из EXE и добавьте COLLECT(...)
  pyinstaller gui.spec --onedir --noconfirm
  ```
- **Qt-плагины:** если `BodyTempMonitor-gui` падает с ошибкой _"no Qt platform plugin could
  be initialized"_, раскомментируйте строку `collect_all('PySide6')` в `gui.spec` и
  пересоберите.

---

**Примечание:** Устройство предназначено только для образовательных и исследовательских целей. Не используйте его для реального медицинского мониторинга без соответствующей сертификации.
