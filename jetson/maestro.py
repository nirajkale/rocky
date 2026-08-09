"""Shared Pololu Mini Maestro UART control + Rocky joint channel map.

Used by the interactive CSV CLI (main.py) and the Jetson TCP pipe (server.py).
Kept compatible with Jetson system Python 3.6.
"""

import time

import serial

# --- Serial settings. Must match the Maestro's configuration. ---
DEFAULT_PORT = "/dev/ttyTHS1"
BAUD_RATE = 9600
AUTO_DETECT_BAUD = True

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

# Maestro channel (0-17) -> joint name. Hand-verified wiring.
CHANNEL_TO_JOINT = {
    0: "R1.tibia",
    1: "R1.coxa",
    2: "R1.femur",
    3: "L1.tibia",
    4: "L1.femur",
    5: "L1.coxa",
    6: "R2.femur",
    7: "R3.coxa",
    8: "R3.femur",
    9: "R2.coxa",
    10: "R2.tibia",
    11: "L2.tibia",
    12: "L3.coxa",
    13: "L2.coxa",
    14: "L3.femur",
    15: "R3.tibia",
    16: "L3.tibia",
    17: "L2.femur",
}

JOINT_TO_CHANNEL = {name: ch for ch, name in CHANNEL_TO_JOINT.items()}

# By-leg view of the same map (coxa / femur / tibia channel indices).
LEG_CHANNELS = {
    "R1": {"coxa": 1, "femur": 2, "tibia": 0},
    "R2": {"coxa": 9, "femur": 6, "tibia": 10},
    "R3": {"coxa": 7, "femur": 8, "tibia": 15},
    "L1": {"coxa": 5, "femur": 4, "tibia": 3},
    "L2": {"coxa": 13, "femur": 17, "tibia": 11},
    "L3": {"coxa": 12, "femur": 14, "tibia": 16},
}


def clamp_angle(angle_deg):
    return max(MIN_ANGLE, min(MAX_ANGLE, float(angle_deg)))


def validate_channel(channel):
    channel = int(channel)
    if not (0 <= channel <= 17):
        raise ValueError("channel/position must be 0-17 for an 18-channel Maestro")
    return channel


def resolve_joint_name(name):
    """Return canonical joint name; raise ValueError if unknown."""
    if name not in JOINT_TO_CHANNEL:
        known = ", ".join(sorted(JOINT_TO_CHANNEL.keys()))
        raise ValueError(f"unknown joint name {name!r}; expected one of: {known}")
    return name


def servo_position_map():
    """Mapping payload for LLMs / callers: channels, names, and by-leg view."""
    return {
        "channel_to_joint": dict(CHANNEL_TO_JOINT),
        "joint_to_channel": dict(JOINT_TO_CHANNEL),
        "legs": dict(LEG_CHANNELS),
        "angle_range": {"min": MIN_ANGLE, "max": MAX_ANGLE},
        "notes": (
            "Call get_servo_positions first. Joint names look like 'R1.coxa'. "
            f"Angles are degrees in [{MIN_ANGLE}, {MAX_ANGLE}]. "
            "Channels are Maestro indices 0-17."
        ),
    }


class MaestroController:
    """Minimal wrapper around the Maestro Compact Protocol over pyserial."""

    def __init__(
        self,
        port=DEFAULT_PORT,
        baudrate=BAUD_RATE,
        timeout=1,
        detect_baud=AUTO_DETECT_BAUD,
        speed=SPEED,
        acceleration=ACCELERATION,
    ):
        self.ser = serial.Serial(port, baudrate, timeout=timeout)
        self.speed = speed
        self.acceleration = acceleration
        if detect_baud:
            # Required by the Maestro's "detect baud rate" UART mode.
            self.ser.write(bytes([0xAA]))
            self.ser.flush()
            time.sleep(0.05)

    def close(self):
        if self.ser.is_open:
            self.ser.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def _send(self, cmd, channel, value):
        """value is a 14-bit number, sent as two 7-bit bytes (low, high)."""
        value = max(0, min(0x3FFF, int(value)))
        low = value & 0x7F
        high = (value >> 7) & 0x7F
        self.ser.write(bytes([cmd, channel, low, high]))
        self.ser.flush()

    def set_target(self, channel, angle_deg):
        """Move channel to angle_deg (0-180), converted to quarter-us pulse."""
        channel = validate_channel(channel)
        angle_deg = clamp_angle(angle_deg)
        pulse_us = MIN_PULSE_US + (angle_deg - MIN_ANGLE) * (
            MAX_PULSE_US - MIN_PULSE_US
        ) / (MAX_ANGLE - MIN_ANGLE)
        target_qus = int(pulse_us * 4)  # Maestro target units = 0.25us
        self._send(0x84, channel, target_qus)
        return angle_deg

    def set_speed(self, channel, speed):
        self._send(0x87, validate_channel(channel), speed)

    def set_acceleration(self, channel, accel):
        self._send(0x89, validate_channel(channel), accel)

    def apply(self, channel, angle_deg, speed=None, accel=None):
        """Set speed/accel then target so the move obeys them."""
        if speed is None:
            speed = self.speed
        if accel is None:
            accel = self.acceleration
        channel = validate_channel(channel)
        self.set_speed(channel, speed)
        self.set_acceleration(channel, accel)
        angle = self.set_target(channel, angle_deg)
        return {
            "channel": channel,
            "joint": CHANNEL_TO_JOINT.get(channel),
            "angle": angle,
            "speed": speed,
            "acceleration": accel,
        }

    def set_angle_by_position(self, position, angle):
        return self.apply(position, angle)

    def set_angle_by_name(self, name, angle):
        name = resolve_joint_name(name)
        return self.apply(JOINT_TO_CHANNEL[name], angle)
