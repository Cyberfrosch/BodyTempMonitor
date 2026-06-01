"""
gui.py - Десктоп-GUI для BodyTempMonitor (PySide6).

Три вкладки:
  «Сервер»         - запуск/остановка Flask, лог werkzeug в реальном времени.
  «Конфигурация»   - чтение/запись конфига ESP32 через Serial (ConfigClient).
  «Логгер»         - скачивание CSV, очистка, потоковый мониторинг Serial.

Запуск:
  python server/gui.py

CLI-утилиты (tool config/log, server.py) продолжают работать независимо.
"""

import logging
import sys
import webbrowser
from typing import Callable

import serial.tools.list_ports
from PySide6.QtCore import QThread, Signal, Qt
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import (
    QApplication, QComboBox, QFormLayout, QGroupBox, QHBoxLayout, QLabel,
    QLineEdit, QMainWindow, QMessageBox, QPlainTextEdit, QPushButton,
    QSizePolicy, QTabWidget, QVBoxLayout, QWidget,
)
from werkzeug.serving import make_server

from app_config import cfg as app_cfg
from config_schema import CONFIG_KEYS, CONFIG_LABELS
from config_tool import ConfigClient
from db_common import DATABASE, Database
from logger import LogDownloader, SerialMonitor
from serial_device import BAUD_RATE, SERIAL_PORT, SerialDevice
from server import HOST, PORT, create_app


# ══════════════════════════════════════════════════════════════════════ helpers

def _list_ports() -> list[str]:
    return [p.device for p in serial.tools.list_ports.comports()] or [SERIAL_PORT]


class _QtLogHandler(logging.Handler):
    """Мост между Python-logging и Qt-сигналом."""

    def __init__(self, emitter: Callable[[str], None]) -> None:
        super().__init__()
        self._emit = emitter

    def emit(self, record: logging.LogRecord) -> None:
        self._emit(self.format(record))


# ══════════════════════════════════════════════════════════════════════ workers

class FlaskThread(QThread):
    """Запускает werkzeug-сервер в отдельном потоке."""
    log_line = Signal(str)

    def __init__(self, db: Database) -> None:
        super().__init__()
        self._db      = db
        self._srv     = None
        self._handler: _QtLogHandler | None = None

    def run(self) -> None:
        app = create_app(self._db)
        self._srv = make_server(HOST, PORT, app, threaded=True)

        self._handler = _QtLogHandler(self.log_line.emit)
        self._handler.setFormatter(logging.Formatter("%(asctime)s  %(message)s", "%H:%M:%S"))
        wz_log = logging.getLogger("werkzeug")
        wz_log.addHandler(self._handler)

        self.log_line.emit(f"Server started → http://localhost:{PORT}")
        self._srv.serve_forever()

    def stop(self) -> None:
        if self._srv:
            self._srv.shutdown()
        if self._handler:
            logging.getLogger("werkzeug").removeHandler(self._handler)


class ConfigWorker(QThread):
    """Выполняет Serial-операции с ConfigClient в фоновом потоке."""
    log_line     = Signal(str)
    config_ready = Signal(dict)   # после show()
    done         = Signal()       # не «finished» - иначе конфликт с QThread.finished

    def __init__(self, port: str, baud: int, action: str, **kwargs) -> None:
        super().__init__()
        self._port   = port
        self._baud   = baud
        self._action = action
        self._kwargs = kwargs

    def run(self) -> None:
        try:
            with SerialDevice(self._port, self._baud) as dev:
                client = ConfigClient(dev, log=self.log_line.emit)
                if self._action == "show":
                    cfg = client.show()
                    self.config_ready.emit(cfg)
                elif self._action == "apply":
                    for key, val in self._kwargs.get("pairs", []):
                        client.set(key, val)
                elif self._action == "reset":
                    client.reset()
                elif self._action == "upload":
                    client.upload(self._kwargs.get("config", {}))
        except Exception as exc:
            self.log_line.emit(f"[error] {exc}")
        finally:
            self.done.emit()


