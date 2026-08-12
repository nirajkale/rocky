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
| `speed` | integer | optional on both set commands | Maestro speed limit `0`–`16383` (default **`32`**) |
| `acceleration` | integer | optional on both set commands | Maestro accel limit `0`–`255` (default **`5`**) |

Unknown fields are ignored. Extra whitespace around the line is fine; the payload must be valid JSON with double-quoted keys/strings.

### `angle`

- Type: number (int or float)
- Valid range: **`0` to `180`** (degrees)
- Values outside that range are **clamped** to `0` or `180` (not rejected)
- `90` is mid-stroke / neutral in pulse space; physical pose still depends on horn alignment

### `speed` / `acceleration`

Optional per-move limits on `set_servo_angle_by_name` and `set_servo_angle_by_position`. Omitted → Jetson defaults **`speed: 32`**, **`acceleration: 5`**. Units assume the Maestro’s default **20 ms** servo period (Pololu Maestro User’s Guide §4.b / Set Speed & Set Acceleration in §5.e).

#### `speed`

- Type: integer **`0`–`16383`** (Compact Protocol 14-bit field; `0` = unlimited)
- Unit: **`(0.25 µs) / (10 ms)`** — max change in pulse width every 10 ms
- Higher = faster pulse slewing; `1` is very slow (~40 s to move a 1 ms pulse span)
- Does **not** make a mechanical servo faster than it can physically move

| Value | Max pulse change | Rough time for 1000 µs travel (full 1→2 ms) |
|-------|------------------|-----------------------------------------------|
| `0` | unlimited | as fast as the servo allows |
| `1` | 0.25 µs / 10 ms | ~40 s |
| `32` (default) | 8 µs / 10 ms (= 800 µs/s) | ~1.25 s |
| `140` (Pololu example) | 35 µs / 10 ms (= 3.5 µs/ms) | ~286 ms |

#### `acceleration`

- Type: integer **`0`–`255`** (Maestro documented range; `0` = no accel limit)
- Unit: **`(0.25 µs) / (10 ms) / (80 ms)`** — how fast the *speed* itself may ramp
- With both limits set, the channel ramps up to the speed cap, then ramps down near the target (smoother motion)

| Value | Meaning |
|-------|---------|
| `0` | no acceleration limit (jump straight to speed limit) |
| `5` (default) | gentle ramp |
| `255` | fastest allowed ramp under the Maestro accel command |

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

```json
{"cmd":"set_servo_angle_by_name","name":"R1.coxa","angle":90,"speed":64,"acceleration":10}
```

| Field | Type | Required |
|-------|------|----------|
| `name` | string | yes |
| `angle` | number (`0`–`180`) | yes |
| `speed` | integer (`0`–`16383`) | no (default `32`) |
| `acceleration` | integer (`0`–`255`) | no (default `5`) |

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
| `speed` | integer (`0`–`16383`) | no (default `32`) |
| `acceleration` | integer (`0`–`255`) | no (default `5`) |

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
| `speed must be an integer 0-16383` | invalid optional `speed` |
| `acceleration must be an integer 0-255` | invalid optional `acceleration` |
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

echo '{"cmd":"set_servo_angle_by_name","name":"R1.coxa","angle":45,"speed":64,"acceleration":10}' > /tmp/rocky-commands.fifo

echo '{"cmd":"set_servo_angle_by_position","position":1,"angle":45}' > /tmp/rocky-commands.fifo
```

## Understanding Speed & Acceleration

These fields do **not** command motor RPM. They tell the Maestro how fast to **slew the PWM pulse width** toward the new target. The servo then tries to follow that pulse. Real motion is also limited by the servo gearing, supply voltage, and mechanical load — so a high `speed` will not make a stalled or weak servo move faster than physics allows.

Rocky maps **0°–180° → 1000–2000 µs** pulse (`jetson/maestro.py`). That is **~5.556 µs per degree**. All timing below assumes the Maestro’s default **20 ms** servo period.

### What `speed` means

| Property | Value |
|----------|--------|
| Range | `0`–`16383` (`0` = unlimited / jump as fast as the channel allows) |
| Unit | `(0.25 µs) / (10 ms)` |
| Formula | pulse slew rate = `speed × 25` µs/s |
| Angle rate (Rocky pulse map) | ≈ `speed × 4.5` °/s |

**Sample: what `speed: 1` means in angle**

- Maestro allows the pulse to change by at most **0.25 µs every 10 ms** → **25 µs/s**
- On Rocky’s map (**5.556 µs ≈ 1°**), that is about **4.5 °/s**
- So a joint commanded from **0° → 180°** at `speed: 1` (and no accel limit) takes about **40 seconds**
- A **90°** move takes about **20 seconds**

```text
1 speed unit  ≈  4.5 degrees per second
N speed units ≈  N × 4.5 °/s
```

Quick checks: `speed: 10` ≈ 45 °/s; default `speed: 32` ≈ 144 °/s; `speed: 0` = uncapped.

**Worked examples** (constant speed, ignoring acceleration ramps):

| `speed` | Pulse slew | ~Angle rate | Time for 90° (500 µs) | Time for 180° (1000 µs) |
|---------|------------|-------------|------------------------|-------------------------|
| `0` | unlimited | servo max | as fast as hardware | as fast as hardware |
| `1` | 25 µs/s | **~4.5 °/s** | ~20 s | ~40 s |
| `8` | 200 µs/s | ~36 °/s | ~2.5 s | ~5 s |
| `16` | 400 µs/s | ~72 °/s | ~1.25 s | ~2.5 s |
| `32` (default) | 800 µs/s | ~144 °/s | ~0.63 s | ~1.25 s |
| `64` | 1600 µs/s | ~288 °/s | ~0.31 s | ~0.63 s |
| `140` | 3500 µs/s | ~630 °/s | ~0.14 s | ~0.29 s |

**Pick a value from a desired duration:**

```text
speed ≈ (Δangle_deg × 5.556) / (desired_seconds × 25)
      ≈ Δangle_deg / (desired_seconds × 4.5)
