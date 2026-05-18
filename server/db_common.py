"""
db_common.py — Common database logic for server and logger.

Shared functions for database initialization, data validation and insertion.
"""

import sqlite3
from contextlib import closing
from datetime import datetime

DATABASE = "sensor_data.db"

CREATE_TABLE_SQL = """
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
MIN_VALID_TEMP = -50.0  # Минимальная валидная температура (°C)
MAX_VALID_TEMP = 100.0  # Максимальная валидная температура (°C)
INVALID_TEMP_VALUE = -127.0  # Значение ошибки датчика DS18B20


def init_db(database: str = DATABASE) -> None:
    """Initialize database with required tables and indexes."""
    with closing(sqlite3.connect(database)) as conn:
        conn.executescript(CREATE_TABLE_SQL)
        conn.commit()


def is_valid_temperature(temp: float) -> bool:
    """Check if temperature value is valid (not error code or out of range)."""
    if temp == INVALID_TEMP_VALUE:
        return False
    if temp < MIN_VALID_TEMP or temp > MAX_VALID_TEMP:
        return False
    return True


def unix_to_str(unix_timestamp: int) -> str:
    """Convert Unix timestamp to string format YYYY-MM-DD HH:MM:SS."""
    return datetime.fromtimestamp(unix_timestamp).strftime("%Y-%m-%d %H:%M:%S")


def record_exists(conn: sqlite3.Connection, timestamp: str, sensor_id: int) -> bool:
    """Check if record with given timestamp and sensor_id already exists."""
    cursor = conn.execute(
        "SELECT COUNT(*) FROM temperatures WHERE timestamp = ? AND sensor_id = ?",
        (timestamp, sensor_id)
    )
    return cursor.fetchone()[0] > 0


def insert_temperature(conn: sqlite3.Connection, timestamp: str, sensor_id: int, temperature: float) -> bool:
    """
    Insert temperature record if valid and not duplicate.
    Returns True if inserted, False if skipped.
    """
    if not is_valid_temperature(temperature):
        return False

    if record_exists(conn, timestamp, sensor_id):
        return False

    conn.execute(
        "INSERT INTO temperatures (timestamp, sensor_id, temperature) VALUES (?, ?, ?)",
        (timestamp, sensor_id, temperature)
    )
    return True


def insert_temperatures_batch(conn: sqlite3.Connection, records: list[tuple]) -> tuple[int, int, int]:
    """
    Insert multiple temperature records.

    Args:
        records: List of tuples (timestamp, sensor_id, temperature)

    Returns:
        Tuple of (inserted_count, skipped_duplicates, skipped_invalid)
    """
    inserted = 0
    skipped_duplicates = 0
    skipped_invalid = 0

    for timestamp, sensor_id, temperature in records:
        if not is_valid_temperature(temperature):
            skipped_invalid += 1
            continue

        if record_exists(conn, timestamp, sensor_id):
            skipped_duplicates += 1
            continue

        conn.execute(
            "INSERT INTO temperatures (timestamp, sensor_id, temperature) VALUES (?, ?, ?)",
            (timestamp, sensor_id, temperature)
        )
        inserted += 1

    conn.commit()
    return inserted, skipped_duplicates, skipped_invalid