class DownloadWorker(QThread):
    """Скачивает CSV или очищает журнал."""
    log_line = Signal(str)
    done     = Signal()       # не «finished» - иначе конфликт с QThread.finished

    def __init__(self, port: str, baud: int, db: Database, action: str) -> None:
        super().__init__()
        self._port   = port
        self._baud   = baud
        self._db     = db
        self._action = action

    def run(self) -> None:
        import csv as _csv
        from io import StringIO
        KNOWN = {"unixtime,temp0,temp1", "reltime,temp0,temp1"}

        try:
            with SerialDevice(self._port, self._baud) as dev:
                dl = LogDownloader(dev, self._db, log=self.log_line.emit)
                if self._action == "download":
                    self.log_line.emit("Fetching CSV from device...")
                    lines = dl.fetch_csv()
                    if not lines:
                        self.log_line.emit("No data received.")
                    else:
                        reader  = _csv.reader(StringIO("\n".join(lines)))
                        header  = next(reader, None)
                        all_rows = [r for r in reader if ",".join(r).strip() not in KNOWN and r]
                        if header and ",".join(header).strip() not in KNOWN:
                            all_rows.insert(0, header)
                        if not all_rows or not LogDownloader.is_unix_timestamp(all_rows[0][0]):
                            self.log_line.emit("Warning: no Unix timestamps found.")
                        else:
                            dl.process(all_rows)
                elif self._action == "clear":
                    self.log_line.emit("Clearing CSV on ESP32...")
                    dl.clear()
        except Exception as exc:
            self.log_line.emit(f"[error] {exc}")
        finally:
            self.done.emit()


class MonitorWorker(QThread):
    """Потоковый мониторинг Serial. Останавливается через stop()."""
    chunk    = Signal(str)   # сырой текст для отображения
    db_saved = Signal(str)   # строка подтверждения сохранения в БД
    done     = Signal()      # не «finished» - иначе конфликт с QThread.finished

    def __init__(self, port: str, baud: int, db: Database) -> None:
        super().__init__()
        self._port    = port
        self._baud    = baud
        self._db      = db
        self._monitor: SerialMonitor | None = None

    def run(self) -> None:
        try:
            with SerialDevice(self._port, self._baud, serial_timeout=1) as dev:
                self._monitor = SerialMonitor(dev, self._db, chunk_cb=self.chunk.emit)
                self._monitor.run()
        except Exception as exc:
            self.chunk.emit(f"\n[error] {exc}\n")
        finally:
            self.done.emit()

    def stop(self) -> None:
        if self._monitor:
            self._monitor.stop()


# ══════════════════════════════════════════════════════════════════════ tab: server

class ServerTab(QWidget):
    def __init__(self, db: Database) -> None:
        super().__init__()
        self._db     = db
        self._thread: FlaskThread | None = None
        self._running = False
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)

        # --- Controls row
        ctrl = QHBoxLayout()
        self._btn_start = QPushButton("Запустить сервер")
        self._btn_stop  = QPushButton("Остановить сервер")
        self._btn_open  = QPushButton("Открыть дашборд")
        self._lbl_status = QLabel("● Остановлен")
        self._lbl_status.setStyleSheet("color: #888;")
        self._btn_stop.setEnabled(False)
        self._btn_open.setEnabled(False)
        for btn in (self._btn_start, self._btn_stop, self._btn_open):
            ctrl.addWidget(btn)
        ctrl.addWidget(self._lbl_status)
        ctrl.addStretch()
        root.addLayout(ctrl)

        # --- Log panel
        grp = QGroupBox("Лог сервера")
        vb  = QVBoxLayout(grp)
        self._log = QPlainTextEdit()
        self._log.setReadOnly(True)
        self._log.setMaximumBlockCount(2000)
        vb.addWidget(self._log)
        root.addWidget(grp)

        self._btn_start.clicked.connect(self._start)
        self._btn_stop.clicked.connect(self._stop)
        self._btn_open.clicked.connect(
            lambda: webbrowser.open(f"http://localhost:{PORT}/dashboard")
        )

    def _start(self) -> None:
        self._thread = FlaskThread(self._db)
        self._thread.log_line.connect(self._append)
        self._thread.start()
        self._running = True
        self._btn_start.setEnabled(False)
        self._btn_stop.setEnabled(True)
        self._btn_open.setEnabled(True)
        self._lbl_status.setText("● Работает")
        self._lbl_status.setStyleSheet("color: green; font-weight: bold;")

    def _stop(self) -> None:
        if self._thread:
            self._thread.stop()
            self._thread.wait(3000)
        self._running = False
        self._btn_start.setEnabled(True)
        self._btn_stop.setEnabled(False)
        self._btn_open.setEnabled(False)
        self._lbl_status.setText("● Остановлен")
        self._lbl_status.setStyleSheet("color: #888;")
        self._append("Server stopped.")

    def _append(self, text: str) -> None:
        self._log.appendPlainText(text)

    def shutdown(self) -> None:
        """Вызывается при закрытии окна."""
        if self._running:
            self._stop()


