"""TCP client for the Jetson Maestro JSON-line pipe (jetson/server.py)."""

from __future__ import annotations

import json
import os
import socket
import threading
from typing import Any

DEFAULT_HOST = os.environ.get("ROCKY_JETSON_HOST", "192.168.3.23")
DEFAULT_PORT = int(os.environ.get("ROCKY_JETSON_PORT", "9000"))
DEFAULT_TIMEOUT_S = float(os.environ.get("ROCKY_JETSON_TIMEOUT", "5"))


class JetsonTcpClient:
    """Persistent JSON-line client to the Jetson TCP servo pipe."""

    def __init__(
        self,
        host: str = DEFAULT_HOST,
        port: int = DEFAULT_PORT,
        timeout: float = DEFAULT_TIMEOUT_S,
    ) -> None:
        self.host = host
        self.port = port
        self.timeout = timeout
        self._sock: socket.socket | None = None
        self._rfile: Any = None
        self._wfile: Any = None
        self._lock = threading.Lock()

    def close(self) -> None:
        with self._lock:
            self._close_unlocked()

    def _close_unlocked(self) -> None:
        for stream in (self._rfile, self._wfile):
            if stream is not None:
                try:
                    stream.close()
                except OSError:
                    pass
        self._rfile = None
        self._wfile = None
        if self._sock is not None:
            try:
                self._sock.close()
            except OSError:
                pass
        self._sock = None

    def _ensure_connected(self) -> None:
        if self._sock is not None:
            return
        sock = socket.create_connection((self.host, self.port), timeout=self.timeout)
        sock.settimeout(self.timeout)
        self._sock = sock
        self._rfile = sock.makefile("r", encoding="utf-8", newline="\n")
        self._wfile = sock.makefile("w", encoding="utf-8", newline="\n")

    def request(self, payload: dict[str, Any]) -> Any:
        with self._lock:
            try:
                self._ensure_connected()
                assert self._wfile is not None and self._rfile is not None
                self._wfile.write(json.dumps(payload, separators=(",", ":")) + "\n")
                self._wfile.flush()
                line = self._rfile.readline()
                if not line:
                    raise ConnectionError("Jetson TCP pipe closed")
                resp = json.loads(line)
            except Exception:
                self._close_unlocked()
                raise

            if not isinstance(resp, dict):
                raise TypeError("invalid response from Jetson (not an object)")
            if not resp.get("ok"):
                raise RuntimeError(resp.get("error") or "Jetson command failed")
            return resp.get("result")

    def ping(self) -> Any:
        return self.request({"cmd": "ping"})

    def get_servo_positions(self) -> Any:
        return self.request({"cmd": "get_servo_positions"})

    def set_servo_angle_by_name(self, name: str, angle: float) -> Any:
        return self.request(
            {"cmd": "set_servo_angle_by_name", "name": name, "angle": angle}
        )

    def set_servo_angle_by_position(self, position: int, angle: float) -> Any:
        return self.request(
            {
                "cmd": "set_servo_angle_by_position",
                "position": position,
                "angle": angle,
            }
        )
