"""
Jetson TCP pipe for Maestro servo control (Python 3.6+).

One JSON object per line in, one JSON object per line out.
Keeps a single MaestroController open for the process lifetime.

Commands:
  {"cmd":"ping"}
  {"cmd":"get_servo_positions"}
  {"cmd":"set_servo_angle_by_name","name":"R1.coxa","angle":90}
  {"cmd":"set_servo_angle_by_position","position":1,"angle":90}
  Optional on set cmds: "speed" (0-16383, default 32), "acceleration" (0-255, default 5)

Replies:
  {"ok":true,"result":...}
  {"ok":false,"error":"..."}

Usage:
  python3 jetson/server.py
  python3 jetson/server.py --host 0.0.0.0 --port 9000 --port-serial /dev/ttyTHS1
"""

import argparse
import json
import os
import socket
import sys

import serial

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, ".."))
sys.path.insert(0, _HERE)
sys.path.insert(0, _ROOT)

from commons.schema import COMMAND, Request, Response
from maestro import (
    BAUD_RATE,
    DEFAULT_PORT,
    MaestroController,
    servo_position_map,
)

DEFAULT_TCP_HOST = "0.0.0.0"
DEFAULT_TCP_PORT = 9000

_maestro = None


def get_maestro():
    if _maestro is None:
        raise RuntimeError("Maestro controller is not open")
    return _maestro


def open_maestro(port, baud, detect_baud):
    global _maestro
    _maestro = MaestroController(port, baud, detect_baud=detect_baud)
    return _maestro


def readline(conn, buf):
    """Read until \\n. Returns (line_str_or_None, leftover_buf). None = closed."""
    while b"\n" not in buf:
        chunk = conn.recv(4096)
        if not chunk:
            return None, buf
        buf += chunk
    line, buf = buf.split(b"\n", 1)
    return line.decode("utf-8", "replace").strip(), buf


def dispatch(req):
    print(f"cmd: {json.dumps(req.to_dict(), sort_keys=True)}", flush=True)

    if req.cmd == COMMAND.PING:
        return {"pong": True}

    if req.cmd == COMMAND.GET_SERVO_POSITIONS:
        return servo_position_map()

    if req.cmd == COMMAND.SET_SERVO_ANGLE_BY_NAME:
        return get_maestro().set_angle_by_name(
            req.name, req.angle, speed=req.speed, acceleration=req.acceleration
        )

    if req.cmd == COMMAND.SET_SERVO_ANGLE_BY_POSITION:
        return get_maestro().set_angle_by_position(
            req.position, req.angle, speed=req.speed, acceleration=req.acceleration
        )

    raise ValueError(f"unknown cmd {req.cmd!r}")


def handle_client(conn, addr):
    peer = f"{addr[0]}:{addr[1]}"
    print(f"client connected {peer}", flush=True)
    buf = b""
    try:
        while True:
            line, buf = readline(conn, buf)
            if line is None:
                break
            if not line:
                continue
            # print(f"recv: {line}", flush=True)
            try:
                result = dispatch(Request.parse(json.loads(line)))
                resp = Response.ok_result(result)
            except (ValueError, TypeError, KeyError, OSError, RuntimeError) as exc:
                resp = Response.from_error(exc)
            out = json.dumps(resp.to_dict())
            # print(f"send: {out}", flush=True)
            conn.sendall((out + "\n").encode("utf-8"))
    finally:
        conn.close()
        print(f"client disconnected {peer}", flush=True)


def main():
    parser = argparse.ArgumentParser(
        description="Rocky Maestro TCP pipe server (Jetson)"
    )
    parser.add_argument(
        "--host",
        default=os.environ.get("ROCKY_TCP_HOST", DEFAULT_TCP_HOST),
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("ROCKY_TCP_PORT", DEFAULT_TCP_PORT)),
        help="TCP listen port (default 9000)",
    )
    parser.add_argument(
        "--port-serial",
        default=os.environ.get("ROCKY_SERIAL_PORT", DEFAULT_PORT),
        help="Maestro UART device",
    )
    parser.add_argument(
        "--baud",
        type=int,
        default=int(os.environ.get("ROCKY_SERIAL_BAUD", BAUD_RATE)),
    )
    parser.add_argument(
        "--no-baud-detect",
        action="store_true",
        help="Skip 0xAA baud-detect byte",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Listen on TCP without opening the serial port",
    )
    args = parser.parse_args()

    if not args.dry_run:
        try:
            open_maestro(
                args.port_serial, args.baud, detect_baud=not args.no_baud_detect
            )
        except serial.SerialException as exc:
            print(f"Failed to open serial {args.port_serial}: {exc}")
            sys.exit(1)
        print(
            f"Maestro open on {args.port_serial} @ {args.baud} baud",
            flush=True,
        )
    else:
        print("Dry-run: serial port not opened", flush=True)

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((args.host, args.port))
    server.listen(1)
    print(
        f"TCP pipe listening on {args.host}:{args.port} (JSON lines)",
        flush=True,
    )
    try:
        while True:
            conn, addr = server.accept()
            handle_client(conn, addr)
    except KeyboardInterrupt:
        print("\nShutting down.", flush=True)
    finally:
        server.close()
        if _maestro is not None:
            _maestro.close()


if __name__ == "__main__":
    main()
