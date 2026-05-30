"""
tool.py — единая точка входа для CLI-утилит BodyTempMonitor.

Подкоманды:
  tool config [флаги]  — управление конфигурацией ESP32 (config_tool.py)
  tool log [флаги]     — выгрузка CSV-журнала и мониторинг Serial (logger.py)

Usage:
  python tool.py config --show
  python tool.py config --set wifi_ssid=Home
  python tool.py config --upload
  python tool.py log
  python tool.py log --monitor
  python tool.py log --clear
"""

import argparse

from config_tool import add_config_subparser, run_config
from logger import add_log_subparser, run_log


def main() -> None:
    parser = argparse.ArgumentParser(
        description="BodyTempMonitor CLI — ESP32 config and log utilities.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "examples:\n"
            "  tool config --show\n"
            "  tool config --set wifi_ssid=Home\n"
            "  tool config --upload\n"
            "  tool log\n"
            "  tool log --monitor\n"
            "  tool log --clear\n"
        ),
    )

    subparsers = parser.add_subparsers(dest="command", metavar="COMMAND")
    subparsers.required = True

    add_config_subparser(subparsers)
    add_log_subparser(subparsers)

    args = parser.parse_args()

    if args.command == "config":
        run_config(args)
    elif args.command == "log":
        run_log(args)


if __name__ == "__main__":
    main()
