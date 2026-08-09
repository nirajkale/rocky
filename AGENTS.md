# AGENTS.md

Guidance for coding agents working on **Rocky** (robot control: Arduino sketches, Jetson Nano UART → Pololu Mini Maestro, remote-compute helpers).

## Repo map

| Path | Role |
|------|------|
| `arduino/` | Arduino sketches (RF client, etc.) |
| `jetson/` | Jetson Nano Python: UART control of Pololu Mini Maestro |
| `remote-compute/` | Host-side Python helpers (`main.py`, `maestro.py`) |
| `push.sh` | Local helper: commit + push all `*.py` changes (gitignored; may exist only on clone) |

## Goals

### Done

- Jetson ↔ Mini Maestro UART control (`jetson/main.py`) works as user `niraj` on `/dev/ttyTHS1`.
- Maestro channel ↔ joint wiring mapped for all 18 servos; **connections tested and working**.

### In progress / next

- **Servo neutral / angle alignment:** re-position / re-fit each servo horn (or calibration offsets) so that commanded **0°, 90°, and 180° mean the same mechanical pose for each joint type** across all legs (and left/right mirrors as intended). Until this is done, the same angle on two channels can produce different physical orientations.
- After neutrals are consistent, higher-level kinematics / gait code can treat `theta_coxa` / `theta_femur` / `theta_tibia` as comparable across legs.

## Hexapod model

Rocky is a **hexapod**: 6 legs × 3 servos = **18 servos** (Maestro channels `0`–`17`).

### Joint nomenclature

| Everyday name | Servo / link | Role | Angle name |
|---------------|--------------|------|------------|
| Hip joint | **coxa** | hip yaw | `theta_coxa` |
| Second / “knee” (upper) | **femur** | hip pitch | `theta_femur` |
| Near foot | **tibia** | knee pitch | `theta_tibia` |

### Leg labels

| ID | Side / position |
|----|-----------------|
| `L1` | left front |
| `L2` | left mid |
| `L3` | left back |
| `R1` | right front |
| `R2` | right mid |
| `R3` | right back |

Logical joint id form: `{leg}.{joint}` e.g. `R1.coxa`, `L2.tibia` (angles: `theta_coxa` / `theta_femur` / `theta_tibia` on that leg).

### Maestro channel → joint map (as wired)

Physical channel order on the Mini Maestro is **not** tidy by leg. This map is **hand-verified, connections tested, and working**:

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

By leg (same data):

| Leg | coxa | femur | tibia |
|-----|------|-------|-------|
| R1 | 1 | 2 | 0 |
| R2 | 9 | 6 | 10 |
| R3 | 7 | 8 | 15 |
| L1 | 5 | 4 | 3 |
| L2 | 13 | 17 | 11 |
| L3 | 12 | 14 | 16 |

`jetson/main.py` currently takes raw `servo_num,angle` (channel index). Prefer named joints in higher-level code via this map.

## Jetson Nano connection

### Local SSH config (dev machine)

Host alias **`jetson`** should exist in `~/.ssh/config`:

```
Host jetson
  HostName 192.168.3.23
  User niraj
  IdentityFile ~/.ssh/id_ed25519
  AddKeysToAgent yes
  UseKeychain yes
```

- **IP:** `192.168.3.23`
- **User:** `niraj`
- **Hostname on device:** `niraj-desktop` (Ubuntu 18.04 / Jetson L4T, `aarch64`, Python 3.6.9)
- **Auth:** Prefer SSH keys (`ssh-copy-id -i ~/.ssh/id_ed25519.pub jetson`). Password auth may still be required until keys are installed. **Do not commit passwords** into this repo; ask the operator if credentials are needed.
- Non-interactive SSH from agents: use `expect` (macOS has `/usr/bin/expect`) when only password auth is available. `sshpass` is optional and may not be installed.

```bash
ssh jetson
# or non-interactive one-shot:
ssh jetson 'command here'
```

### Repo on the Jetson

Typically cloned at `/home/niraj/rocky`. Pull after local pushes:

```bash
ssh jetson 'cd ~/rocky && git pull'
```

## Jetson UART / `jetson/main.py`

### What it does

`jetson/main.py` drives a **Pololu Mini Maestro** over UART (`/dev/ttyTHS1`, default 9600 baud). Terminal input is CSV: `servo_num,angle`.

```bash
python3 jetson/main.py --port /dev/ttyTHS1 --baud 9600
```

Wiring (Jetson 40-pin): GND → Maestro GND; pin 8 TXD → Maestro RX (optional pin 10 RXD ← Maestro TX).

### Dependency: `pyserial`

Package name is **`pyserial`**; import is `import serial`.

- Installed per-user for `niraj` under `~/.local/lib/python3.6/site-packages` (verified version ~3.5).
- **Root has a separate Python environment.** `sudo su` / root `python3` will not see `niraj`'s packages → `ModuleNotFoundError: No module named 'serial'`.
- Prefer running as **`niraj`**, not root. If root truly needs it: `sudo -H pip3 install pyserial` (avoid polluting user pip cache with bare `sudo pip3`).

### Serial port permissions (`/dev/ttyTHS1`)

Symptom when running as `niraj` without access:

```text
Permission denied: '/dev/ttyTHS1'
```

Expected device after fix: `crw-rw---- root dialout` (mode `660`).

**Persistent setup already applied on this Jetson (reference):**

1. `sudo usermod -aG dialout niraj`
2. Udev rule `/etc/udev/rules.d/99-ttyTHS1.rules`:
   ```
   KERNEL=="ttyTHS1", MODE="0660", GROUP="dialout"
   ```
3. `sudo udevadm control --reload-rules && sudo udevadm trigger`
4. Immediate (until next rule application): `sudo chmod 660 /dev/ttyTHS1 && sudo chgrp dialout /dev/ttyTHS1`

**Group membership only applies after a new login.** Existing shells still lack `dialout` even after `usermod`.

- Log out/in (or new SSH session), confirm with `groups` (must list `dialout`), then run the script.
- Same session workaround: `sg dialout -c 'python3 jetson/main.py --port /dev/ttyTHS1 --baud 9600'`

## Debugging playbook (Jetson)

Work through in order:

1. **Can you SSH as `niraj`?** `ssh jetson` / `ssh niraj@192.168.3.23`
2. **Right user for Python?** Do not use `sudo su` unless necessary. Check: `whoami`, `python3 -c 'import serial; print(serial.__version__)'`
3. **Port exists and mode?** `ls -l /dev/ttyTHS1` — want group `dialout` and group rw (`660` or similar).
4. **In `dialout` in this shell?** `id` / `groups`. If missing but `getent group dialout` lists `niraj`, re-login or use `sg dialout`.
5. **Open the port alone?**  
   `python3 -c "import serial; s=serial.Serial('/dev/ttyTHS1', 9600); print('ok'); s.close()"`
6. **Then run the app** with the same user/group context.

### Agent SSH + sudo note

When automating over SSH with password sudo, prefer an **interactive** `ssh -t` + `expect` session (or `echo <pw> | sudo -S ...` *after* SSH is already authenticated). Nesting `ssh ... "echo pw | sudo -S ..."` often confuses password prompts (SSH vs sudo) and fails.

## Local workflow

- Python changes: from repo root, `./push.sh` or `./push.sh "message"` stages/commits/pushes `*.py` (script may be gitignored locally).
- After pushing, pull on the Jetson before retesting hardware.
- Do not commit secrets (SSH passwords, tokens) into `AGENTS.md` or the tree.
