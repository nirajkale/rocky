# Rocky control protocol

Write **one JSON command per line** to:

`/tmp/rocky-commands.fifo`

Each command must end with a newline. Multiple commands in one write are fine as long as each is its own line (shell: `echo '...' > /tmp/rocky-commands.fifo`).

There is **no reply through the FIFO**. Outcome appears only in the bridge process logs. Assume success unless told otherwise; on failure the bridge logs an error string.

If `/tmp/rocky-commands.fifo` does not exist, the bridge is not listening. The bridge creates the FIFO on start and deletes it on clean exit (Ctrl-C / SIGTERM), do not create or delete this yourself

---

## Request

One JSON object per line.

| Field | Type | When required |
|-------|------|----------------|
| `cmd` | string | always |
| `name` | string | `set_servo_angle_by_name` |
| `position` | integer | `set_servo_angle_by_position` (`0`–`17`) |
| `angle` | number | both set commands | degrees, **valid range `0`–`180`** |

Unknown fields are ignored. Extra whitespace around the line is fine; the payload must be valid JSON with double-quoted keys/strings.

### `angle`

- Type: number (int or float)
- Valid range: **`0` to `180`** (degrees)
- Values outside that range are **clamped** to `0` or `180` (not rejected)
- `90` is mid-stroke / neutral in pulse space; physical pose still depends on horn alignment

---

## Commands

### `ping`

```json
{"cmd":"ping"}
```

**Success `result`:** `{"pong": true}`

### `get_servo_positions`

```json
{"cmd":"get_servo_positions"}
```

**Success `result`:** object with:

- `channel_to_joint`: map of channel string/int → joint name
- `joint_to_channel`: map of joint name → channel

### `set_servo_angle_by_name`

```json
{"cmd":"set_servo_angle_by_name","name":"R1.coxa","angle":90}
```

| Field | Type | Required |
|-------|------|----------|
| `name` | string | yes |
| `angle` | number (`0`–`180`) | yes |

**Joint `name` format:** `{leg}.{joint}`

| Legs | Meaning |
|------|---------|
| `L1` `L2` `L3` | left front, mid, back |
| `R1` `R2` `R3` | right front, mid, back |

| Joint | Role |
|-------|------|
| `coxa` | hip yaw |
| `femur` | hip pitch |
| `tibia` | knee pitch |

Valid examples: `R1.coxa`, `L2.femur`, `R3.tibia`.

**Success `result`:** status object from the servo apply (includes joint/channel/angle details).

### `set_servo_angle_by_position`

```json
{"cmd":"set_servo_angle_by_position","position":1,"angle":90}
```

| Field | Type | Required |
|-------|------|----------|
| `position` | integer | yes (`0`–`17`, Maestro channel) |
| `angle` | number (`0`–`180`) | yes |

**Success `result`:** status object from the servo apply.

---

## Wire response shape (for reference)

The Jetson answers each command with one JSON line (logged by the bridge, not written back to the FIFO):

**Success**

```json
{"ok":true,"result":<any>}
```

**Failure**

```json
{"ok":false,"error":"<message>"}
```

### Common `error` strings

| `error` | Meaning |
|---------|---------|
| `missing cmd` | no `cmd` |
| `unknown cmd '...'` | unsupported `cmd` |
| `name is required` | set-by-name missing `name` |
| `position is required` | set-by-position missing `position` |
| `angle is required` | set command missing `angle` |
| `unknown joint '...'` | invalid `name` |
| connection / timeout text | robot/Jetson unreachable |

---

## Channel ↔ joint map

| Ch | Joint | Ch | Joint |
|----|-------|----|-------|
| 0 | `R1.tibia` | 9 | `R2.coxa` |
| 1 | `R1.coxa` | 10 | `R2.tibia` |
| 2 | `R1.femur` | 11 | `L2.tibia` |
| 3 | `L1.tibia` | 12 | `L3.coxa` |
| 4 | `L1.femur` | 13 | `L2.coxa` |
| 5 | `L1.coxa` | 14 | `L3.femur` |
| 6 | `R2.femur` | 15 | `R3.tibia` |
| 7 | `R3.coxa` | 16 | `L3.tibia` |
| 8 | `R3.femur` | 17 | `L2.femur` |

---

## Shell examples

```bash
echo '{"cmd":"ping"}' > /tmp/rocky-commands.fifo

echo '{"cmd":"get_servo_positions"}' > /tmp/rocky-commands.fifo

echo '{"cmd":"set_servo_angle_by_name","name":"R1.coxa","angle":90}' > /tmp/rocky-commands.fifo

echo '{"cmd":"set_servo_angle_by_position","position":1,"angle":45}' > /tmp/rocky-commands.fifo
```

## Control notes

- One JSON object per line (newline-terminated). Several lines in one write are OK.
- Prefer named joints (`set_servo_angle_by_name`) over raw channels unless mapping is intentional.
- Valid angles are `0`–`180`; out-of-range values are clamped.
- Same angle on two joints may not look identical until servo horns/neutrals are aligned.
- Invalid JSON or validation errors fail that command only; keep sending further commands as needed.
