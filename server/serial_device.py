"""
serial_device.py - Контекст-менеджер для работы с Serial-портом ESP32.

Единый источник констант подключения и низкоуровневых операций чтения/записи.
Используется в config_tool.py и logger.py.
"""

import time

import serial

SERIAL_PORT = "COM5"
BAUD_RATE   = 115200


class SerialDevice:
    """Обёртка над serial.Serial: открывает порт, делает стартовую задержку и закрывает порт."""

    def __init__(self, port: str = SERIAL_PORT, baud: int = BAUD_RATE,
                 serial_timeout: float = 2) -> None:
        self._port    = port
        self._baud    = baud
        self._timeout = serial_timeout
        self._ser: serial.Serial | None = None

    def __enter__(self) -> "SerialDevice":
        self._ser = serial.Serial(self._port, self._baud, timeout=self._timeout)
        time.sleep(2)  # ждём установки соединения
        return self

    def __exit__(self, *_) -> None:
        if self._ser and self._ser.is_open:
            self._ser.close()

    @property
    def port(self) -> str:
        """COM-порт устройства."""
        return self._port

    @property
    def baud(self) -> int:
        """Скорость UART."""
        return self._baud

    @property
    def in_waiting(self) -> int:
        """Количество байт, ожидающих в входном буфере."""
        return self._ser.in_waiting

    # ------------------------------------------------------------------ отправка

    def send(self, cmd: str) -> None:
        """Отправляет команду с CRLF-терминатором."""
        self._ser.write((cmd + "\r\n").encode())

    # ------------------------------------------------------------------ чтение

    def reset_input(self) -> None:
        """Сбрасывает входной буфер порта."""
        self._ser.reset_input_buffer()

    def readline(self) -> str:
        """Читает одну строку из порта (до \\n или таймаута) и возвращает без пробелов по краям."""
        return self._ser.readline().decode("utf-8", errors="ignore").strip()

    def read_available(self) -> str:
        """Читает все байты из входного буфера и возвращает как строку."""
        return self._ser.read(self._ser.in_waiting).decode("utf-8", errors="ignore")

    def wait_for_line(self, prefixes: tuple, timeout: float) -> str | None:
        """Читает строки из Serial, пока одна не начнётся с ожидаемого префикса.

        Буфер вычитывается инкрементально, поэтому он не переполняется, даже если
        устройство временно заблокировано (конверсия датчиков, HTTP-таймаут).
        Возвращает совпавшую строку или None по таймауту.
        """
        prev_timeout = self._ser.timeout
        self._ser.timeout = 0.2
        deadline = time.time() + timeout
        buf = ""
        try:
            while time.time() < deadline:
                chunk = self._ser.read(self._ser.in_waiting or 1).decode("utf-8", errors="ignore")
                if not chunk:
                    continue
                buf += chunk
                while "\n" in buf:
                    line, buf = buf.split("\n", 1)
                    line = line.strip()
                    if any(line.startswith(p) for p in prefixes):
                        return line
            return None
        finally:
            self._ser.timeout = prev_timeout

    def wait_for_block(self, start: str, end: str, timeout: float = 10.0) -> str:
        """Ждёт start-маркер, затем читает всё до end-маркера включительно.

        Выбрасывает TimeoutError, если маркер не появился за timeout секунд.
        """
        self._ser.timeout = timeout
        response = ""
        start_time = time.time()

        while True:
            if time.time() - start_time > timeout:
                raise TimeoutError("Timeout waiting for block start")
            chunk = self._ser.read(1).decode("utf-8", errors="ignore")
            response += chunk
            if start in response:
                _, _, after = response.partition(start)
                break

        block = after
        start_time = time.time()
        while True:
            if time.time() - start_time > timeout:
                raise TimeoutError("Timeout waiting for block end")
            chunk = self._ser.read(1).decode("utf-8", errors="ignore")
            block += chunk
            if end in block:
                return start + block[:block.find(end) + len(end)]
