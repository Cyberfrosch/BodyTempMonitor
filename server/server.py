"""
server.py — Flask HTTP-сервер для приёма данных с ESP32.

Маршруты:
  POST /api/data       — приём данных с датчиков ESP32
  GET  /dashboard      — веб-дашборд с графиком и заметками
  GET  /api/chart-data — JSON-данные для графика
  POST /api/notes      — добавление заметки
"""

from datetime import datetime

from flask import Flask, jsonify, render_template, request
from flask.views import MethodView

from db_common import DATABASE, Database

# ---------- Настройки ----------
HOST = "0.0.0.0"
PORT = 5000

class DataAPI(MethodView):
    """Приём данных с датчиков ESP32 (POST /api/data)."""

    def __init__(self, db: Database) -> None:
        self.db = db

    def post(self):
        data = request.get_json()
        if not data or "temp0" not in data or "temp1" not in data or "timestamp" not in data:
            return "bad request: needs temp0, temp1, and timestamp", 400

        timestamp = Database.unix_to_str(data["timestamp"])

        inserted0 = self.db.insert_temperature(timestamp, 0, data["temp0"])
        inserted1 = self.db.insert_temperature(timestamp, 1, data["temp1"])

        if inserted0 and inserted1:
            print(f"[{timestamp}] temp0={data['temp0']} °C  temp1={data['temp1']} °C")
        elif not inserted0 and not inserted1:
            print(f"[{timestamp}] Skipped (duplicate or invalid)")
        else:
            print(f"[{timestamp}] Partially inserted (one sensor invalid/duplicate)")

        return "ok", 200


class ChartDataAPI(MethodView):
    """Данные для графика температуры (GET /api/chart-data)."""

    def __init__(self, db: Database) -> None:
        self.db = db

    def get(self):
        return jsonify(self.db.fetch_temperatures())


class NotesAPI(MethodView):
    """Добавление заметок (POST /api/notes)."""

    def __init__(self, db: Database) -> None:
        self.db = db

    def post(self):
        data = request.get_json()
        if not data or "note" not in data:
            return "bad request: needs note", 400
        self.db.insert_note(data["note"])
        return "ok", 200


class DashboardView(MethodView):
    """Веб-дашборд с графиком и заметками (GET /dashboard)."""

    def __init__(self, db: Database) -> None:
        self.db = db

    def get(self):
        notes = self.db.fetch_notes(limit=20)
        return render_template("dashboard.html", notes=notes)


def create_app(db: Database) -> Flask:
    """Создаёт и настраивает Flask-приложение, регистрируя все представления."""
    app = Flask(__name__)

    app.add_url_rule("/api/data",       view_func=DataAPI.as_view("data_api", db),        methods=["POST"])
    app.add_url_rule("/api/chart-data", view_func=ChartDataAPI.as_view("chart_data", db), methods=["GET"])
    app.add_url_rule("/api/notes",      view_func=NotesAPI.as_view("notes_api", db),      methods=["POST"])
    app.add_url_rule("/dashboard",      view_func=DashboardView.as_view("dashboard", db), methods=["GET"])

    return app


if __name__ == "__main__":
    db = Database(DATABASE)
    db.init_schema()
    print(f"Server running on http://{HOST}:{PORT}")
    print(f"Dashboard: http://{HOST}:{PORT}/dashboard")
    create_app(db).run(host=HOST, port=PORT, threaded=True)
