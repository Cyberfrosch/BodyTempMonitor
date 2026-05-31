"""
config_schema.py - Метаданные ключей конфигурации устройства.

Единый источник для:
  CONFIG_KEYS      - полный упорядоченный список ключей устройства
  BINDING_KEYS     - связочные (только Serial/GUI; веб не меняет)
  NON_BINDING_KEYS - несвязочные (редактируются через веб и Serial)
  NUMERIC_KEYS     - хранятся как int в config.json
  CONFIG_LABELS    - краткие русские подписи для UI

Импортировать только из этого модуля; не дублировать определения.
"""

CONFIG_KEYS: list[str] = [
    "wifi_ssid",
    "wifi_pass",
    "server_url",
    "ntp_server",
    "gmt_offset",
    "daylight",
    "save_interval",
    "http_timeout",
    "http_delay",
    "wifi_attempts",
]

BINDING_KEYS: frozenset[str] = frozenset({"wifi_ssid", "wifi_pass", "server_url"})

NON_BINDING_KEYS: frozenset[str] = frozenset({
    "ntp_server", "gmt_offset", "daylight",
    "save_interval", "http_timeout", "http_delay", "wifi_attempts",
})

# Числовые ключи приводятся к int при записи в config.json (значения с платы — строки).
NUMERIC_KEYS: frozenset[str] = frozenset({
    "gmt_offset", "daylight", "save_interval",
    "http_timeout", "http_delay", "wifi_attempts",
})

def normalize_server_addr(value: str) -> str:
    """Нормализует адрес сервера к формату ``host:port``.

    Принимает как ``host:port``, так и полный URL (срезает схему и путь).
    При отсутствии порта добавляет ``:5000`` (дефолтный порт сервера).

    Raises:
        ValueError: если после нормализации адрес оказался пустым.

    Examples::

        normalize_server_addr("192.168.0.193:5000")              # → "192.168.0.193:5000"
        normalize_server_addr("192.168.0.193")                   # → "192.168.0.193:5000"
        normalize_server_addr("http://192.168.0.193:5000/api/data") # → "192.168.0.193:5000"
    """
    s = value.strip()
    for scheme in ("https://", "http://"):
        if s.lower().startswith(scheme):
            s = s[len(scheme):]
            break
    slash = s.find("/")
    if slash >= 0:
        s = s[:slash]
    s = s.strip()
    if not s:
        raise ValueError(f"Пустой адрес сервера: {value!r}")
    if ":" not in s:
        s = f"{s}:5000"
    return s


CONFIG_LABELS: dict[str, str] = {
    "wifi_ssid":     "Имя Wi-Fi сети",
    "wifi_pass":     "Пароль Wi-Fi",
    "server_url":    "Адрес сервера (IP:порт)",
    "ntp_server":    "NTP-сервер",
    "gmt_offset":    "Смещение времени, UTC (сек)",
    "daylight":      "Летнее время (сек)",
    "save_interval": "Интервал записи (мс)",
    "http_timeout":  "Таймаут HTTP (мс)",
    "http_delay":    "Задержка повтора HTTP (мс)",
    "wifi_attempts": "Попыток подключения Wi-Fi",
}
