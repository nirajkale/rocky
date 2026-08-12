"""TCP client for the Jetson Maestro JSON-line pipe (jetson/server.py)."""

from __future__ import annotations

import json
import os
import socket
import sys
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from commons.schema import COMMAND, Request, Response

DEFAULT_HOST = os.environ.get("ROCKY_JETSON_HOST", "192.168.3.23")
DEFAULT_PORT = int(os.environ.get("ROCKY_JETSON_PORT", "9000"))
DEFAULT_TIMEOUT_S = float(os.environ.get("ROCKY_JETSON_TIMEOUT", "5"))

# Left-side channels (L1/L2/L3). Matches jetson/maestro.py wiring.
_LEFT_INVERT_CHANNELS = frozenset({3, 4, 5, 11, 12, 13, 14, 16, 17})
_LEFT_INVERT_JOINTS = frozenset(
    {
        "L1.coxa",
        "L1.femur",
        "L1.tibia",
        "L2.coxa",
        "L2.femur",
        "L2.tibia",
        "L3.coxa",
        "L3.femur",
        "L3.tibia",
    }
)


def _angle_for_joint(
    *, angle: float, name: str | None = None, position: int | None = None
) -> float:
    """Invert left-side joints so logical angles match right-side pose."""
    invert = False
    if name is not None:
        invert = name in _LEFT_INVERT_JOINTS
    elif position is not None:
        invert = int(position) in _LEFT_INVERT_CHANNELS
    if invert:
        return 180.0 - float(angle)
    return float(angle)


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
        self._buf = b""

    def close(self) -> None:
        if self._sock is not None:
            try:
                self._sock.close()
            except OSError:
                pass
        self._sock = None
        self._buf = b""

    def _ensure_connected(self) -> socket.socket:
        if self._sock is None:
            sock = socket.create_connection((self.host, self.port), timeout=self.timeout)
            sock.settimeout(self.timeout)
            self._sock = sock
            self._buf = b""
        return self._sock

    def _readline(self, sock: socket.socket) -> str:
        while b"\n" not in self._buf:
            chunk = sock.recv(4096)
            if not chunk:
                raise ConnectionError("Jetson TCP pipe closed")
            self._buf += chunk
        line, self._buf = self._buf.split(b"\n", 1)
        return line.decode("utf-8")

    def request(self, payload: Request | dict[str, Any]) -> Any:
        req = payload if isinstance(payload, Request) else Request.parse(payload)
        if req.cmd == COMMAND.SET_SERVO_ANGLE_BY_NAME and req.angle is not None:
            req.angle = _angle_for_joint(angle=req.angle, name=req.name)
        elif req.cmd == COMMAND.SET_SERVO_ANGLE_BY_POSITION and req.angle is not None:
            req.angle = _angle_for_joint(angle=req.angle, position=req.position)
        try:
            sock = self._ensure_connected()
            sock.sendall((json.dumps(req.to_dict()) + "\n").encode())
            response = self._readline(sock)
            resp = Response.parse(json.loads(response))
        except Exception:
            self.close()
            raise

        if not resp.ok:
            raise RuntimeError(resp.error or "Jetson command failed")
        return resp.result

    def ping(self) -> Any:
        return self.request(Request(COMMAND.PING))

    def get_servo_positions(self) -> Any:
        return self.request(Request(COMMAND.GET_SERVO_POSITIONS))

    def set_servo_angle_by_name(
        self,
        name: str,
        angle: float,
        speed: int | None = None,
        acceleration: int | None = None,
    ) -> Any:
        return self.request(
            Request(
                COMMAND.SET_SERVO_ANGLE_BY_NAME,
                name=name,
                angle=angle,
                speed=speed,
                acceleration=acceleration,
            )
        )

    def set_servo_angle_by_position(
        self,
        position: int,
        angle: float,
        speed: int | None = None,
        acceleration: int | None = None,
    ) -> Any:
        return self.request(
            Request(
                COMMAND.SET_SERVO_ANGLE_BY_POSITION,
                position=position,
                angle=angle,
                speed=speed,
                acceleration=acceleration,
            )
        )
