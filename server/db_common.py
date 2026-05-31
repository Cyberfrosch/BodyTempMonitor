"""
db_common.py - Общая логика работы с базой данных для server.py и logger.py.

Инкапсулирует инициализацию, валидацию и вставку данных в классе Database.
"""

import sqlite3
from contextlib import closing
from datetime import datetime

from app_config import DATABASE

_CREATE_TABLE_SQL = """
    CREATE TABLE IF NOT EXISTS temperatures (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp   TEXT    NOT NULL,
        sensor_id   INTEGER NOT NULL,
        temperature REAL    NOT NULL
    );

    CREATE INDEX IF NOT EXISTS idx_timestamp ON temperatures(timestamp);

    CREATE TABLE IF NOT EXISTS notes (
        id        INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        note      TEXT NOT NULL
    );
"""

# Константы для валидации
MIN_VALID_TEMP     = -50.0   # Минимальная валидная температура (°C)
MAX_VALID_TEMP     = 100.0   # Максимальная валидная температура (°C)
INVALID_TEMP_VALUE = -127.0  # Значение ошибки датчика DS18B20


class Database:
    """Доступ к SQLite-базе данных: инициализация схемы, валидация и вставка записей."""

    def __init__(self, path: str = DATABASE) -> None:
        self.path = path

    # ------------------------------------------------------------------ утилиты

    @staticmethod
    def is_valid_temperature(temp: float) -> bool:
        """Проверяет корректность значения температуры (не код ошибки и не выход за диапазон)."""
        if temp == INVALID_TEMP_VALUE:
            return False
        return MIN_VALID_TEMP <= temp <= MAX_VALID_TEMP

    @staticmethod
    def unix_to_str(unix_timestamp: int) -> str:
        """Конвертирует Unix-timestamp в строку формата YYYY-MM-DD HH:MM:SS."""
        return datetime.fromtimestamp(unix_timestamp).strftime("%Y-%m-%d %H:%M:%S")

    # ------------------------------------------------------------------ схема

    def init_schema(self) -> None:
        """Инициализирует базу данных: создаёт таблицы и индексы при их отсутствии."""
        with closing(sqlite3.connect(self.path)) as conn:
            conn.executescript(_CREATE_TABLE_SQL)
            conn.commit()

    # ------------------------------------------------------------------ чтение

    def fetch_temperatures(self) -> list[dict]:
        """Возвращает все записи температуры в порядке убывания времени."""
        with closing(sqlite3.connect(self.path)) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT timestamp, sensor_id, temperature FROM temperatures ORDER BY timestamp DESC"
            )
            return [dict(row) for row in cursor.fetchall()]

    def fetch_notes(self, limit: int = 20) -> list[dict]:
        """Возвращает последние limit заметок в порядке убывания времени."""
        with closing(sqlite3.connect(self.path)) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT timestamp, note FROM notes ORDER BY timestamp DESC LIMIT ?", (limit,)
            )
            return [dict(row) for row in cursor.fetchall()]

    # ------------------------------------------------------------------ запись

    def _record_exists(self, conn: sqlite3.Connection, timestamp: str, sensor_id: int) -> bool:
        """Проверяет, существует ли запись с заданными timestamp и sensor_id."""
        cursor = conn.execute(
            "SELECT COUNT(*) FROM temperatures WHERE timestamp = ? AND sensor_id = ?",
            (timestamp, sensor_id),
        )
        return cursor.fetchone()[0] > 0

    def insert_temperature(self, timestamp: str, sensor_id: int, temperature: float) -> bool:
        """
        Вставляет запись температуры, если она корректна и не является дубликатом.
        Возвращает True при вставке, False при пропуске.
        """
        with closing(sqlite3.connect(self.path)) as conn:
            if not self.is_valid_temperature(temperature):
                return False
            if self._record_exists(conn, timestamp, sensor_id):
                return False
            conn.execute(
                "INSERT INTO temperatures (timestamp, sensor_id, temperature) VALUES (?, ?, ?)",
                (timestamp, sensor_id, temperature),
            )
            conn.commit()
            return True

    def insert_batch(self, records: list[tuple]) -> tuple[int, int, int]:
        """
        Вставляет несколько записей температуры.

        Аргументы:
            records: список кортежей (timestamp, sensor_id, temperature)

        Возвращает:
            Кортеж (inserted_count, skipped_duplicates, skipped_invalid)
        """
        inserted = skipped_duplicates = skipped_invalid = 0

        with closing(sqlite3.connect(self.path)) as conn:
            for timestamp, sensor_id, temperature in records:
                if not self.is_valid_temperature(temperature):
                    skipped_invalid += 1
                    continue
                if self._record_exists(conn, timestamp, sensor_id):
                    skipped_duplicates += 1
                    continue
                conn.execute(
                    "INSERT INTO temperatures (timestamp, sensor_id, temperature) VALUES (?, ?, ?)",
                    (timestamp, sensor_id, temperature),
                )
                inserted += 1
            conn.commit()

        return inserted, skipped_duplicates, skipped_invalid

    def insert_note(self, note: str) -> None:
        """Добавляет заметку с текущим временем."""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with closing(sqlite3.connect(self.path)) as conn:
            conn.execute("INSERT INTO notes (timestamp, note) VALUES (?, ?)", (now, note))
            conn.commit()
