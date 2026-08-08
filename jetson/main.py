#!/usr/bin/env python3
"""
Jetson Nano -> Pololu Mini Maestro 18-Channel USB Servo Controller

Talks to the Maestro over USB (pyserial) using the Compact Protocol and
lets you drive servos by typing CSV lines in the terminal:

    servo_num,angle

Speed and acceleration are fixed globally (see SPEED / ACCELERATION below)
and applied to every move.

Example:
    0,90      -> channel 0 to 90 degrees
    1,0       -> channel 1 to 0 degrees

Setup notes (Maestro Control Center, on a PC first):
  - Serial Settings -> Serial mode: "USB Dual Port" (or "USB Chained")
    so the command port accepts Compact Protocol bytes directly.
  - On Linux/Jetson the command port usually shows up as /dev/ttyACM0.
  - Run `ls /dev/ttyACM*` after plugging in to confirm the port.

Usage:
    python3 maestro_control.py --port /dev/ttyACM0
"""

import sys
import argparse
import serial

# --- Pulse range in microseconds. Adjust to match your servos' spec. ---
MIN_PULSE_US = 1000
MAX_PULSE_US = 2000
MIN_ANGLE = 0
MAX_ANGLE = 180

# --- Global speed/acceleration applied to every move. ---
# speed: 0 = unlimited, else 1-255 (units of 0.25us per 10ms)
# acceleration: 0 = unlimited, else 1-255 (units of 0.25us per 10ms per 80ms)
SPEED = 32
ACCELERATION = 5


class MaestroController:
    """Minimal wrapper around the Maestro Compact Protocol over pyserial."""

    def __init__(self, port, baudrate=9600, timeout=1):
        # Baud rate is irrelevant over native USB but pyserial requires one.
        self.ser = serial.Serial(port, baudrate, timeout=timeout)

    def close(self):
        if self.ser.is_open:
            self.ser.close()

    def _send(self, cmd, channel, value):
        """value is a 14-bit number, sent as two 7-bit bytes (low, high)."""
        value = max(0, min(0x3FFF, int(value)))
        low = value & 0x7F
        high = (value >> 7) & 0x7F
        self.ser.write(bytes([cmd, channel, low, high]))

    def set_target(self, channel, angle_deg):
        """Move channel to angle_deg (0-180), converted to quarter-us pulse."""
        angle_deg = max(MIN_ANGLE, min(MAX_ANGLE, angle_deg))
        pulse_us = MIN_PULSE_US + (angle_deg - MIN_ANGLE) * (
            MAX_PULSE_US - MIN_PULSE_US
        ) / (MAX_ANGLE - MIN_ANGLE)
        target_qus = int(pulse_us * 4)  # Maestro target units = 0.25us
        self._send(0x84, channel, target_qus)

    def set_speed(self, channel, speed):
        """0 = unlimited, else 1-255 (units of 0.25us per 10ms)."""
        self._send(0x87, channel, speed)

    def set_acceleration(self, channel, accel):
        """0 = unlimited, else 1-255 (units of 0.25us per 10ms per 80ms)."""
        self._send(0x89, channel, accel)

    def apply(self, channel, angle_deg, speed, accel):
        # Set speed/accel before target so the move obeys them.
        self.set_speed(channel, speed)
        self.set_acceleration(channel, accel)
        self.set_target(channel, angle_deg)


def parse_csv_line(line):
    parts = [p.strip() for p in line.split(",")]
    if len(parts) != 2:
        raise ValueError("expected 2 values: servo_num,angle")
    servo_num = int(float(parts[0]))
    angle = float(parts[1])
    if not (0 <= servo_num <= 17):
        raise ValueError("servo_num must be 0-17 for an 18-channel Maestro")
    return servo_num, angle


def main():
    parser = argparse.ArgumentParser(
        description="Control Maestro servos via CSV input from the terminal"
    )
    parser.add_argument(
        "--port", default="/dev/ttyACM0", help="Maestro command serial port"
    )
    parser.add_argument("--baud", type=int, default=9600, help="Baud rate (unused over USB)")
    args = parser.parse_args()

    try:
        maestro = MaestroController(args.port, args.baud)
    except serial.SerialException as e:
        print(f"Failed to open serial port {args.port}: {e}")
        sys.exit(1)

    print(f"Connected to Maestro on {args.port}")
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
                maestro.apply(servo_num, angle, SPEED, ACCELERATION)
                print(f"  -> servo {servo_num}: angle={angle}")
            except ValueError as e:
                print(f"  Invalid input: {e}")
    except (KeyboardInterrupt, EOFError):
        print("\nExiting.")
    finally:
        maestro.close()


if __name__ == "__main__":
    main()