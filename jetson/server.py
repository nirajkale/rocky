"""
Jetson TCP pipe for Maestro servo control (Python 3.6+).

One JSON object per line in, one JSON object per line out.
Keeps a single MaestroController open for the process lifetime.

Commands:
  {"cmd":"ping"}
  {"cmd":"get_servo_positions"}
  {"cmd":"set_servo_angle_by_name","name":"R1.coxa","angle":90}
  {"cmd":"set_servo_angle_by_position","position":1,"angle":90}

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
import socketserver
import sys
import threading

import serial

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from maestro import (
    BAUD_RATE,
    DEFAULT_PORT,
    MaestroController,
    servo_position_map,
)

DEFAULT_TCP_HOST = "0.0.0.0"
DEFAULT_TCP_PORT = 9000

_maestro = None
_maestro_lock = threading.Lock()


def get_maestro():
    if _maestro is None:
        raise RuntimeError("Maestro controller is not open")
    return _maestro


def open_maestro(port, baud, detect_baud):
    global _maestro
    _maestro = MaestroController(port, baud, detect_baud=detect_baud)
    return _maestro


def handle_request(obj):
    """Dispatch one request dict; return result or raise."""
    if not isinstance(obj, dict):
        raise TypeError("request must be a JSON object")
    cmd = obj.get("cmd")
    print(f"cmd: {cmd}", flush=True)
    if not cmd:
        raise ValueError("missing cmd")

    if cmd == "ping":
        return {"pong": True}

    if cmd == "get_servo_positions":
        return servo_position_map()

    if cmd == "set_servo_angle_by_name":
        name = obj.get("name")
        if name is None:
            raise ValueError("name is required")
        angle = obj.get("angle")
        if angle is None:
            raise ValueError("angle is required")
        with _maestro_lock:
            return get_maestro().set_angle_by_name(name, angle)

    if cmd == "set_servo_angle_by_position":
        position = obj.get("position")
        if position is None:
            raise ValueError("position is required")
        angle = obj.get("angle")
        if angle is None:
            raise ValueError("angle is required")
        with _maestro_lock:
            return get_maestro().set_angle_by_position(position, angle)

    raise ValueError(f"unknown cmd {cmd!r}")


class JsonLineHandler(socketserver.StreamRequestHandler):
    def handle(self):
        peer = f"{self.client_address[0]}:{self.client_address[1]}"
        print(f"client connected {peer}", flush=True)
        try:
            while True:
                raw = self.rfile.readline()
                if not raw:
                    break
                line = raw.decode("utf-8", errors="replace").strip()
                if not line:
                    continue
                try:
                    req = json.loads(line)
                    result = handle_request(req)
                    resp = {"ok": True, "result": result}
                except (ValueError, TypeError, KeyError, OSError, RuntimeError) as exc:
                    resp = {"ok": False, "error": str(exc)}
                out = (json.dumps(resp, separators=(",", ":")) + "\n").encode("utf-8")
                self.wfile.write(out)
                self.wfile.flush()
        finally:
            print(f"client disconnected {peer}", flush=True)


class ThreadedTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True
    daemon_threads = True


def parse_args():
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
    return parser.parse_args()


def main():
    args = parse_args()
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

    server = ThreadedTCPServer((args.host, args.port), JsonLineHandler)
    print(
        f"TCP pipe listening on {args.host}:{args.port} (JSON lines)",
        flush=True,
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.", flush=True)
    finally:
        server.server_close()
        if _maestro is not None:
            _maestro.close()


if __name__ == "__main__":
    main()
