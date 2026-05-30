"""
logger.py — Загрузка CSV-журнала с ESP32 через Serial и сохранение в SQLite.

Отправляет команду "download" в Serial Monitor, считывает CSV между
маркерами BEGIN/END FILE и сохраняет данные в локальную БД.

Формат CSV: unixtime,temp0,temp1 (абсолютные метки времени от RTC)

Usage:
  python logger.py            # download and save to DB
  python logger.py --clear    # wipe CSV on ESP32 (no download)
  python logger.py --monitor  # real-time monitoring of Serial output
"""

import argparse
import csv
import time
from io import StringIO

from db_common import DATABASE, Database
from serial_device import BAUD_RATE, SERIAL_PORT, SerialDevice

KNOWN_HEADERS = {"unixtime,temp0,temp1", "reltime,temp0,temp1"}


class LogDownloader:
    """Выгрузка CSV-журнала с ESP32 и сохранение данных в базу данных."""

    def __init__(self, device: SerialDevice, db: Database) -> None:
        self._dev = device
        self._db  = db

    @staticmethod
    def is_unix_timestamp(value: str) -> bool:
        """Проверяет, похоже ли значение на Unix-timestamp (10 цифр, год ≥ 2000)."""
        try:
            ts = int(value)
            return ts > 946684800 and len(value) >= 10  # 2000-01-01
        except ValueError:
            return False

    @staticmethod
    def rows_to_db(rows: list[list[str]]) -> list[tuple]:
        """Преобразует строки с Unix-timestamps в кортежи для вставки в БД."""
        result = []
        for row in rows:
            try:
                if len(row) >= 3:
                    unix_ts = int(row[0])
                    ts = Database.unix_to_str(unix_ts)
                    result.append((ts, 0, float(row[1])))
                    result.append((ts, 1, float(row[2])))
            except (ValueError, IndexError):
                continue
        return result

    def fetch_csv(self) -> list[str]:
        """Отправляет 'download' и возвращает строки между маркерами BEGIN/END FILE."""
        self._dev.send("download")
        time.sleep(1)

        lines, capturing = [], False
        while True:
            line = self._dev.readline()
            if not capturing and line == "--- BEGIN FILE ---":
                capturing = True
            elif capturing and line == "--- END FILE ---":
                break
            elif capturing:
                lines.append(line)
        return lines

    def clear(self) -> None:
        """Отправляет команду 'clear' на ESP32 для очистки CSV-журнала."""
        self._dev.send("clear")
        time.sleep(1)
        response = self._dev.read_available().strip()
        print(f"ESP32: {response}" if response else "ESP32: no response")

    def process(self, all_rows: list[list[str]]) -> None:
        """Обрабатывает CSV-данные с Unix-timestamps от RTC и сохраняет в БД."""
        rows = self.rows_to_db(all_rows)
        if not rows:
            print("No valid data found.")
            return

        inserted, skipped_dup, skipped_inv = self._db.insert_batch(rows)

        if inserted > 0:
            print(f"Inserted {inserted} new records.")
        if skipped_dup > 0:
            print(f"Skipped {skipped_dup} duplicate records.")
        if skipped_inv > 0:
            print(f"Skipped {skipped_inv} invalid records (error values).")
        if inserted == 0 and skipped_dup == 0 and skipped_inv == 0:
            print("No data to process.")