```

Example: move **90°** in about **1 second** → `speed ≈ 90 / 4.5 ≈ 20`.

### What `acceleration` means

| Property | Value |
|----------|--------|
| Range | `0`–`255` (`0` = no accel limit; jump straight to the speed cap) |
| Unit | `(0.25 µs) / (10 ms) / (80 ms)` |
| Effect | Ramps the *commanded* speed up at the start and down near the target |

**Sample: what `acceleration: 1` means in angle**

Acceleration does not set a cruise rate in °/s. It sets how fast that cruise rate is **allowed to change**.

- Maestro may increase/decrease the speed setting by **1 speed unit every 80 ms**
- 1 speed unit ≈ **4.5 °/s**, so every 80 ms the angle-rate limit may change by ~4.5 °/s
- That is about **56 °/s²** of angular acceleration on Rocky’s pulse map

```text
1 acceleration unit  ≈  56 degrees per second²
N acceleration units ≈  N × 56 °/s²
```

Quick checks:

| `acceleration` | ~Angular accel | Time to ramp from rest up to `speed: 32` (~144 °/s) |
|----------------|----------------|------------------------------------------------------|
| `0` | unlimited (instant) | 0 (jumps to speed cap) |
| `1` | ~56 °/s² | `(32 / 1) × 0.08 s` ≈ **2.6 s** |
| `5` (default) | ~281 °/s² | `(32 / 5) × 0.08 s` ≈ **0.51 s** |
| `20` | ~1125 °/s² | `(32 / 20) × 0.08 s` ≈ **0.13 s** |
| `255` | ~14 300 °/s² | `(32 / 255) × 0.08 s` ≈ **0.01 s** |

```text
ramp_time_seconds ≈ (speed / acceleration) × 0.08
```

With both `speed` and `acceleration` non-zero, the Maestro produces a trapezoid (or triangle) in pulse space: accelerate → cruise at `speed` → decelerate into the target. That looks smoother and puts less shock into the legs than a hard step in pulse width.

Rule of thumb:

- **`acceleration: 0`** — square velocity profile; snappy but jerky
- **Low (`1`–`10`)** — long soft ramp; good for careful posing / calibration
- **Default `5`** — gentle for bench work (~0.5 s to reach default `speed: 32`)
- **Higher (`20`–`80`)** — reaches cruise sooner; better when you want the move to mostly follow the `speed` timing above
- **`255`** — fastest ramp the accel command allows (still softer than `0` if `speed` is finite)

Acceleration does **not** raise the top speed. If moves feel “stuck soft” at the start/end, raise `acceleration` (or set it to `0`) before raising `speed`.

### How to calibrate (recommended)

Do this on a **single joint** with the robot supported so a fall cannot damage legs. Prefer named joints.

1. **Baseline** — move mid → mid±45° with defaults and watch:

   ```bash
   echo '{"cmd":"set_servo_angle_by_name","name":"R1.coxa","angle":90}' > /tmp/rocky-commands.fifo
   echo '{"cmd":"set_servo_angle_by_name","name":"R1.coxa","angle":45,"speed":32,"acceleration":5}' > /tmp/rocky-commands.fifo
   ```

2. **Isolate speed** — set `"acceleration":0` (or a high value like `80`) so ramps do not dominate timing. Change only `speed` between trials (`8`, `16`, `32`, `64`…). Time or visually judge a fixed Δangle (e.g. 45→135).

3. **Match a target duration** — use the formula above, then round to a nearby integer and re-test. Remember: if the servo cannot physically keep up, increasing `speed` further does nothing useful.

4. **Add smoothness** — once `speed` feels right, bring `acceleration` back down until the start/stop look acceptable without making the move obviously longer than you want.

5. **Per-joint notes** — coxa (yaw) often tolerates higher `speed` than femur/tibia under load. Calibrate the slowest/heavily loaded joints first, then reuse those limits (or slightly faster) for lighter joints.

6. **Multi-joint moves** — when several channels move together, use the **same** `speed`/`acceleration` on each command if you want them to finish roughly together for equal angle deltas. Different Δangles still finish at different times at the same `speed`.

### Safety / practical tips

- Start **slower than you think** (`8`–`16`) when a leg is near the ground or the body is not supported.
- `speed: 0` plus `acceleration: 0` is an immediate pulse jump — useful for testing mapping, risky on a standing hexapod.
- These limits live on the **Maestro channel** until changed again; each Rocky set command re-applies whatever `speed`/`acceleration` you send (or the defaults if omitted).
- Units change if you ever reconfigure the Maestro servo **period** away from 20 ms (see Pololu guide §4.b). Rocky assumes the default period.

## Control notes

- One JSON object per line (newline-terminated). Several lines in one write are OK.
- Prefer named joints (`set_servo_angle_by_name`) over raw channels unless mapping is intentional.
- Valid angles are `0`–`180`; out-of-range values are clamped.
- Optional `speed` / `acceleration` override per move; omit for defaults (`32` / `5`). See **Understanding Speed & Acceleration** above.
- Same angle on two joints may not look identical until servo horns/neutrals are aligned.
- Invalid JSON or validation errors fail that command only; keep sending further commands as needed.
