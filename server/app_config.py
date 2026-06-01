"""
app_config.py - Единый загрузчик настроек из config.json.

Структура (новый формат):
  {
    "host":   { "serial_port": "COM5", "baud_rate": 115200,
                "server_host": "0.0.0.0", "server_port": 5000,
                "database": "sensor_data.db" },
    "device": { "wifi_ssid": "", "wifi_pass": "", "server_url": "",
                "ntp_server": "pool.ntp.org", "gmt_offset": 25200, ... }
  }

Обратная совместимость: плоский config.json (без секций host/device)
трактуется как секция device; host-настройки берутся из дефолтов.
"""

import hashlib
import json
import os
import threading
from typing import Any

from app_paths import external_path
from config_schema import BINDING_KEYS, NON_BINDING_KEYS, NUMERIC_KEYS

CONFIG_FILE = external_path("config.json")

_HOST_DEFAULTS: dict[str, Any] = {
    "serial_port": "COM5",
    "baud_rate":   115200,
    "server_host": "0.0.0.0",
    "server_port": 5000,
    "database":    "sensor_data.db",
}

_DEVICE_DEFAULTS: dict[str, Any] = {
    "wifi_ssid":     "",
    "wifi_pass":     "",
    "server_url":    "",
    "ntp_server":    "pool.ntp.org",
    "gmt_offset":    25200,
    "daylight":      0,
    "save_interval": 10000,
    "http_timeout":  5000,
    "http_delay":    1000,
    "wifi_attempts": 20,
}


def _load_raw() -> dict[str, Any]:
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


def _is_sectioned(raw: dict) -> bool:
    return "host" in raw or "device" in raw


class AppConfig:
    """Синглтон-загрузчик config.json; потокобезопасная запись через save_device_updates."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._host:   dict[str, Any] = {}
        self._device: dict[str, Any] = {}
        self._reload()

    def _reload(self) -> None:
        """Перечитывает config.json без захвата лока (вызывать уже под локом или из __init__)."""
        raw      = _load_raw()
        sectioned = _is_sectioned(raw)
        host_raw   = raw.get("host",   {}) if sectioned else {}
        device_raw = raw.get("device", {}) if sectioned else raw
        self._host   = {**_HOST_DEFAULTS,   **host_raw}
        self._device = {**_DEVICE_DEFAULTS, **device_raw}

    # ------------------------------------------------------------------ host

    @property
    def serial_port(self) -> str:
        return str(self._host["serial_port"])

    @property
    def baud_rate(self) -> int:
        return int(self._host["baud_rate"])

    @property
    def server_host(self) -> str:
        return str(self._host["server_host"])

    @property
    def server_port(self) -> int:
        return int(self._host["server_port"])

    @property
    def database(self) -> str:
        db = str(self._host["database"])
        return db if os.path.isabs(db) else external_path(db)

    # ------------------------------------------------------------------ device

    def device_config(self) -> dict[str, Any]:
        """Полный device-конфиг; для Serial --upload (включает связочные ключи)."""
        return dict(self._device)

    def non_binding_config(self) -> dict[str, Any]:
        """Только несвязочные ключи; источник для ETag и веб-канала."""
        return {k: self._device[k] for k in sorted(NON_BINDING_KEYS) if k in self._device}

    # ------------------------------------------------------------------ ETag

    def compute_etag(self) -> str:
        """SHA-256 несвязочного конфига, первые 16 hex-символов.

        Хэш стабилен: ключи сортируются, поэтому порядок вставки не влияет.
        Меняется при изменении любого несвязочного ключа; связочные на хэш не влияют.
        """
        nb    = self.non_binding_config()
        parts = [f"{k}={nb.get(k, '')}" for k in sorted(NON_BINDING_KEYS)]
        return hashlib.sha256("\n".join(parts).encode()).hexdigest()[:16]

    def as_text(self) -> str:
        """Несвязочный конфиг в формате key=value\\n для GET /api/config (прошивка)."""
        nb    = self.non_binding_config()
        lines = [f"{k}={nb.get(k, '')}" for k in sorted(NON_BINDING_KEYS)]
        lines.append(f"etag={self.compute_etag()}")
        return "\n".join(lines) + "\n"

    # ------------------------------------------------------------------ write

    def save_from_device(self, updates: dict[str, Any]) -> None:
        """Сохраняет полный конфиг, прочитанный с платы через Serial.

        Отличие от save_device_updates: сохраняет связочные ключи (wifi_ssid,
        server_url), но НИКОГДА не перезаписывает wifi_pass маскированным '***'.
        Числовые ключи приводятся к int (с платы приходят строками).
        """
        to_save: dict[str, Any] = {}
        for key, val in updates.items():
            if key == "wifi_pass":
                continue  # device always masks password; never overwrite config.json from readout
            if key in NUMERIC_KEYS:
                try:
                    to_save[key] = int(val)
                except (ValueError, TypeError):
                    to_save[key] = val
            else:
                to_save[key] = str(val)

        if not to_save:
            return

        with self._lock:
            raw = _load_raw()
            if _is_sectioned(raw):
                raw.setdefault("device", {}).update(to_save)
            else:
                raw.update(to_save)
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(raw, f, indent=2, ensure_ascii=False)
            self._reload()

    def save_device_updates(self, updates: dict[str, Any]) -> tuple[bool, list[str]]:
        """Сохраняет несвязочные ключи в config.json; связочные отклоняет.

        Потокобезопасно (файловая операция под локом).
        Возвращает (applied, rejected_keys).
        """
        rejected: list[str] = []
        to_save:  dict[str, Any] = {}

        for key, val in updates.items():
            if key in BINDING_KEYS:
                rejected.append(key)
            elif key in NON_BINDING_KEYS:
                to_save[key] = val
            # неизвестные ключи молча игнорируем

        if not to_save:
            return False, rejected

        with self._lock:
            raw = _load_raw()
            if _is_sectioned(raw):
                raw.setdefault("device", {}).update(to_save)
            else:
                raw.update(to_save)
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(raw, f, indent=2, ensure_ascii=False)
            self._reload()

        return True, rejected


# Синглтон - загружается один раз при импорте модуля
cfg = AppConfig()

# Алиасы для прямого импорта в других модулях (значения фиксируются при старте)
SERIAL_PORT = cfg.serial_port
BAUD_RATE   = cfg.baud_rate
SERVER_HOST = cfg.server_host
SERVER_PORT = cfg.server_port
DATABASE    = cfg.database
