"""
config_tool.py — Manage ESP32 runtime configuration via Serial.

The ESP32 stores configuration in NVS (Preferences). This tool provides
a CLI interface to read/write config values through Serial commands.

Usage:
  python config_tool.py                    # show current config
  python config_tool.py --show             # show current config
  python config_tool.py --set key=value    # set a config key
  python config_tool.py --reset            # reset to defaults
  python config_tool.py --interactive      # interactive mode
  python config_tool.py --upload           # upload from config.json
"""

import argparse
import json
import os
import time
import serial

SERIAL_PORT = "COM5"
BAUD_RATE   = 115200
# CONFIG_FILE = os.path.join(os.path.dirname(__file__), "config.json")

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
    """Send command and return response."""
    ser.write((cmd + "\r\n").encode())
    time.sleep(wait)
    response = ser.read(ser.in_waiting).decode("utf-8", errors="ignore")
    return response.strip()


def parse_config(response: str) -> dict:
    """Parse config from 'config show' response."""
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


def show_config(ser: serial.Serial) -> dict:
    """Show current configuration."""
    response = send_command(ser, "config show")
    print(response)

    config = parse_config(response)
    return config


def set_config(ser: serial.Serial, key: str, value: str) -> None:
    """Set a configuration key."""
    if key not in CONFIG_KEYS:
        print(f"Unknown key: {key}")
        print(f"Valid keys: {', '.join(CONFIG_KEYS)}")
        return

    response = send_command(ser, f"config set {key}={value}")
    print(response)


def reset_config(ser: serial.Serial) -> None:
    """Reset configuration to defaults."""
    response = send_command(ser, "config reset")
    print(response)


def interactive_mode(ser: serial.Serial) -> None:
    """Interactive configuration mode."""
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
    parser = argparse.ArgumentParser(description="Manage ESP32 configuration via Serial.")
    parser.add_argument("--show", action="store_true", help="Show current configuration")
    parser.add_argument("--set", metavar="KEY=VALUE", help="Set a configuration key")
    parser.add_argument("--reset", action="store_true", help="Reset to defaults")
    parser.add_argument("--interactive", "-i", action="store_true", help="Interactive mode")
    parser.add_argument("--port", default=SERIAL_PORT, help=f"Serial port (default: {SERIAL_PORT})")
    args = parser.parse_args()

    # Default to show if no action specified
    if not (args.show or args.set or args.reset or args.interactive):
        args.show = True

    with serial.Serial(args.port, BAUD_RATE, timeout=2) as ser:
        time.sleep(2)  # Wait for connection

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


if __name__ == "__main__":
    main()
