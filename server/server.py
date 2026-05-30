"""
server.py — Flask HTTP-сервер для приёма данных с ESP32.

Маршруты:
  POST /api/data       — приём данных с датчиков ESP32
  GET  /dashboard      — веб-дашборд с графиком и заметками
  GET  /api/chart-data — JSON-данные для графика
  POST /api/notes      — добавление заметки
"""

from datetime import datetime

from flask import Flask, jsonify, render_template_string, request
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
        return render_template_string(DASHBOARD_HTML, notes=notes)


def create_app(db: Database) -> Flask:
    """Создаёт и настраивает Flask-приложение, регистрируя все представления."""
    app = Flask(__name__)

    app.add_url_rule("/api/data",       view_func=DataAPI.as_view("data_api", db),        methods=["POST"])
    app.add_url_rule("/api/chart-data", view_func=ChartDataAPI.as_view("chart_data", db), methods=["GET"])
    app.add_url_rule("/api/notes",      view_func=NotesAPI.as_view("notes_api", db),      methods=["POST"])
    app.add_url_rule("/dashboard",      view_func=DashboardView.as_view("dashboard", db), methods=["GET"])

    return app


DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Панель мониторинга температуры</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0"></script>
    <script src="https://cdn.jsdelivr.net/npm/hammerjs@2.0.8"></script>
    <script src="https://cdn.jsdelivr.net/npm/chartjs-plugin-zoom@2.0.1"></script>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }
        h1 { color: #333; }
        .container { max-width: 1200px; margin: 0 auto; background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        canvas { max-height: 400px; margin-bottom: 30px; }
        .notes { margin-top: 30px; }
        .note-item { padding: 10px; margin: 5px 0; background: #f9f9f9; border-left: 3px solid #007bff; }
        .note-time { font-size: 0.85em; color: #666; }
        input, textarea { width: 100%; padding: 8px; margin: 5px 0; box-sizing: border-box; }
        button { padding: 10px 20px; background: #007bff; color: white; border: none; cursor: pointer; border-radius: 4px; margin-right: 10px; }
        button:hover { background: #0056b3; }
        button:disabled { background: #ccc; cursor: not-allowed; }
        .chart-controls { margin-bottom: 10px; }
        .auto-refresh { margin-left: 15px; }
        .auto-refresh input { width: auto; margin: 0 5px; }
        .switch { position: relative; display: inline-block; width: 50px; height: 24px; margin-left: 10px; vertical-align: middle; }
        .switch input { opacity: 0; width: 0; height: 0; }
        .slider { position: absolute; cursor: pointer; top: 0; left: 0; right: 0; bottom: 0; background-color: #ccc; transition: .4s; border-radius: 24px; }
        .slider:before { position: absolute; content: ""; height: 18px; width: 18px; left: 3px; bottom: 3px; background-color: white; transition: .4s; border-radius: 50%; }
        input:checked + .slider { background-color: #007bff; }
        input:checked + .slider:before { transform: translateX(26px); }
    </style>
</head>
<body>
    <div class="container">
        <h1>Панель мониторинга температуры</h1>
        <div class="chart-controls">
            <button id="resetZoomBtn" onclick="chart.resetZoom()" disabled>Сбросить масштаб</button>
            <span class="auto-refresh">
                Автообновление:
                <label class="switch">
                    <input type="checkbox" id="autoRefresh" checked>
                    <span class="slider"></span>
                </label>
            </span>
        </div>
        <canvas id="tempChart"></canvas>

        <h2>Добавить заметку</h2>
        <textarea id="noteInput" rows="3" placeholder="Введите заметку..."></textarea>
        <button onclick="addNote()">Добавить заметку</button>

        <div class="notes">
            <h2>Последние заметки</h2>
            {% for note in notes %}
            <div class="note-item">
                <div class="note-time">{{ note.timestamp }}</div>
                <div>{{ note.note }}</div>
            </div>
            {% endfor %}
        </div>
    </div>

    <script>
        const ctx = document.getElementById('tempChart').getContext('2d');
        const resetZoomBtn = document.getElementById('resetZoomBtn');
        const autoRefreshCheckbox = document.getElementById('autoRefresh');
        let chart;
        let autoRefreshInterval;

        async function loadData() {
            const response = await fetch('/api/chart-data');
            const data = await response.json();

            // Group by sensor_id
            const sensor0 = data.filter(d => d.sensor_id === 0).reverse();
            const sensor1 = data.filter(d => d.sensor_id === 1).reverse();

            const labels = sensor0.map(d => d.timestamp);

            // Сохраняем состояние видимости датчиков
            let sensor0Visible = true;
            let sensor1Visible = true;
            if (chart) {
                sensor0Visible = chart.isDatasetVisible(0);
                sensor1Visible = chart.isDatasetVisible(1);
                chart.destroy();
            } else {
                resetZoomBtn.disabled = true;
            }

            chart = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: labels,
                    datasets: [
                        {
                            label: 'Датчик 0',
                            data: sensor0.map(d => d.temperature),
                            borderColor: 'rgb(255, 99, 132)',
                            backgroundColor: 'rgba(255, 99, 132, 0.1)',
                            tension: 0.1,
                            hidden: !sensor0Visible
                        },
                        {
                            label: 'Датчик 1',
                            data: sensor1.map(d => d.temperature),
                            borderColor: 'rgb(54, 162, 235)',
                            backgroundColor: 'rgba(54, 162, 235, 0.1)',
                            tension: 0.1,
                            hidden: !sensor1Visible
                        }
                    ]
                },
                options: {
                    responsive: true,
                    plugins: {
                        legend: { position: 'top' },
                        title: { display: true, text: 'Температура во времени' },
                        zoom: {
                            zoom: {
                                drag: {
                                    enabled: true,
                                    backgroundColor: 'rgba(54, 162, 235, 0.3)',
                                    modifierKey: 'shift'
                                },
                                wheel: {
                                    enabled: true,
                                    speed: 0.1
                                },
                                mode: 'x',
                                onZoomComplete: function() {
                                    resetZoomBtn.disabled = false;
                                }
                            },
                            pan: {
                                enabled: true,
                                mode: 'x',
                                modifierKey: null,
                                onPanComplete: function() {
                                    resetZoomBtn.disabled = false;
                                }
                            },
                            limits: {
                                x: { min: 'original', max: 'original' }
                            }
                        }
                    },
                    scales: {
                        y: { beginAtZero: false }
                    }
                }
            });
        }

        function startAutoRefresh() {
            if (autoRefreshInterval) clearInterval(autoRefreshInterval);
            if (autoRefreshCheckbox.checked) {
                autoRefreshInterval = setInterval(loadData, 60000);
            }
        }

        autoRefreshCheckbox.addEventListener('change', startAutoRefresh);

        const originalResetZoom = Chart.prototype.resetZoom;
        Chart.prototype.resetZoom = function() {
            originalResetZoom.call(this);
            resetZoomBtn.disabled = true;
        };

        async function addNote() {
            const note = document.getElementById('noteInput').value.trim();
            if (!note) return;

            await fetch('/api/notes', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ note })
            });

            document.getElementById('noteInput').value = '';
            location.reload();
        }

        loadData();
        startAutoRefresh();
    </script>
</body>
</html>
"""


if __name__ == "__main__":
    db = Database(DATABASE)
    db.init_schema()
    print(f"Server running on http://{HOST}:{PORT}")
    print(f"Dashboard: http://{HOST}:{PORT}/dashboard")
    create_app(db).run(host=HOST, port=PORT, threaded=True)
