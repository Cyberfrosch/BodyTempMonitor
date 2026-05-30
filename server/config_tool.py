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

from app_paths import external_path
from serial_device import BAUD_RATE, SERIAL_PORT, SerialDevice

CONFIG_FILE = external_path("config.json")

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


class ConfigClient:
    """CLI-клиент для управления конфигурацией ESP32 через Serial."""

    def __init__(self, device: SerialDevice) -> None:
        self._dev = device

    # ------------------------------------------------------------------ утилиты

    @staticmethod
    def parse_config(response: str) -> dict:
        """Парсит конфигурацию из текстового блока ответа устройства."""
        config: dict = {}
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

    @staticmethod
    def load_file(path: str) -> dict:
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

    # ------------------------------------------------------------------ команды

    def show(self) -> dict:
        """Показывает и разбирает текущую конфигурацию устройства."""
        self._dev.reset_input()
        self._dev.send("config show")
        try:
            block = self._dev.wait_for_block("--- CONFIG ---", "--- END CONFIG ---")
        except TimeoutError as e:
            print(f"Error reading config: {e}")
            return {}
        print(block)
        return self.parse_config(block)

    def set(self, key: str, value: str, timeout: float = 15.0, retries: int = 2) -> bool:
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
            self._dev.reset_input()
            self._dev.send(f"config set {key}={value}")
            line = self._dev.wait_for_line((ack_prefix, unknown_msg), timeout)
            if line is not None:
                print(line)
                return line.startswith(ack_prefix)
            if attempt < retries:
                print(f"  [retry {attempt}/{retries}] no ACK for '{key}', resending...")
        print(f"  [fail] device did not acknowledge '{key}'")
        return False

    def reset(self) -> None:
        """Сбрасывает конфигурацию к значениям по умолчанию."""
        self._dev.send("config reset")
        time.sleep(1)
        print(self._dev.read_available().strip())

    def upload(self, config: dict) -> None:
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
            if self.set(key, str(value)):
                ok += 1

        print(f"\nUpload complete ({ok}/{total} keys acknowledged). Current device config:")
        self.show()

    def interactive(self) -> None:
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
                    self.show()
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
                    self.set(key, val)
                elif cmd == "reset":
                    confirm = input("Reset to defaults? (y/N): ")
                    if confirm.lower() == "y":
                        self.reset()
                elif cmd:
                    print(f"Unknown command: {cmd}. Type 'help' for commands.")

            except KeyboardInterrupt:
                print("\nExiting...")
                break


def _add_config_args(p: argparse.ArgumentParser) -> None:
    """Регистрирует аргументы конфигурационного CLI в переданном парсере."""
    p.add_argument("--show",        action="store_true", help="Show current configuration")
    p.add_argument("--set",         metavar="KEY=VALUE", help="Set a configuration key")
    p.add_argument("--reset",       action="store_true", help="Reset to defaults")
    p.add_argument("--interactive", "-i", action="store_true", help="Interactive mode")
    p.add_argument("--upload",      action="store_true", help="Upload configuration from config.json")
    p.add_argument("--file",        default=CONFIG_FILE, metavar="PATH",
                   help="JSON file to upload (default: config.json)")
    p.add_argument("--baud",        type=int, default=BAUD_RATE,
                   help=f"Baud rate (default: {BAUD_RATE}); must match SERIAL_BAUD_RATE in firmware")
    p.add_argument("--port",        default=SERIAL_PORT,
                   help=f"Serial port (default: {SERIAL_PORT})")


def add_config_subparser(subparsers) -> None:
    """Добавляет подпарсер 'config' в составной парсер (tool.py)."""
    p = subparsers.add_parser(
        "config",
        description="Manage ESP32 configuration via Serial.",
        epilog=(
            "examples:\n"
            "  tool config                              # show current config\n"
            "  tool config --set wifi_ssid=Home         # set one key\n"
            "  tool config --upload                     # upload from config.json\n"
            "  tool config --upload --file my.json\n"
            "  tool config --reset\n"
            "  tool config --interactive\n"
            "  tool config --port COM3 --baud 115200 --show\n"
            "\n"
            f"valid config keys: {', '.join(CONFIG_KEYS)}"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        help="Manage ESP32 configuration",
    )
    _add_config_args(p)


def run_config(args: argparse.Namespace) -> None:
    """Выполняет подкоманду 'config' с разобранными аргументами."""
    if not (args.show or args.set or args.reset or args.interactive or args.upload):
        args.show = True

    with SerialDevice(args.port, args.baud) as dev:
        client = ConfigClient(dev)

        if args.show:
            client.show()
        elif args.set:
            if "=" not in args.set:
                print("Usage: --set key=value")
                return
            key, val = args.set.split("=", 1)
            client.set(key, val)
        elif args.reset:
            client.reset()
        elif args.interactive:
            client.interactive()
        elif args.upload:
            config = ConfigClient.load_file(args.file)
            client.upload(config)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Manage ESP32 configuration via Serial.",
        epilog=(
            "examples:\n"
            "  python config_tool.py                       # show current config\n"
            "  python config_tool.py --set wifi_ssid=Home  # set one key\n"
            "  python config_tool.py --upload              # upload from config.json\n"
            "  python config_tool.py --upload --file my.json\n"
            "  python config_tool.py --reset\n"
            "  python config_tool.py --interactive\n"
            "  python config_tool.py --port COM3 --baud 115200 --show\n"
            "\n"
            f"valid config keys: {', '.join(CONFIG_KEYS)}"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    _add_config_args(parser)
    args = parser.parse_args()
    run_config(args)


if __name__ == "__main__":
    main()
