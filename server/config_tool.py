"""
config_tool.py — Управление конфигурацией ESP32 через Serial.

ESP32 хранит конфигурацию в NVS (Preferences). Утилита предоставляет
CLI-интерфейс для чтения и записи параметров через Serial-команды.

Usage:
  python config_tool.py                            # show current config
  python config_tool.py --show                     # show current config
  python config_tool.py --set key=value            # set a config key
  python config_tool.py --reset                    # reset to defaults
  python config_tool.py --interactive              # interactive mode
  python config_tool.py --upload                   # upload from config.json
  python config_tool.py --upload --file my.json    # upload from custom file
  python config_tool.py --baud 115200              # set custom baud rate
"""

import argparse
import json
import os
import time
import serial

SERIAL_PORT = "COM5"
BAUD_RATE   = 115200
CONFIG_FILE = os.path.join(os.path.dirname(__file__), "config.json")

CONFIG_KEYS = [
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


def send_command(ser: serial.Serial, cmd: str, wait: float = 1.0) -> str:
    """Отправляет команду и возвращает ответ."""
    ser.write((cmd + "\r\n").encode())
    time.sleep(wait)
    response = ser.read(ser.in_waiting).decode("utf-8", errors="ignore")
    return response.strip()


def wait_for_config_block(ser: serial.Serial, start_marker: str, end_marker: str, timeout: float = 10.0) -> str:
    """Ждет start_marker, затем читает все до end_marker включительно."""
    ser.timeout = timeout
    response = ""
    start_time = time.time()

    while True:
        if time.time() - start_time > timeout:
            raise TimeoutError("Timeout waiting for block start")
        chunk = ser.read(1).decode("utf-8", errors="ignore")
        response += chunk
        if start_marker in response:
            _, _, after = response.partition(start_marker)
            break

    block = after
    start_time = time.time()
    while True:
        if time.time() - start_time > timeout:
            raise TimeoutError("Timeout waiting for block end")
        chunk = ser.read(1).decode("utf-8", errors="ignore")
        block += chunk
        if end_marker in block:
            full_block = start_marker + block[:block.find(end_marker) + len(end_marker)]
            return full_block


def show_config(ser: serial.Serial) -> dict:
    """Показать и разобрать текущую конфигурацию."""
    ser.reset_input_buffer()
    ser.write(b"config show\r\n")

    try:
        config_block = wait_for_config_block(ser, "--- CONFIG ---", "--- END CONFIG ---")
    except TimeoutError as e:
        print(f"Error reading config: {e}")
        return {}

    print(config_block)
    config = parse_config(config_block)
    return config


def parse_config(response: str) -> dict:
    """Парсит конфигурацию из ответа."""
    config = {}
    in_config = False
    for line in response.split("\n"):
        line = line.strip()
        if line == "--- CONFIG ---":
            in_config = True
            continue
        if line == "--- END CONFIG ---":
            break
        if in_config and "=" in line:
            key, val = line.split("=", 1)
            config[key] = val
    return config


def _wait_for_line(ser: serial.Serial, prefixes: tuple, timeout: float) -> str | None:
    """Читает строки из Serial, пока одна не начнётся с ожидаемого префикса.

    Буфер вычитывается инкрементально, поэтому он не переполняется, даже если
    устройство временно заблокировано (конверсия датчиков, HTTP-таймаут).
    Возвращает совпавшую строку или None по таймауту.
    """
    prev_timeout = ser.timeout
    ser.timeout = 0.2
    deadline = time.time() + timeout
    buf = ""
    try:
        while time.time() < deadline:
            chunk = ser.read(ser.in_waiting or 1).decode("utf-8", errors="ignore")
            if not chunk:
                continue
            buf += chunk
            while "\n" in buf:
                line, buf = buf.split("\n", 1)
                line = line.strip()
                if any(line.startswith(p) for p in prefixes):
                    return line
        return None
    finally:
        ser.timeout = prev_timeout


def set_config(ser: serial.Serial, key: str, value: str,
               timeout: float = 15.0, retries: int = 2) -> bool:
    """Устанавливает параметр конфигурации и ожидает подтверждения от устройства.

    Дожидается подтверждения `Set: <key>=...` от устройства перед возвратом.
    Это синхронизирует отправку со скоростью прошивки и не даёт командам
    накапливаться в RX-буфере МК (иначе длинные строки вроде server_url теряются).
    Возвращает True, если устройство подтвердило изменение.
    """
    if key not in CONFIG_KEYS:
        print(f"Unknown key: {key}")
        print(f"Valid keys: {', '.join(CONFIG_KEYS)}")
        return False

    ack_prefix = f"Set: {key}="
    unknown_msg = f"Unknown key: {key}"
    for attempt in range(1, retries + 1):
        ser.reset_input_buffer()
        ser.write((f"config set {key}={value}\r\n").encode())
        line = _wait_for_line(ser, (ack_prefix, unknown_msg), timeout)
        if line is not None:
            print(line)
            return line.startswith(ack_prefix)
        if attempt < retries:
            print(f"  [retry {attempt}/{retries}] no ACK for '{key}', resending...")
    print(f"  [fail] device did not acknowledge '{key}'")
    return False


def reset_config(ser: serial.Serial) -> None:
    """Сбрасывает конфигурацию к значениям по умолчанию."""
    response = send_command(ser, "config reset")
    print(response)


def load_config_file(path: str) -> dict:
    """Загружает и разбирает JSON-файл конфигурации."""
    if not os.path.exists(path):
        print(f"Error: config file not found: {path}")
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        print(f"Error: invalid JSON in {path}: {e}")
        return {}


def upload_config(ser: serial.Serial, config: dict) -> None:
    """Загружает конфигурацию из словаря на устройство через Serial."""
    if not config:
        print("Nothing to upload: config is empty.")
        return

    ok = 0
    total = 0
    for key, value in config.items():
        if key not in CONFIG_KEYS:
            print(f"  [skip] Unknown key: {key}")
            continue
        total += 1
        display_value = "***" if key == "wifi_pass" else str(value)
        print(f"  Setting {key} = {display_value}")
        if set_config(ser, key, str(value)):
            ok += 1

    print(f"\nUpload complete ({ok}/{total} keys acknowledged). Current device config:")
    show_config(ser)


def interactive_mode(ser: serial.Serial) -> None:
    """Интерактивный режим настройки конфигурации."""
    print("Interactive configuration mode. Type 'help' for commands, 'quit' to exit.\n")

    while True:
        try:
            cmd = input("> ").strip()

            if cmd in ("quit", "exit", "q"):
                break
            elif cmd == "help":
                print("Commands:")
                print("  show              - show current config")
                print("  set key=value     - set a config key")
                print("  reset             - reset to defaults")
                print("  keys              - list available keys")
                print("  quit              - exit interactive mode")
            elif cmd == "show":
                show_config(ser)
            elif cmd == "keys":
                print("Available keys:")
                for k in CONFIG_KEYS:
                    print(f"  {k}")
            elif cmd.startswith("set "):
                kv = cmd[4:]
                if "=" not in kv:
                    print("Usage: set key=value")
                    continue
                key, val = kv.split("=", 1)
                set_config(ser, key, val)
            elif cmd == "reset":
                confirm = input("Reset to defaults? (y/N): ")
                if confirm.lower() == "y":
                    reset_config(ser)
            elif cmd:
                print(f"Unknown command: {cmd}. Type 'help' for commands.")

        except KeyboardInterrupt:
            print("\nExiting...")
            break


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Manage ESP32 configuration via Serial",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--show", action="store_true", help="Show current configuration")
    parser.add_argument("--set", metavar="KEY=VALUE", help="Set a configuration key")
    parser.add_argument("--reset", action="store_true", help="Reset to defaults")
    parser.add_argument("--interactive", "-i", action="store_true", help="Interactive mode")
    parser.add_argument("--upload", action="store_true", help="Upload configuration from config.json")
    parser.add_argument("--file", default=CONFIG_FILE, metavar="PATH", help=f"JSON file to upload (default: config.json)")
    parser.add_argument("--baud", type=int, default=BAUD_RATE,
                        help=f"Baud rate (default: {BAUD_RATE}); must match SERIAL_BAUD_RATE in firmware")
    parser.add_argument("--port", default=SERIAL_PORT, help=f"Serial port (default: {SERIAL_PORT})")
    args = parser.parse_args()

    # По умолчанию показываем конфигурацию, если не указано другое действие
    if not (args.show or args.set or args.reset or args.interactive or args.upload):
        args.show = True

    with serial.Serial(args.port, args.baud, timeout=2) as ser:
        time.sleep(2)  # ждём установки соединения

        if args.show:
            show_config(ser)
        elif args.set:
            if "=" not in args.set:
                print("Usage: --set key=value")
                return
            key, val = args.set.split("=", 1)
            set_config(ser, key, val)
        elif args.reset:
            reset_config(ser)
        elif args.interactive:
            interactive_mode(ser)
        elif args.upload:
            config = load_config_file(args.file)
            upload_config(ser, config)


if __name__ == "__main__":
    main()
