#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT
set -euo pipefail

: "${FACMAN_PREVIEW_ORCA_MARKER:?FACMAN_PREVIEW_ORCA_MARKER is required}"
: "${FACMAN_PREVIEW_ATSPI_REPORT:?FACMAN_PREVIEW_ATSPI_REPORT is required}"
: "${FACMAN_PREVIEW_ATSPI_RELEASE_FILE:?FACMAN_PREVIEW_ATSPI_RELEASE_FILE is required}"
: "${FACMAN_PREVIEW_WINDOW_NAME:?FACMAN_PREVIEW_WINDOW_NAME is required}"

rm -f -- "${FACMAN_PREVIEW_ORCA_MARKER}" "${FACMAN_PREVIEW_ORCA_MARKER}.log" \
  "${FACMAN_PREVIEW_ATSPI_REPORT}" "${FACMAN_PREVIEW_ATSPI_RELEASE_FILE}"
orca --replace --no-setup >"${FACMAN_PREVIEW_ORCA_MARKER}.log" 2>&1 &
orca_pid=$!
app_pid=""
terminate_child() {
  local pid="$1"
  if [[ -z "${pid}" ]]; then
    return
  fi
  kill "${pid}" 2>/dev/null || true
  sleep 0.25
  kill -KILL "${pid}" 2>/dev/null || true
  wait "${pid}" 2>/dev/null || true
}
cleanup() {
  terminate_child "${app_pid}"
  terminate_child "${orca_pid}"
}
trap cleanup EXIT INT TERM

for _ in {1..20}; do
  kill -0 "${orca_pid}" 2>/dev/null && break
  sleep 0.25
done
if ! kill -0 "${orca_pid}" 2>/dev/null; then
  echo "Orca exited before the GTK accessibility probe" >&2
  exit 1
fi

GTK_THEME=HighContrast \
GTK_MODULES=atk-bridge \
NO_AT_BRIDGE=0 \
"$@" &
app_pid=$!

probe_passed=false
for _ in {1..20}; do
  if ! kill -0 "${app_pid}" 2>/dev/null; then
    break
  fi
  if timeout --signal=KILL 1s \
      /usr/bin/python3 "$(dirname "$0")/gtk_atspi_probe.py" \
      --output "${FACMAN_PREVIEW_ATSPI_REPORT}" \
      --window-name "${FACMAN_PREVIEW_WINDOW_NAME}"; then
    probe_passed=true
    break
  fi
  sleep 0.25
done
if [[ "${probe_passed}" != true ]]; then
  echo "External AT-SPI query did not find the FacMan window, Launch Deck, and Play role" >&2
  exit 1
fi
if ! kill -0 "${orca_pid}" 2>/dev/null; then
  echo "Orca exited during the external AT-SPI query" >&2
  exit 1
fi
printf 'orca_pid=%s\n' "${orca_pid}" >"${FACMAN_PREVIEW_ORCA_MARKER}"
: >"${FACMAN_PREVIEW_ATSPI_RELEASE_FILE}"
wait "${app_pid}"
app_pid=""