# ══════════════════════════════════════════════════════════════════════ tab: config

class ConfigTab(QWidget):
    serial_lock = Signal(bool)   # True = порт занят

    def __init__(self) -> None:
        super().__init__()
        self._worker: ConfigWorker | None = None
        self._orig_values: dict[str, str] = {}
        self._fields: dict[str, QLineEdit] = {}
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)

        # --- Port row
        port_row = QHBoxLayout()
        port_row.addWidget(QLabel("Порт:"))
        self._combo_port = QComboBox()
        self._combo_port.addItems(_list_ports())
        self._combo_port.setEditable(True)
        btn_refresh = QPushButton("↺")
        btn_refresh.setFixedWidth(32)
        btn_refresh.clicked.connect(self._refresh_ports)
        port_row.addWidget(self._combo_port)
        port_row.addWidget(btn_refresh)
        port_row.addWidget(QLabel("Baud:"))
        self._baud_edit = QLineEdit(str(BAUD_RATE))
        self._baud_edit.setFixedWidth(80)
        port_row.addWidget(self._baud_edit)
        port_row.addStretch()
        root.addLayout(port_row)

        # --- Form fields
        grp  = QGroupBox("Параметры конфигурации")
        form = QFormLayout(grp)
        for key in CONFIG_KEYS:
            le = QLineEdit()
            if key == "wifi_pass":
                le.setEchoMode(QLineEdit.EchoMode.Password)
                le.setPlaceholderText("не считывается с устройства — задайте вручную")
            self._fields[key] = le
            lbl = QLabel(CONFIG_LABELS.get(key, key))
            lbl.setToolTip(key)
            form.addRow(lbl, le)
        root.addWidget(grp)

        # --- Action buttons
        btn_row = QHBoxLayout()
        self._btn_read   = QPushButton("Прочитать")
        self._btn_apply  = QPushButton("Применить изменения")
        self._btn_upload = QPushButton("Загрузить config.json")
        self._btn_reset  = QPushButton("Сбросить к умолчанию")
        for btn in (self._btn_read, self._btn_apply, self._btn_upload, self._btn_reset):
            btn_row.addWidget(btn)
        root.addLayout(btn_row)

        # --- Log
        grp2 = QGroupBox("Лог операций")
        vb   = QVBoxLayout(grp2)
        self._log = QPlainTextEdit()
        self._log.setReadOnly(True)
        self._log.setMaximumBlockCount(1000)
        vb.addWidget(self._log)
        root.addWidget(grp2)

        self._btn_read.clicked.connect(self._do_read)
        self._btn_apply.clicked.connect(self._do_apply)
        self._btn_upload.clicked.connect(self._do_upload)
        self._btn_reset.clicked.connect(self._do_reset)

    # ------------------------------------------------------------------ slots

    def _refresh_ports(self) -> None:
        self._combo_port.clear()
        self._combo_port.addItems(_list_ports())

    def _port(self) -> str:
        return self._combo_port.currentText()

    def _baud(self) -> int:
        try:
            return int(self._baud_edit.text())
        except ValueError:
            return BAUD_RATE

    def _start_worker(self, worker: ConfigWorker) -> None:
        self._worker = worker
        worker.log_line.connect(self._log.appendPlainText)
        worker.done.connect(self._on_worker_done)
        self.serial_lock.emit(True)
        self._set_buttons(False)
        worker.start()

    def _on_worker_done(self) -> None:
        self.serial_lock.emit(False)
        self._set_buttons(True)

    def _set_buttons(self, enabled: bool) -> None:
        for btn in (self._btn_read, self._btn_apply, self._btn_upload, self._btn_reset):
            btn.setEnabled(enabled)

    def _do_read(self) -> None:
        w = ConfigWorker(self._port(), self._baud(), "show")
        w.config_ready.connect(self._populate_form)
        self._start_worker(w)

    def _populate_form(self, device_cfg: dict) -> None:
        self._orig_values = {}
        for key, le in self._fields.items():
            if key == "wifi_pass":
                # Password is always masked on device — never overwrite field or orig value.
                # Empty orig marks "unchanged": _do_apply skips empty fields, so an untouched
                # password field will not be sent to the device.
                le.setText("")
                self._orig_values[key] = ""
                continue
            val = device_cfg.get(key, "")
            le.setText(str(val))
            self._orig_values[key] = str(val)
        app_cfg.save_from_device(device_cfg)
        self._log.appendPlainText("Конфигурация сохранена в config.json")

    def _do_apply(self) -> None:
        pairs = []
        for key, le in self._fields.items():
            cur = le.text()
            if cur and cur != self._orig_values.get(key, ""):
                pairs.append((key, cur))
        if not pairs:
            self._log.appendPlainText("Нет изменений для отправки.")
            return
        w = ConfigWorker(self._port(), self._baud(), "apply", pairs=pairs)
        self._start_worker(w)

    def _do_upload(self) -> None:
        from config_tool import CONFIG_FILE
        cfg = ConfigClient.load_file(CONFIG_FILE)
        if not cfg:
            return
        w = ConfigWorker(self._port(), self._baud(), "upload", config=cfg)
        self._start_worker(w)

    def _do_reset(self) -> None:
        if QMessageBox.question(self, "Сброс", "Сбросить конфигурацию к значениям по умолчанию?") \
                != QMessageBox.StandardButton.Yes:
            return
        w = ConfigWorker(self._port(), self._baud(), "reset")
        self._start_worker(w)

    def set_serial_locked(self, locked: bool) -> None:
        """Блокирует/разблокирует кнопки, пока порт занят другой вкладкой."""
        self._set_buttons(not locked)


