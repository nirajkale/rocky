"""
Rocky hexapod MCP server (FastMCP, HTTP transport) — runs on the Mac / remote-compute host.

Talks to the Jetson Maestro TCP pipe (jetson/server.py).

Requires Python 3.10+ and: uv sync  (or pip install "fastmcp[code-mode]")

Usage:
  cd remote-compute && uv run python mcp_server.py
  ROCKY_JETSON_HOST=192.168.3.23 ROCKY_JETSON_PORT=9000 uv run python mcp_server.py

Endpoint: http://127.0.0.1:8000/mcp
"""

from __future__ import annotations

import argparse
import atexit
import os
from typing import Any

from fastmcp import FastMCP
from fastmcp.experimental.transforms.code_mode import CodeMode, GetSchemas, ListTools

from jetson_tcp import DEFAULT_HOST, DEFAULT_PORT, JetsonTcpClient

DEFAULT_MCP_HOST = "127.0.0.1"
DEFAULT_MCP_PORT = 8000

_client: JetsonTcpClient | None = None


def get_client() -> JetsonTcpClient:
    if _client is None:
        raise RuntimeError("Jetson TCP client is not configured")
    return _client


mcp = FastMCP(
    "Rocky Servo Control",
    instructions=(
        "Control Rocky the hexapod's 18 Maestro servos via the Jetson TCP pipe. "
        "Always call get_servo_positions first to learn channel↔joint mappings "
        "and valid joint names (e.g. R1.coxa). Angles are degrees 0–180. "
        "With CodeMode, list tools then execute Python that call_tool(...)'s these APIs."
    ),
    transforms=[
        CodeMode(discovery_tools=[ListTools(), GetSchemas()]),
    ],
)


@mcp.tool
def get_servo_positions() -> dict[str, Any]:
    """Return Maestro channel ↔ joint mappings for Rocky.

    Call this first before setting any angles. Returns channel_to_joint,
    joint_to_channel, per-leg coxa/femur/tibia channels, and angle limits.
    """
    return get_client().get_servo_positions()


@mcp.tool
def set_servo_angle_by_name(name: str, angle: float) -> dict[str, Any]:
    """Set a servo angle by joint name (e.g. 'R1.coxa', 'L2.tibia').

    name must be one of the joint names from get_servo_positions().
    angle must be between 0 and 180 degrees.
    """
    return get_client().set_servo_angle_by_name(name, angle)


@mcp.tool
def set_servo_angle_by_position(position: int, angle: float) -> dict[str, Any]:
    """Set a servo angle by Maestro channel index.

    position must be 0–17. angle must be between 0 and 180 degrees.
    Prefer set_servo_angle_by_name when you know the joint name.
    """
    return get_client().set_servo_angle_by_position(position, angle)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Rocky FastMCP server (Mac) → Jetson TCP Maestro pipe"
    )
    parser.add_argument(
        "--host",
        default=os.environ.get("ROCKY_MCP_HOST", DEFAULT_MCP_HOST),
        help="MCP HTTP bind host",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("ROCKY_MCP_PORT", DEFAULT_MCP_PORT)),
        help="MCP HTTP listen port",
    )
    parser.add_argument(
        "--jetson-host",
        default=os.environ.get("ROCKY_JETSON_HOST", DEFAULT_HOST),
        help="Jetson TCP pipe host",
    )
    parser.add_argument(
        "--jetson-port",
        type=int,
        default=int(os.environ.get("ROCKY_JETSON_PORT", str(DEFAULT_PORT))),
        help="Jetson TCP pipe port (default 9000)",
    )
    parser.add_argument(
        "--skip-ping",
        action="store_true",
        help="Do not ping Jetson on startup",
    )
    return parser.parse_args()


def main() -> None:
    global _client
    args = parse_args()
    _client = JetsonTcpClient(host=args.jetson_host, port=args.jetson_port)
    atexit.register(_client.close)

    if not args.skip_ping:
        try:
            _client.ping()
            print(
                f"Jetson TCP OK at {args.jetson_host}:{args.jetson_port}",
                flush=True,
            )
        except OSError as exc:
            print(
                f"Warning: could not reach Jetson at "
                f"{args.jetson_host}:{args.jetson_port}: {exc}",
                flush=True,
            )

    print(f"MCP HTTP listening on http://{args.host}:{args.port}/mcp", flush=True)
    mcp.run(transport="http", host=args.host, port=args.port)


if __name__ == "__main__":
    main()
