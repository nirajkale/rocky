"""
Jetson Nano -> Pololu Mini Maestro 18-Channel Servo Controller (UART / TTL serial)

Wiring (Jetson Nano 40-pin header):
    Nano pin 6  (GND)      -> Maestro GND
    Nano pin 8  (UART TXD) -> Maestro RX
    [optional, for reading back]
    Nano pin 10 (UART RXD) <- Maestro TX

    NOTE: This is one-way as wired above (TX only). Commands work fine;
    reading servo positions / error flags requires the optional RX line.
    The Nano's 3.3V logic drives the Maestro's RX input fine.

Maestro configuration (set once via Maestro Control Center):
    Serial Settings -> Serial mode: "UART, fixed baud rate"
      -> then set AUTO_DETECT_BAUD = False in maestro.py, and match BAUD_RATE.
    or  Serial mode: "UART, detect baud rate"
      -> then leave AUTO_DETECT_BAUD = True (sends 0xAA on startup).

Terminal input is CSV:
    servo_num,angle

Speed and acceleration are fixed globally (see SPEED / ACCELERATION in maestro.py)
and applied to every move.

Example:
    0,90      -> channel 0 to 90 degrees
    1,0       -> channel 1 to 0 degrees

Usage:
    python3 jetson/main.py --port /dev/ttyTHS1 --baud 9600
"""

import argparse
import os
import sys

import serial

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from maestro import (
    ACCELERATION,
    BAUD_RATE,
    DEFAULT_PORT,
    SPEED,
    MaestroController,
    validate_channel,
)


def parse_csv_line(line):
    parts = [p.strip() for p in line.split(",")]
    if len(parts) != 2:
        raise ValueError("expected 2 values: servo_num,angle")
    servo_num = validate_channel(int(float(parts[0])))
    angle = float(parts[1])
    return servo_num, angle


def main():
    parser = argparse.ArgumentParser(
        description="Control Maestro servos over UART via CSV input from the terminal"
    )
    parser.add_argument(
        "--port", default=DEFAULT_PORT, help="Serial port (Jetson UART)"
    )
    parser.add_argument("--baud", type=int, default=BAUD_RATE, help="Baud rate")
    parser.add_argument(
        "--no-baud-detect",
        action="store_true",
        help="Skip the 0xAA byte (use when Maestro is in fixed-baud UART mode)",
    )
    args = parser.parse_args()

    try:
        maestro = MaestroController(
            args.port, args.baud, detect_baud=not args.no_baud_detect
        )
    except serial.SerialException as e:
        print(f"Failed to open serial port {args.port}: {e}")
        sys.exit(1)

    print(f"Connected on {args.port} @ {args.baud} baud")
    print("Enter: servo_num,angle")
    print(f"  angle: 0-180 deg | speed={SPEED} accel={ACCELERATION} (fixed globally)")
    print("Type 'q' to quit.\n")

    try:
        while True:
            line = input("> ").strip()
            if not line:
                continue
            if line.lower() in ("q", "quit", "exit"):
                break
            try:
                servo_num, angle = parse_csv_line(line)
                result = maestro.apply(servo_num, angle)
                print(
                    "  -> servo {} ({}): angle={}".format(
                        result["channel"], result["joint"], result["angle"]
                    )
                )
            except ValueError as e:
                print(f"  Invalid input: {e}")
    except (KeyboardInterrupt, EOFError):
        print("\nExiting.")
    finally:
        maestro.close()


if __name__ == "__main__":
    main()
