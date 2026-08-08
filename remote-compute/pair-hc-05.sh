#!/usr/bin/env bash
#
# Pair (and verify) an HC-05 Bluetooth module on macOS using blueutil.
#
# Flow:
#   1. Remove any existing HC-05 pairing to clear stale macOS SPP state.
#   2. Scan continuously until HC-05 appears, then pair it again.
#   3. Open the serial port briefly to verify the data link (the HC-05 LED
#      slows to a ~2s blink while the port is open), then close it.
#   4. Print SUCCESS with the address, or FAILURE.

set -euo pipefail

DEVICE_NAME="HC-05"
PIN="1234"            # Some HC-05 clones use "0000"
SCAN_DURATION=5       # Seconds per inquiry sweep
PORT="/dev/cu.${DEVICE_NAME}"
CONNECT_HOLD=10       # Seconds to hold the port open (watch for the slow blink)
PORT_WAIT=15          # Seconds to wait for macOS to create the serial port

if ! command -v blueutil >/dev/null 2>&1; then
  echo "Error: blueutil is not installed. Install it with: brew install blueutil"
  exit 1
fi

# Extract the address for DEVICE_NAME from a blueutil listing (paired or inquiry).
# Prints the address on stdout, or nothing if not found.
find_address() {
  echo "$1" \
    | grep "name: \"${DEVICE_NAME}\"" \
    | sed -E 's/^address: ([0-9a-fA-F:-]+),.*/\1/' \
    | head -n 1
}

echo "Checking for an existing ${DEVICE_NAME} pairing..."
old_address="$(find_address "$(blueutil --paired)" || true)"

if [ -n "${old_address}" ]; then
  echo "Removing existing pairing at ${old_address}..."
  blueutil --disconnect "${old_address}" >/dev/null 2>&1 || true
  if ! blueutil --unpair "${old_address}"; then
    echo "FAILURE: could not remove the existing pairing at ${old_address}"
    exit 1
  fi
  sleep 1
else
  echo "No existing ${DEVICE_NAME} pairing found."
fi

echo "Scanning for ${DEVICE_NAME} (make sure it is powered and blinking fast)..."
attempt=0
while true; do
  attempt=$((attempt + 1))
  echo "Scan attempt ${attempt} (${SCAN_DURATION}s)..."
  address="$(find_address "$(blueutil --inquiry "${SCAN_DURATION}")" || true)"
  if [ -n "${address}" ]; then
    echo "Found ${DEVICE_NAME} at ${address}"
    break
  fi
  echo "${DEVICE_NAME} not found yet, scanning again..."
done

echo "Pairing with ${address} using PIN ${PIN}..."
if ! blueutil --pair "${address}" "${PIN}"; then
  echo "FAILURE: could not pair with ${DEVICE_NAME} at ${address}"
  exit 1
fi
echo "Paired with ${address}"

echo "Waiting for macOS to create ${PORT}..."
for ((second = 1; second <= PORT_WAIT; second++)); do
  if [ -e "${PORT}" ]; then
    break
  fi
  sleep 1
done

# The HC-05 only shows the slow "connected" blink when the RFCOMM/SPP serial
# channel is actually opened. blueutil --connect brings up the low-level link
# but does not open that channel, so we verify by opening the serial port
# itself. macOS establishes the link on open and tears it down on close.
echo "Verifying the data link by opening ${PORT} for ${CONNECT_HOLD}s..."
echo "(The ${DEVICE_NAME} LED should slow to a ~2s blink while the port is open.)"

if [ ! -e "${PORT}" ]; then
  echo "FAILURE: paired with ${DEVICE_NAME} at ${address}, but ${PORT} did not appear within ${PORT_WAIT}s"
  exit 1
fi

if sleep "${CONNECT_HOLD}" 3<>"${PORT}"; then
  blueutil --disconnect "${address}" >/dev/null 2>&1 || true
  echo "SUCCESS: ${DEVICE_NAME} is paired and the data link opened at ${address} (${PORT})"
  exit 0
else
  blueutil --disconnect "${address}" >/dev/null 2>&1 || true
  echo "FAILURE: ${DEVICE_NAME} is paired at ${address} but ${PORT} could not be opened"
  exit 1
fi
