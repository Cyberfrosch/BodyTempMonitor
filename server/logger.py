"""
logger.py — Download CSV log from ESP32 via Serial and save to SQLite.

Sends the "download" command to Serial Monitor, reads CSV between
BEGIN/END FILE markers, splits into sessions by RESET marker and
saves to a local DB with real-time anchoring.

Supported CSV formats (may be mixed in one file):
  - old: unixtime,temperature    (1 sensor, reltime)
  - new: reltime,temp0,temp1     (2 sensors, reltime)

Usage:
  python logger.py            # download and save to DB
  python logger.py --clear    # wipe CSV on ESP32 (no download)
"""

import argparse
import csv
import sqlite3
import time
from contextlib import closing
from datetime import datetime, timedelta
from io import StringIO

import serial

# ---------- Settings ----------
SERIAL_PORT = "COM5"
BAUD_RATE   = 115200
DATABASE    = "sensor_data_local.db"

CREATE_TABLE_SQL = """
    CREATE TABLE IF NOT EXISTS temperatures (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp   TEXT    NOT NULL,
        sensor_id   INTEGER NOT NULL,
        temperature REAL    NOT NULL
    )
"""

KNOWN_HEADERS = {"unixtime,temperature", "reltime,temp0,temp1"}


def init_db(conn: sqlite3.Connection) -> None:
    conn.execute(CREATE_TABLE_SQL)
    conn.commit()


def unix_to_str(ut: int) -> str:
    return datetime.fromtimestamp(ut).strftime("%Y-%m-%d %H:%M:%S")


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


def parse_sessions(rows: list[list[str]]) -> list[list[list[str]]]:
    """Splits CSV rows into sessions by RESET marker."""
    sessions, current = [], []
    for row in rows:
        if row[0].strip() == "RESET":
            if current:
                sessions.append(current)
                current = []
        else:
            current.append(row)
    if current:
        sessions.append(current)
    return sessions


def session_duration(session: list[list[str]]) -> int:
    """Returns last reltime value of a session in seconds."""
    for row in reversed(session):
        try:
            return int(row[0])
        except (ValueError, IndexError):
            continue
    return 0


def ask_start_time(session_idx: int, total: int, now: datetime) -> tuple[datetime | None, bool]:
    """Asks the user for the session start time. Enter = current time.
    Returns (datetime, pressed_enter).
    """
    if session_idx == total - 1:
        try:
            uptime = int(input("ESP32 uptime in seconds (0 to enter date manually): "))
        except ValueError:
            uptime = 0
        if uptime > 0:
            return now - timedelta(seconds=uptime), False

    raw = input(f"Session start date/time (YYYY-MM-DD HH:MM:SS) [Enter = {now.strftime('%Y-%m-%d %H:%M:%S')}]: ").strip()
    if not raw:
        return now, True
    try:
        return datetime.strptime(raw, "%Y-%m-%d %H:%M:%S"), False
    except ValueError:
        print("Invalid format, session skipped.")
        return None, False


def rows_to_db(session: list[list[str]], start_unix: int) -> list[tuple]:
    """Converts one session's rows to DB tuples, handles 2- and 3-column formats."""
    result = []
    for row in session:
        try:
            ts = unix_to_str(start_unix + int(row[0]))
            if len(row) >= 3:
                result.append((ts, 0, float(row[1])))
                result.append((ts, 1, float(row[2])))
            elif len(row) == 2:
                result.append((ts, 0, float(row[1])))
        except (ValueError, IndexError):
            continue
    return result


def process_relative(all_rows: list[list[str]], conn: sqlite3.Connection) -> None:
    sessions = parse_sessions(all_rows)
    if not sessions:
        print("No valid data found.")
        return

    now = datetime.now()
    print(f"Current PC time: {now.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Total sessions: {len(sessions)}")

    rows = []
    auto_start: datetime | None = None
    for idx, session in enumerate(sessions):
        print(f"\nSession {idx + 1}/{len(sessions)} — {len(session)} records")

        if auto_start is not None:
            start = auto_start
            print(f"Auto start time: {start.strftime('%Y-%m-%d %H:%M:%S')}")
        else:
            start, pressed_enter = ask_start_time(idx, len(sessions), now)
            if start is None:
                continue
            if pressed_enter:
                total_remaining = sum(session_duration(s) for s in sessions[idx:])
                start = now - timedelta(seconds=total_remaining)
                auto_start = start

        rows += rows_to_db(session, int(start.timestamp()))

        if auto_start is not None:
            auto_start = start + timedelta(seconds=session_duration(session))

    conn.executemany(
        "INSERT INTO temperatures (timestamp, sensor_id, temperature) VALUES (?, ?, ?)",
        rows,
    )
    conn.commit()
    print(f"\nInserted {len(rows)} records.")


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

        process_relative(all_rows, conn)


if __name__ == "__main__":
    main()
