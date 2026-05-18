"""
logger.py — Download CSV log from ESP32 via Serial and save to SQLite.

Sends the "download" command to Serial Monitor, reads CSV between
BEGIN/END FILE markers and saves to a local DB.

CSV format: unixtime,temp0,temp1 (absolute timestamps from RTC)

Usage:
  python logger.py            # download and save to DB
  python logger.py --clear    # wipe CSV on ESP32 (no download)
"""

import argparse
import csv
import sqlite3
import time
from contextlib import closing
from datetime import datetime
from io import StringIO

import serial

# ---------- Settings ----------
SERIAL_PORT = "COM5"
BAUD_RATE   = 115200
DATABASE    = "sensor_data.db"

CREATE_TABLE_SQL = """
    CREATE TABLE IF NOT EXISTS temperatures (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp   TEXT    NOT NULL,
        sensor_id   INTEGER NOT NULL,
        temperature REAL    NOT NULL,
        UNIQUE(timestamp, sensor_id)
    )
"""

KNOWN_HEADERS = {"unixtime,temp0,temp1", "reltime,temp0,temp1"}


def init_db(conn: sqlite3.Connection) -> None:
    conn.execute(CREATE_TABLE_SQL)
    conn.commit()


def unix_to_str(ut: int) -> str:
    return datetime.fromtimestamp(ut).strftime("%Y-%m-%d %H:%M:%S")


def is_unix_timestamp(value: str) -> bool:
    """Check if value looks like a Unix timestamp (10 digits, year 2000+)."""
    try:
        ts = int(value)
        return ts > 946684800 and len(value) >= 10  # 2000-01-01
    except ValueError:
        return False


def fetch_csv(ser: serial.Serial) -> list[str]:
    """Sends 'download' and returns lines between BEGIN/END FILE markers."""
    ser.write(b"download\r\n")
    time.sleep(1)

    lines, capturing = [], False
    while True:
        line = ser.readline().decode("utf-8", errors="ignore").strip()
        if not capturing and line == "--- BEGIN FILE ---":
            capturing = True
        elif capturing and line == "--- END FILE ---":
            break
        elif capturing:
            lines.append(line)
    return lines


def clear_csv(ser: serial.Serial) -> None:
    """Sends 'clear' command to ESP32 to wipe the CSV log."""
    ser.write(b"clear\r\n")
    time.sleep(1)
    response = ser.read(ser.in_waiting).decode("utf-8", errors="ignore").strip()
    print(f"ESP32: {response}" if response else "ESP32: no response")


def rows_to_db(rows: list[list[str]]) -> list[tuple]:
    """Converts rows with Unix timestamps to DB tuples."""
    result = []
    for row in rows:
        try:
            if len(row) >= 3:
                unix_ts = int(row[0])
                ts = unix_to_str(unix_ts)
                result.append((ts, 0, float(row[1]), unix_ts))
                result.append((ts, 1, float(row[2]), unix_ts))
        except (ValueError, IndexError):
            continue
    return result


def process_data(all_rows: list[list[str]], conn: sqlite3.Connection) -> None:
    """Process CSV with Unix timestamps from RTC."""
    rows = rows_to_db(all_rows)
    if not rows:
        print("No valid data found.")
        return

    inserted = 0
    skipped = 0
    
    for row in rows:
        try:
            # Проверяем существование по timestamp, sensor_id и unix_timestamp
            cursor = conn.execute(
                "SELECT COUNT(*) FROM temperatures WHERE timestamp = ? AND sensor_id = ?",
                (row[0], row[1])
            )
            if cursor.fetchone()[0] > 0:
                skipped += 1
                continue
                
            conn.execute(
                "INSERT INTO temperatures (timestamp, sensor_id, temperature) VALUES (?, ?, ?)",
                (row[0], row[1], row[2])
            )
            inserted += 1
        except sqlite3.IntegrityError:
            skipped += 1
    
    conn.commit()
    
    if inserted > 0:
        print(f"Inserted {inserted} new records.")
    if skipped > 0:
        print(f"Skipped {skipped} duplicate records.")
    if inserted == 0 and skipped == 0:
        print("No data to process.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Download ESP32 CSV log to SQLite.")
    parser.add_argument("--clear", action="store_true", help="Wipe CSV on ESP32 without downloading")
    args = parser.parse_args()

    if args.clear:
        with serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=2) as ser:
            time.sleep(2)
            print("Clearing CSV on ESP32...")
            clear_csv(ser)
        return

    with closing(sqlite3.connect(DATABASE)) as conn:
        init_db(conn)

        with serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=2) as ser:
            time.sleep(2)
            lines = fetch_csv(ser)

        if not lines:
            print("No data received.")
            return

        reader = csv.reader(StringIO("\n".join(lines)))
        header = next(reader, None)
        if header is None:
            print("File is empty.")
            return

        all_rows = [
            row for row in reader
            if ",".join(row).strip() not in KNOWN_HEADERS and row
        ]

        if ",".join(header).strip() not in KNOWN_HEADERS:
            all_rows.insert(0, header)

        if not all_rows:
            print("No data found.")
            return

        if not is_unix_timestamp(all_rows[0][0]):
            print("Warning: Data doesn't contain Unix timestamps. RTC may not be working.")
            print("First timestamp:", all_rows[0][0])
            return

        process_data(all_rows, conn)


if __name__ == "__main__":
    main()
