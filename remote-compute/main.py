import serial

from maestro import Controller


PORT = "/dev/cu.HC-05"
BAUDRATE = 9600
DEVICE_NUMBER = 12
CHANNEL_COUNT = 18
MIN_PULSE_US = 800
MAX_PULSE_US = 2500


def parse_command(command: str) -> tuple[int, int, int, int]:
    parts = [part.strip() for part in command.split(",")]
    if len(parts) != 4:
        raise ValueError(
            "expected channel,speed,acceleration,pwmWidth_us"
        )

    try:
        channel, speed, acceleration, pulse_us = map(int, parts)
    except ValueError as error:
        raise ValueError("all four values must be integers") from error

    if not 0 <= channel < CHANNEL_COUNT:
        raise ValueError(f"channel must be between 0 and {CHANNEL_COUNT - 1}")
    if not 0 <= speed <= 0x3FFF:
        raise ValueError("speed must be between 0 and 16383")
    if not 0 <= acceleration <= 255:
        raise ValueError("acceleration must be between 0 and 255")
    if not MIN_PULSE_US <= pulse_us <= MAX_PULSE_US:
        raise ValueError(
            f"pwmWidth_us must be between {MIN_PULSE_US} and {MAX_PULSE_US}"
        )

    return channel, speed, acceleration, pulse_us


def main() -> int:
    try:
        controller = Controller(
            PORT,
            baudrate=BAUDRATE,
            device_number=DEVICE_NUMBER,
        )
    except serial.SerialException as error:
        print(f"Could not open {PORT}: {error}")
        return 1

    print("Connected to Maestro through HC-05")
    print("Enter: channel,speed,acceleration,pwmWidth_us")
    print("Example: 0,20,5,1500")
    print("Press Ctrl-C or Ctrl-D to exit")

    try:
        while True:
            try:
                channel, speed, acceleration, pulse_us = parse_command(
                    input("> ")
                )
                target = pulse_us * 4

                controller.set_speed(channel, speed)
                controller.set_acceleration(channel, acceleration)
                controller.set_target(channel, target)

                print(
                    f"OK: channel={channel} speed={speed} "
                    f"accel={acceleration} pwmWidth_us={pulse_us} "
                    f"maestro_target={target}"
                )
            except ValueError as error:
                print(f"Error: {error}")
    except (EOFError, KeyboardInterrupt):
        print("\nClosing connection")
    except serial.SerialException as error:
        print(f"\nSerial communication failed: {error}")
        return 1
    finally:
        controller.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
