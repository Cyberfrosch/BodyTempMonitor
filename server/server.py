"""
server.py - Flask HTTP-сервер для приёма данных с ESP32.

Маршруты:
  POST /api/data       - приём данных с датчиков ESP32 (ответ: X-Config-ETag)
  GET  /api/chart-data - JSON-данные для графика
  POST /api/notes      - добавление заметки
  GET  /dashboard      - веб-дашборд с графиком и заметками
  GET  /api/config     - несвязочный конфиг устройства (key=value, для прошивки)
  POST /api/config     - обновление несвязочного конфига (JSON, из веб-формы)
  GET  /config         - страница редактирования конфига устройства
"""

from flask import Flask, Response, jsonify, make_response, render_template, request
from flask.views import MethodView

from app_config import cfg
from config_schema import BINDING_KEYS, CONFIG_LABELS, NON_BINDING_KEYS
from app_paths import resource_path
from db_common import Database

# Экспортируем для обратной совместимости (gui.py: from server import HOST, PORT)
HOST = cfg.server_host
PORT = cfg.server_port


class DataAPI(MethodView):
    """Приём данных с датчиков ESP32 (POST /api/data).

    Ответ несёт заголовок X-Config-ETag - SHA-256 несвязочного конфига.
    Прошивка сравнивает его с последним применённым ETag и при расхождении
    делает GET /api/config (событийный pull без периодического опроса).
    """

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

        resp = make_response("ok", 200)
        resp.headers["X-Config-ETag"] = cfg.compute_etag()
        return resp


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


class DeviceConfigAPI(MethodView):
    """Несвязочный конфиг устройства (GET/POST /api/config).

    GET  - text/plain, строки key=value + etag= (прошивка парсит напрямую).
    POST - JSON-тело {key: value}; связочные ключи отклоняются.
    """

    def get(self):
        return Response(cfg.as_text(), mimetype="text/plain")

    def post(self):
        data = request.get_json(force=True, silent=True) or {}
        applied, rejected = cfg.save_device_updates(data)
        return jsonify({
            "applied":  applied,
            "rejected": rejected,
            "etag":     cfg.compute_etag(),
        }), (200 if applied else 400)


class DeviceConfigPage(MethodView):
    """Страница редактирования несвязочного конфига устройства (GET /config)."""

    def get(self):
        return render_template(
            "config.html",
            config=cfg.device_config(),
            editable_keys=sorted(NON_BINDING_KEYS),
            binding_keys=sorted(BINDING_KEYS),
            etag=cfg.compute_etag(),
            labels=CONFIG_LABELS,
        )


def create_app(db: Database) -> Flask:
    """Создаёт и настраивает Flask-приложение, регистрируя все представления."""
    app = Flask(__name__, template_folder=resource_path("templates"))

    app.add_url_rule("/api/data",       view_func=DataAPI.as_view("data_api", db),             methods=["POST"])
    app.add_url_rule("/api/chart-data", view_func=ChartDataAPI.as_view("chart_data", db),      methods=["GET"])
    app.add_url_rule("/api/notes",      view_func=NotesAPI.as_view("notes_api", db),           methods=["POST"])
    app.add_url_rule("/dashboard",      view_func=DashboardView.as_view("dashboard", db),      methods=["GET"])
    app.add_url_rule("/api/config",     view_func=DeviceConfigAPI.as_view("device_config_api"), methods=["GET", "POST"])
    app.add_url_rule("/config",         view_func=DeviceConfigPage.as_view("device_config_page"), methods=["GET"])

    return app


if __name__ == "__main__":
    from db_common import DATABASE
    db = Database(DATABASE)
    db.init_schema()
    print(f"Server running on http://{HOST}:{PORT}")
    print(f"Dashboard:     http://{HOST}:{PORT}/dashboard")
    print(f"Device config: http://{HOST}:{PORT}/config")
    create_app(db).run(host=HOST, port=PORT, threaded=True)