class SerialMonitor:
    """Мониторинг вывода Serial в реальном времени с сохранением данных в БД."""

    def __init__(self, device: SerialDevice, db: Database) -> None:
        self._dev = device
        self._db  = db

    def _handle_logged_line(self, line: str) -> None:
        """Разбирает строку «Logged: …» и сохраняет показания датчиков в БД.

        Сама строка уже выведена потоковой печатью; здесь только запись в БД
        и вывод подтверждения/предупреждения.
        """
        if not line.startswith("Logged: "):
            return
        try:
            # Парсим "Logged: 1735123456, 36.50, 37.20"
            parts = line.replace("Logged: ", "").split(", ")
            if len(parts) == 3:
                unix_ts   = int(parts[0])
                temp0     = float(parts[1])
                temp1     = float(parts[2])
                timestamp = Database.unix_to_str(unix_ts)

                inserted0 = self._db.insert_temperature(timestamp, 0, temp0)
                inserted1 = self._db.insert_temperature(timestamp, 1, temp1)

                if inserted0 and inserted1:
                    print(f"  → Saved to DB: [{timestamp}] temp0={temp0}°C, temp1={temp1}°C")
                elif not inserted0 and not inserted1:
                    print(f"  → Skipped (duplicate or invalid)")
        except (ValueError, IndexError):
            pass

    def run(self) -> None:
        """Запускает потоковый мониторинг Serial. Остановка — Ctrl+C.

        Байты печатаются сразу по мере поступления, не дожидаясь символа \\n,
        поэтому частичные строки (прогресс-точки Wi-Fi) видны в реальном времени.
        Параллельно завершённые строки «Logged: …» сохраняются в БД.
        """
        print(f"Monitoring Serial port {self._dev.port} at {self._dev.baud} baud...")
        print("Press Ctrl+C to stop.\n")

        buf = ""
        try:
            while True:
                chunk = self._dev.read_available()
                if not chunk:
                    time.sleep(0.02)  # уступаем CPU при отсутствии данных
                    continue

                # Печатаем немедленно: \r отбрасываем, чтобы \r\n не ломал вывод
                print(chunk.replace("\r", ""), end="", flush=True)

                # Накапливаем в буфере для построчного разбора
                buf += chunk

                # Извлекаем завершённые строки (по \n) и обрабатываем каждую
                while "\n" in buf:
                    line, buf = buf.split("\n", 1)
                    self._handle_logged_line(line.strip())

        except KeyboardInterrupt:
            print("\n\nMonitoring stopped.")


def _add_log_args(p: argparse.ArgumentParser) -> None:
    """Регистрирует аргументы команды загрузки журнала в переданном парсере."""
    p.add_argument("--clear",   action="store_true", help="Wipe CSV on ESP32 without downloading")
    p.add_argument("--monitor", action="store_true", help="Monitor Serial output in real-time")


def add_log_subparser(subparsers) -> None:
    """Добавляет подпарсер 'log' в составной парсер (tool.py)."""
    p = subparsers.add_parser(
        "log",
        description="Download ESP32 CSV log to SQLite.",
        epilog=(
            "examples:\n"
            "  tool log            # download CSV log and save to DB\n"
            "  tool log --clear    # wipe CSV on ESP32\n"
            "  tool log --monitor  # monitor Serial output in real-time\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        help="Download CSV log or monitor Serial output",
    )
    _add_log_args(p)


def run_log(args: argparse.Namespace) -> None:
    """Выполняет подкоманду 'log' с разобранными аргументами."""
    db = Database(DATABASE)
    db.init_schema()

    if args.monitor:
        # serial_timeout=1 — readline возвращает управление каждую секунду при отсутствии данных
        with SerialDevice(SERIAL_PORT, BAUD_RATE, serial_timeout=1) as dev:
            SerialMonitor(dev, db).run()
        return

    with SerialDevice(SERIAL_PORT, BAUD_RATE) as dev:
        downloader = LogDownloader(dev, db)

        if args.clear:
            print("Clearing CSV on ESP32...")
            downloader.clear()
            return

        lines = downloader.fetch_csv()
    # порт закрыт; downloader._db по-прежнему доступен для process()

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

    if not LogDownloader.is_unix_timestamp(all_rows[0][0]):
        print("Warning: Data doesn't contain Unix timestamps. RTC may not be working.")
        print("First timestamp:", all_rows[0][0])
        return

    downloader.process(all_rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Download ESP32 CSV log to SQLite.")
    _add_log_args(parser)
    args = parser.parse_args()
    run_log(args)


if __name__ == "__main__":
    main()
