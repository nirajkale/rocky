"""Shared JSON-line request/response schema (stdlib; works on Jetson 3.6+)."""

from enum import Enum


class COMMAND(Enum):
    PING = "ping"
    GET_SERVO_POSITIONS = "get_servo_positions"
    SET_SERVO_ANGLE_BY_NAME = "set_servo_angle_by_name"
    SET_SERVO_ANGLE_BY_POSITION = "set_servo_angle_by_position"


class Request(object):
    def __init__(
        self, cmd, name=None, angle=None, position=None, speed=None, acceleration=None
    ):
        if isinstance(cmd, COMMAND):
            self.cmd = cmd
        else:
            self.cmd = COMMAND(cmd)
        self.name = name
        self.angle = angle
        self.position = position
        self.speed = speed
        self.acceleration = acceleration

    @classmethod
    def parse(cls, obj):
        if not isinstance(obj, dict):
            raise TypeError("request must be a JSON object")
        if "cmd" not in obj or obj["cmd"] is None:
            raise ValueError("missing cmd")
        try:
            req = cls(
                cmd=obj["cmd"],
                name=obj.get("name"),
                angle=obj.get("angle"),
                position=obj.get("position"),
                speed=obj.get("speed"),
                acceleration=obj.get("acceleration"),
            )
        except ValueError:
            raise ValueError(f"unknown cmd {obj.get('cmd')!r}")
        return req.validate()

    def validate(self):
        if self.cmd == COMMAND.SET_SERVO_ANGLE_BY_NAME:
            if self.name is None:
                raise ValueError("name is required")
            if self.angle is None:
                raise ValueError("angle is required")
        if self.cmd == COMMAND.SET_SERVO_ANGLE_BY_POSITION:
            if self.position is None:
                raise ValueError("position is required")
            if self.angle is None:
                raise ValueError("angle is required")
        if self.speed is not None:
            # Compact Protocol encodes speed as 14-bit (0 = unlimited).
            self.speed = _validate_int_range(self.speed, "speed", 0, 16383)
        if self.acceleration is not None:
            # Maestro docs: acceleration is 0-255 (0 = unlimited).
            self.acceleration = _validate_int_range(
                self.acceleration, "acceleration", 0, 255
            )
        return self

    def to_dict(self):
        out = {"cmd": self.cmd.value}
        if self.name is not None:
            out["name"] = self.name
        if self.angle is not None:
            out["angle"] = self.angle
        if self.position is not None:
            out["position"] = self.position
        if self.speed is not None:
            out["speed"] = self.speed
        if self.acceleration is not None:
            out["acceleration"] = self.acceleration
        return out


def _validate_int_range(value, field, lo, hi):
    try:
        n = int(value)
    except (TypeError, ValueError):
        raise ValueError(f"{field} must be an integer {lo}-{hi}")
    if not (lo <= n <= hi):
        raise ValueError(f"{field} must be an integer {lo}-{hi}")
    return n


class Response(object):
    def __init__(self, ok, result=None, error=None):
        self.ok = ok
        self.result = result
        self.error = error

    @classmethod
    def ok_result(cls, result):
        return cls(ok=True, result=result)

    @classmethod
    def from_error(cls, error):
        return cls(ok=False, error=str(error))

    @classmethod
    def parse(cls, obj):
        if not isinstance(obj, dict):
            raise TypeError("invalid response from Jetson (not an object)")
        return cls(ok=bool(obj.get("ok")), result=obj.get("result"), error=obj.get("error"))

    def to_dict(self):
        out = {"ok": self.ok}
        if self.ok:
            out["result"] = self.result
        else:
            out["error"] = self.error
        return out