# ══════════════════════════════════════════════════════════════════════ tab: logger

class LoggerTab(QWidget):
    serial_lock = Signal(bool)

    def __init__(self, db: Database) -> None:
        super().__init__()
        self._db = db
        self._monitor_worker: MonitorWorker | None = None
        self._download_worker: DownloadWorker | None = None
        self._monitoring = False
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)

        # --- Port row
        port_row = QHBoxLayout()
        port_row.addWidget(QLabel("Порт:"))
        self._combo_port = QComboBox()
        self._combo_port.addItems(_list_ports())
        self._combo_port.setEditable(True)
        btn_refresh = QPushButton("↺")
        btn_refresh.setFixedWidth(32)
        btn_refresh.clicked.connect(self._refresh_ports)
        port_row.addWidget(self._combo_port)
        port_row.addWidget(btn_refresh)
        port_row.addWidget(QLabel("Baud:"))
        self._baud_edit = QLineEdit(str(BAUD_RATE))
        self._baud_edit.setFixedWidth(80)
        port_row.addWidget(self._baud_edit)
        port_row.addStretch()
        root.addLayout(port_row)

        # --- Action buttons
        btn_row = QHBoxLayout()
        self._btn_download = QPushButton("Скачать CSV → БД")
        self._btn_clear    = QPushButton("Очистить CSV")
        self._btn_monitor  = QPushButton("Начать мониторинг")
        self._btn_stop_mon = QPushButton("Остановить мониторинг")
        self._btn_stop_mon.setEnabled(False)
        for btn in (self._btn_download, self._btn_clear, self._btn_monitor, self._btn_stop_mon):
            btn_row.addWidget(btn)
        root.addLayout(btn_row)

        # --- Log
        grp = QGroupBox("Вывод Serial")
        vb  = QVBoxLayout(grp)
        self._log = QPlainTextEdit()
        self._log.setReadOnly(True)
        self._log.setMaximumBlockCount(5000)
        self._log.setFont(self._log.font())  # моноширинный шрифт сохраняется
        vb.addWidget(self._log)
        root.addWidget(grp)

        self._btn_download.clicked.connect(self._do_download)
        self._btn_clear.clicked.connect(self._do_clear)
        self._btn_monitor.clicked.connect(self._do_start_monitor)
        self._btn_stop_mon.clicked.connect(self._do_stop_monitor)

    # ------------------------------------------------------------------ slots

    def _refresh_ports(self) -> None:
        self._combo_port.clear()
        self._combo_port.addItems(_list_ports())

    def _port(self) -> str:
        return self._combo_port.currentText()

    def _baud(self) -> int:
        try:
            return int(self._baud_edit.text())
        except ValueError:
            return BAUD_RATE

    def _set_action_buttons(self, enabled: bool) -> None:
        self._btn_download.setEnabled(enabled)
        self._btn_clear.setEnabled(enabled)
        self._btn_monitor.setEnabled(enabled)

    def _do_download(self) -> None:
        w = DownloadWorker(self._port(), self._baud(), self._db, "download")
        w.log_line.connect(self._log.appendPlainText)
        w.done.connect(lambda: (self.serial_lock.emit(False), self._set_action_buttons(True)))
        self.serial_lock.emit(True)
        self._set_action_buttons(False)
        self._download_worker = w
        w.start()

    def _do_clear(self) -> None:
        if QMessageBox.question(self, "Очистка", "Очистить CSV-журнал на ESP32?") \
                != QMessageBox.StandardButton.Yes:
            return
        w = DownloadWorker(self._port(), self._baud(), self._db, "clear")
        w.log_line.connect(self._log.appendPlainText)
        w.done.connect(lambda: (self.serial_lock.emit(False), self._set_action_buttons(True)))
        self.serial_lock.emit(True)
        self._set_action_buttons(False)
        self._download_worker = w
        w.start()

    def _do_start_monitor(self) -> None:
        self._monitoring = True
        self.serial_lock.emit(True)
        self._set_action_buttons(False)
        self._btn_stop_mon.setEnabled(True)

        w = MonitorWorker(self._port(), self._baud(), self._db)
        w.chunk.connect(self._append_chunk)
        w.done.connect(self._on_monitor_done)
        self._monitor_worker = w
        w.start()

    def _do_stop_monitor(self) -> None:
        if self._monitor_worker:
            self._monitor_worker.stop()

    def _on_monitor_done(self) -> None:
        self._monitoring = False
        self.serial_lock.emit(False)
        self._set_action_buttons(True)
        self._btn_stop_mon.setEnabled(False)
        self._append_chunk("\n-- мониторинг остановлен --\n")

    def _append_chunk(self, chunk: str) -> None:
        """Вставляет chunk без добавления лишнего перевода строки."""
        cursor = self._log.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self._log.setTextCursor(cursor)
        self._log.insertPlainText(chunk)
        self._log.ensureCursorVisible()

    def set_serial_locked(self, locked: bool) -> None:
        """Блокирует кнопки, пока порт занят другой вкладкой."""
        if not self._monitoring:
            self._set_action_buttons(not locked)

    def shutdown(self) -> None:
        """Вызывается при закрытии окна."""
        if self._monitoring and self._monitor_worker:
            self._monitor_worker.stop()
            self._monitor_worker.wait(3000)


