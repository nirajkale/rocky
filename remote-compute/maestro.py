"""Small pyserial adapter for a Pololu Maestro controller."""

from __future__ import annotations

import serial


class Controller:
    """Control a Maestro over any transparent serial connection."""

    def __init__(
        self,
        port: str,
        *,
        baudrate: int = 9600,
        device_number: int = 12,
        timeout: float = 1.0,
    ) -> None:
        if not 0 <= device_number <= 127:
            raise ValueError("device_number must be between 0 and 127")

        self._device_number = device_number
        self._serial = serial.Serial(
            port=port,
            baudrate=baudrate,
            timeout=timeout,
            write_timeout=timeout,
        )

    @staticmethod
    def _split_14_bit(value: int) -> tuple[int, int]:
        if not 0 <= value <= 0x3FFF:
            raise ValueError("value must be between 0 and 16383")
        return value & 0x7F, (value >> 7) & 0x7F

    def _send_command(self, command: int, *parameters: int) -> None:
        packet = bytes(
            [0xAA, self._device_number, command, *parameters]
        )
        self._serial.write(packet)
        self._serial.flush()

    def set_target(self, channel: int, target: int) -> None:
        low, high = self._split_14_bit(target)
        self._send_command(0x04, channel, low, high)

    def set_speed(self, channel: int, speed: int) -> None:
        low, high = self._split_14_bit(speed)
        self._send_command(0x07, channel, low, high)

    def set_acceleration(self, channel: int, acceleration: int) -> None:
        if not 0 <= acceleration <= 255:
            raise ValueError("acceleration must be between 0 and 255")
        low, high = self._split_14_bit(acceleration)
        self._send_command(0x09, channel, low, high)

    def close(self) -> None:
        self._serial.close()

    def __enter__(self) -> Controller:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
