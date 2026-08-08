#!/usr/bin/env python3
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
      -> then set AUTO_DETECT_BAUD = False below, and match BAUD_RATE.
    or  Serial mode: "UART, detect baud rate"
      -> then leave AUTO_DETECT_BAUD = True (sends 0xAA on startup).

Terminal input is CSV:
    servo_num,angle

Speed and acceleration are fixed globally (see SPEED / ACCELERATION below)
and applied to every move.

Example:
    0,90      -> channel 0 to 90 degrees
    1,0       -> channel 1 to 0 degrees

Usage:
    python3 maestro_control.py --port /dev/ttyTHS1 --baud 9600
"""

import sys
import time
import argparse
import serial

# --- Serial settings. Must match the Maestro's configuration. ---
DEFAULT_PORT = "/dev/ttyTHS1"   # Jetson Nano UART on header pins 8/10
BAUD_RATE = 9600
AUTO_DETECT_BAUD = True         # True if Maestro is in "detect baud rate" mode

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

    def __init__(self, port, baudrate=BAUD_RATE, timeout=1, detect_baud=AUTO_DETECT_BAUD):
        self.ser = serial.Serial(port, baudrate, timeout=timeout)
        if detect_baud:
            # Required by the Maestro's "detect baud rate" UART mode.
            # Harmless to omit if the Maestro uses a fixed baud rate.
            self.ser.write(bytes([0xAA]))
            self.ser.flush()
            time.sleep(0.05)

    def close(self):
        if self.ser.is_open:
            self.ser.close()

    def _send(self, cmd, channel, value):
        """value is a 14-bit number, sent as two 7-bit bytes (low, high)."""
        value = max(0, min(0x3FFF, int(value)))
        low = value & 0x7F
        high = (value >> 7) & 0x7F
        self.ser.write(bytes([cmd, channel, low, high]))
        self.ser.flush()

    def set_target(self, channel, angle_deg):
        """Move channel to angle_deg (0-180), converted to quarter-us pulse."""
        angle_deg = max(MIN_ANGLE, min(MAX_ANGLE, angle_deg))
        pulse_us = MIN_PULSE_US + (angle_deg - MIN_ANGLE) * (
            MAX_PULSE_US - MIN_PULSE_US
        ) / (MAX_ANGLE - MIN_ANGLE)
        target_qus = int(pulse_us * 4)  # Maestro target units = 0.25us
        self._send(0x84, channel, target_qus)

    def set_speed(self, channel, speed):
        self._send(0x87, channel, speed)

    def set_acceleration(self, channel, accel):
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
        description="Control Maestro servos over UART via CSV input from the terminal"
    )
    parser.add_argument("--port", default=DEFAULT_PORT, help="Serial port (Jetson UART)")
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