"""
device_config.py - Хранилище «желаемой» конфигурации устройства (веб-канал).

Хранит редактируемые параметры и счётчик ревизий в device_config.json рядом
с базой данных.  Отличается от config.json (источник Serial/GUI-загрузки):
device_config.json управляется через веб-форму и доставляется устройству
событийно - только когда revision изменилась с момента последней синхронизации.

Связочные параметры (wifi_ssid, wifi_pass, server_url) изменяются ТОЛЬКО через
Serial/десктоп-GUI и не входят в allow-list этого модуля.
"""

import json
import os
from typing import Any

from app_paths import external_path

DEVICE_CONFIG_FILE = external_path("device_config.json")

# Ключи, разрешённые к изменению через веб (allow-list).
# Проверяется и на сервере, и в прошивке.
WEB_EDITABLE_KEYS: list[str] = [
    "ntp_server",
    "gmt_offset",
    "daylight",
    "save_interval",
    "http_timeout",
    "http_delay",
    "wifi_attempts",
]

# Связочные параметры - явно запрещены.
_BINDING_KEYS: frozenset[str] = frozenset({"wifi_ssid", "wifi_pass", "server_url"})

_DEFAULTS: dict[str, Any] = {
    "ntp_server":    "pool.ntp.org",
    "gmt_offset":    25200,   # UTC+7 в секундах
    "daylight":      0,
    "save_interval": 10000,   # мс
    "http_timeout":  5000,    # мс
    "http_delay":    1000,    # мс
    "wifi_attempts": 20,
    "revision":      0,
}


class DeviceConfig:
    """Персистентное хранилище желаемой конфигурации устройства для веб-канала."""

    def __init__(self, path: str = DEVICE_CONFIG_FILE) -> None:
        self._path = path
        self._data: dict[str, Any] = {}
        self._load()

    # ------------------------------------------------------------------ I/O

    def _load(self) -> None:
        if os.path.exists(self._path):
            try:
                with open(self._path, "r", encoding="utf-8") as f:
                    self._data = json.load(f)
                return
            except (json.JSONDecodeError, OSError):
                pass
        self._data = dict(_DEFAULTS)
        self._save()

    def _save(self) -> None:
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2, ensure_ascii=False)

    # ------------------------------------------------------------------ доступ

    @property
    def revision(self) -> int:
        """Текущая ревизия конфигурации (инкрементируется при каждом изменении)."""
        return int(self._data.get("revision", 0))

    def get_all(self) -> dict[str, Any]:
        """Возвращает все редактируемые ключи и revision."""
        result = {k: self._data.get(k, _DEFAULTS.get(k, "")) for k in WEB_EDITABLE_KEYS}
        result["revision"] = self.revision
        return result

    def as_text(self) -> str:
        """Конфиг в формате key=value\\n - именно такой формат парсит прошивка."""
        lines = [f"{k}={self._data.get(k, _DEFAULTS.get(k, ''))}" for k in WEB_EDITABLE_KEYS]
        lines.append(f"revision={self.revision}")
        return "\n".join(lines) + "\n"

    # ------------------------------------------------------------------ изменение

    def update(self, updates: dict[str, Any]) -> tuple[bool, list[str]]:
        """Обновляет редактируемые ключи и инкрементирует revision.

        Возвращает (applied, rejected_keys).
        Связочные ключи отклоняются; неизвестные ключи игнорируются.
        """
        rejected: list[str] = []
        applied = False

        for key, val in updates.items():
            if key in _BINDING_KEYS:
                rejected.append(key)
                continue
            if key not in WEB_EDITABLE_KEYS:
                continue
            self._data[key] = val
            applied = True

        if applied:
            self._data["revision"] = self.revision + 1
            self._save()

        return applied, rejected
