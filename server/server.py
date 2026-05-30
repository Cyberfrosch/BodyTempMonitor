"""
server.py - Flask HTTP-сервер для приёма данных с ESP32.

Маршруты:
  POST /api/data       - приём данных с датчиков ESP32
  GET  /api/data       - (не используется; POST-only)
  GET  /api/chart-data - JSON-данные для графика
  POST /api/notes      - добавление заметки
  GET  /dashboard      - веб-дашборд с графиком и заметками
  GET  /api/config     - «желаемый» конфиг устройства (key=value, для прошивки)
  POST /api/config     - обновление желаемого конфига (JSON, из веб-формы)
  GET  /config         - страница редактирования конфига устройства
"""

from flask import Flask, Response, jsonify, make_response, render_template, request
from flask.views import MethodView

from app_paths import resource_path
from db_common import DATABASE, Database
from device_config import DEVICE_CONFIG_FILE, DeviceConfig, WEB_EDITABLE_KEYS

# ---------- Настройки ----------
HOST = "0.0.0.0"
PORT = 5000


class DataAPI(MethodView):
    """Приём данных с датчиков ESP32 (POST /api/data).

    Ответ содержит заголовок X-Config-Revision с текущей ревизией желаемого
    конфига.  Прошивка сравнивает его с последней применённой ревизией и,
    если они отличаются, делает GET /api/config для получения обновлений.
    """

    def __init__(self, db: Database, dev_cfg: DeviceConfig) -> None:
        self.db      = db
        self.dev_cfg = dev_cfg

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
        resp.headers["X-Config-Revision"] = str(self.dev_cfg.revision)
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
    """Желаемый конфиг устройства (GET/POST /api/config).

    GET  → text/plain, строки key=value (прошивка парсит напрямую).
    POST → JSON-тело {"key": value, ...}; связочные ключи отклоняются.
    """

    def __init__(self, dev_cfg: DeviceConfig) -> None:
        self.dev_cfg = dev_cfg

    def get(self):
        return Response(self.dev_cfg.as_text(), mimetype="text/plain")

    def post(self):
        data = request.get_json(force=True, silent=True) or {}
        applied, rejected = self.dev_cfg.update(data)
        result: dict = {
            "applied":  applied,
            "rejected": rejected,
            "revision": self.dev_cfg.revision,
        }
        return jsonify(result), (200 if applied else 400)


class DeviceConfigPage(MethodView):
    """Страница редактирования желаемого конфига устройства (GET /config)."""

    def __init__(self, dev_cfg: DeviceConfig) -> None:
        self.dev_cfg = dev_cfg

    def get(self):
        return render_template(
            "config.html",
            config=self.dev_cfg.get_all(),
            editable_keys=WEB_EDITABLE_KEYS,
        )


def create_app(db: Database, dev_cfg: DeviceConfig | None = None) -> Flask:
    """Создаёт и настраивает Flask-приложение, регистрируя все представления.

    dev_cfg опционален: если не передан, создаётся с путём по умолчанию.
    Это сохраняет обратную совместимость с вызовами create_app(db).
    """
    if dev_cfg is None:
        dev_cfg = DeviceConfig(DEVICE_CONFIG_FILE)

    app = Flask(__name__, template_folder=resource_path("templates"))

    app.add_url_rule(
        "/api/data",
        view_func=DataAPI.as_view("data_api", db, dev_cfg),
        methods=["POST"],
    )
    app.add_url_rule(
        "/api/chart-data",
        view_func=ChartDataAPI.as_view("chart_data", db),
        methods=["GET"],
    )
    app.add_url_rule(
        "/api/notes",
        view_func=NotesAPI.as_view("notes_api", db),
        methods=["POST"],
    )
    app.add_url_rule(
        "/dashboard",
        view_func=DashboardView.as_view("dashboard", db),
        methods=["GET"],
    )
    app.add_url_rule(
        "/api/config",
        view_func=DeviceConfigAPI.as_view("device_config_api", dev_cfg),
        methods=["GET", "POST"],
    )
    app.add_url_rule(
        "/config",
        view_func=DeviceConfigPage.as_view("device_config_page", dev_cfg),
        methods=["GET"],
    )

    return app


if __name__ == "__main__":
    db = Database(DATABASE)
    db.init_schema()
    print(f"Server running on http://{HOST}:{PORT}")
    print(f"Dashboard:     http://{HOST}:{PORT}/dashboard")
    print(f"Device config: http://{HOST}:{PORT}/config")
    create_app(db).run(host=HOST, port=PORT, threaded=True)
