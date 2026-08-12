"""
Named FIFO → Jetson TCP bridge.

Creates /tmp/rocky-commands.fifo if needed. Each JSON line written to the
FIFO is forwarded to the Jetson TCP pipe. On exit the FIFO is removed so
its presence means the bridge is listening.

  echo '{"cmd":"ping"}' > /tmp/rocky-commands.fifo
  echo '{"cmd":"set_servo_angle_by_name","name":"R1.coxa","angle":90}' > /tmp/rocky-commands.fifo

  python main.py
"""

from __future__ import annotations

import json
import os
import signal
import stat
import time
from pathlib import Path

from jetson_tcp import JetsonTcpClient

DEFAULT_FIFO = "/tmp/rocky-commands.fifo"
FIFO_PATH = Path(os.environ.get("ROCKY_CMD_FIFO", DEFAULT_FIFO))


def ensure_fifo(path: Path) -> None:
    if path.exists():
        if not stat.S_ISFIFO(path.stat().st_mode):
            raise SystemExit(f"{path} exists and is not a FIFO")
        return
    os.mkfifo(path)


def remove_fifo(path: Path) -> None:
    try:
        if path.exists() and stat.S_ISFIFO(path.stat().st_mode):
            path.unlink()
    except OSError:
        pass


def main() -> None:
    ensure_fifo(FIFO_PATH)
    client = JetsonTcpClient()
    print(f"reading {FIFO_PATH.resolve()} → {client.host}:{client.port}", flush=True)

    def _stop(_signum=None, _frame=None) -> None:
        raise SystemExit(0)

    signal.signal(signal.SIGTERM, _stop)

    try:
        while True:
            # Open blocks until a writer connects; reopen after writers leave.
            with FIFO_PATH.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        payload = json.loads(line)
                        result = client.request(payload)
                        print(f"ok {payload.get('cmd')}: {result}", flush=True)
                    except Exception as exc:
                        print(f"fail {line!r}: {exc}", flush=True)
            time.sleep(0.05)
    except (KeyboardInterrupt, SystemExit):
        print("\nShutting down.", flush=True)
    finally:
        client.close()
        remove_fifo(FIFO_PATH)


if __name__ == "__main__":
    main()
