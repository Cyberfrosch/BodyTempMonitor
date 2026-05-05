"""
server.py — Flask HTTP-сервер для приёма данных с ESP32.

Принимает POST /data с JSON {"temp0": float, "temp1": float},
сохраняет в SQLite. GET / — статус сервера.
"""

import sqlite3
from contextlib import closing
from datetime import datetime

from flask import Flask, request

# ---------- Настройки ----------
DATABASE = "sensor_data.db"
HOST     = "0.0.0.0"
PORT     = 5000

app = Flask(__name__)

CREATE_TABLE_SQL = """
    CREATE TABLE IF NOT EXISTS temperatures (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp  TEXT    NOT NULL,
        sensor_id  INTEGER NOT NULL,
        temperature REAL   NOT NULL
    )
"""


def init_db() -> None:
    with closing(sqlite3.connect(DATABASE)) as conn:
        conn.execute(CREATE_TABLE_SQL)
        conn.commit()


@app.route("/data", methods=["POST"])
def receive_data():
    data = request.get_json()
    if not data or "temp0" not in data or "temp1" not in data:
        return "bad request: needs temp0 and temp1", 400

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with closing(sqlite3.connect(DATABASE)) as conn:
        conn.executemany(
            "INSERT INTO temperatures (timestamp, sensor_id, temperature) VALUES (?, ?, ?)",
            [(now, 0, data["temp0"]), (now, 1, data["temp1"])],
        )
        conn.commit()

    print(f"[{now}] temp0={data['temp0']} °C  temp1={data['temp1']} °C")
    return "ok", 200


@app.route("/")
def index():
    return 'Server is running. POST to /data with {"temp0": ..., "temp1": ...}'


if __name__ == "__main__":
    init_db()
    print(f"Server running on http://{HOST}:{PORT}")
    app.run(host=HOST, port=PORT)