# ══════════════════════════════════════════════════════════════════════ main window

class MainWindow(QMainWindow):
    def __init__(self, db: Database) -> None:
        super().__init__()
        self.setWindowTitle("BodyTempMonitor")
        self.resize(900, 620)

        tabs = QTabWidget()

        self._server_tab = ServerTab(db)
        self._config_tab = ConfigTab()
        self._logger_tab = LoggerTab(db)

        tabs.addTab(self._server_tab, "Сервер")
        tabs.addTab(self._config_tab, "Конфигурация")
        tabs.addTab(self._logger_tab, "Логгер")

        self.setCentralWidget(tabs)

        # Serial port lock: оба таба уведомляют друг друга
        self._config_tab.serial_lock.connect(self._on_serial_lock)
        self._logger_tab.serial_lock.connect(self._on_serial_lock)

    def _on_serial_lock(self, locked: bool) -> None:
        sender = self.sender()
        if sender is not self._config_tab:
            self._config_tab.set_serial_locked(locked)
        if sender is not self._logger_tab:
            self._logger_tab.set_serial_locked(locked)

    def closeEvent(self, event) -> None:
        self._server_tab.shutdown()
        self._logger_tab.shutdown()
        event.accept()


# ══════════════════════════════════════════════════════════════════════ entry point

def main() -> None:
    db = Database(DATABASE)
    db.init_schema()

    app = QApplication(sys.argv)
    win = MainWindow(db)
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
