"""
app_paths.py - Разрешение путей к ресурсам в режиме разработки и в frozen-бандле.

resource_path  - упакованные ресурсы (templates/): при заморозке лежат в sys._MEIPASS.
external_path  - внешние файлы рядом с бинарём (config.json, sensor_data.db):
                 при заморозке - каталог exe, иначе - каталог этого модуля.
"""

import os
import sys


def resource_path(rel: str) -> str:
    """Путь к упакованному ресурсу: при заморозке - sys._MEIPASS, иначе - каталог модуля."""
    if getattr(sys, "frozen", False):
        base = sys._MEIPASS  # type: ignore[attr-defined]
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, rel)


def external_path(rel: str) -> str:
    """Путь к внешнему файлу рядом с бинарём: при заморозке - каталог exe, иначе - каталог модуля."""
    if getattr(sys, "frozen", False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, rel)
