#!/usr/bin/env bash
set -Eeuo pipefail

repo=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
tmp=$(mktemp -d)

DUMMY_PID=''
HTTP_PID=''
cleanup() {
  local pid
  for pid in "$DUMMY_PID" "$HTTP_PID"; do
    if [[ -n "$pid" ]]; then
      kill "$pid" 2>/dev/null || true
      wait "$pid" 2>/dev/null || true
    fi
  done
  rm -rf -- "$tmp"
}
trap cleanup EXIT


mkdir -p "$tmp/shm"

cat > "$tmp/utils.sh" <<'MOCK_UTILS'
disabled() {
  case "${1:-}" in
    [Nn]*|[Ff]*|0|[Oo][Ff][Ff]) return 0 ;;
    *) return 1 ;;
  esac
}

enabled() {
  case "${1:-}" in
    [Yy]*|[Tt]*|1|[Oo][Nn]) return 0 ;;
    *) return 1 ;;
  esac
}
MOCK_UTILS

sed "s|/run|$tmp|g" "$repo/src/check.sh" > "$tmp/check.sh"
chmod +x "$tmp/check.sh"

run_check() {
  (
    cd "$tmp"
    # Persist observations across the check.sh subprocess; a shell counter in
    # this parent would not see requests made by the child.
    curl() {
      printf '%s\n' "$*" >> "$HEALTHCHECK_REQUEST_LOG"
      command curl "$@"
    }
    export -f curl
    HEALTHCHECK_REQUEST_LOG="$tmp/http-requests.log" ./check.sh >/dev/null 2>&1
  )
}

sleep 300 &
DUMMY_PID=$!

HTTP_PORT=$(python3 -c 'import socket; s = socket.socket(); s.bind(("127.0.0.1", 0)); print(s.getsockname()[1]); s.close()')
python3 -m http.server "$HTTP_PORT" --bind 127.0.0.1 >/dev/null 2>&1 &
HTTP_PID=$!

# Wait for HTTP server to start
for _ in {1..50}; do
  if curl -m 1 -s -o /dev/null "http://127.0.0.1:$HTTP_PORT/"; then
    break
  fi
  sleep 0.1
done
if ! kill -0 "$HTTP_PID" 2>/dev/null || ! curl -m 1 -fsS -o /dev/null "http://127.0.0.1:$HTTP_PORT/"; then
  echo "FAIL: HTTP fixture did not start" >&2
  exit 1
fi

# Scenario 1: qemu.end exists -> non-zero
touch "$tmp/shm/qemu.end"
if run_check; then
  echo "FAIL: Expected non-zero exit status when qemu.end exists" >&2
  exit 1
fi
rm -f "$tmp/shm/qemu.end"

# Scenario 2: PID file missing or empty -> non-zero
rm -f "$tmp/shm/qemu.pid"
if run_check; then
  echo "FAIL: Expected non-zero exit status when qemu.pid is missing" >&2
  exit 1
fi

touch "$tmp/shm/qemu.pid"
if run_check; then
  echo "FAIL: Expected non-zero exit status when qemu.pid is empty" >&2
  exit 1
fi

# Scenario 3: PID file exists but process does not exist or format is invalid -> non-zero
for invalid_pid in "-123" "0" "abc" "123a" " 999999 "; do
  echo "$invalid_pid" > "$tmp/shm/qemu.pid"
  if run_check; then
    echo "FAIL: Expected non-zero exit status for invalid PID '$invalid_pid'" >&2
    exit 1
  fi
done

# Embedded whitespace must not turn an invalid value into a live PID.
# Disable networking so a missing dsm.url cannot hide a PID-validation bug.
for invalid_pid in "${DUMMY_PID:0:1} ${DUMMY_PID:1}" " ${DUMMY_PID}" "${DUMMY_PID} " \
                   "${DUMMY_PID:0:1}"$'\t'"${DUMMY_PID:1}" "${DUMMY_PID:0:1}"$'\n'"${DUMMY_PID:1}"; do
  printf '%s\n' "$invalid_pid" > "$tmp/shm/qemu.pid"
  if NETWORK=N run_check; then
    echo "FAIL: Accepted whitespace in a live PID" >&2
    exit 1
  fi
done

echo "999999" > "$tmp/shm/qemu.pid"
if run_check; then
  echo "FAIL: Expected non-zero exit status when qemu.pid process does not exist" >&2
  exit 1
fi

# Scenario 4: QEMU process alive and NETWORK=N -> exit 0 without HTTP
echo "$DUMMY_PID" > "$tmp/shm/qemu.pid"
echo "127.0.0.1:$HTTP_PORT" > "$tmp/shm/dsm.url"
: > "$tmp/http-requests.log"
if ! NETWORK=N run_check; then
  echo "FAIL: Expected exit 0 when QEMU is alive and NETWORK=N" >&2
  exit 1
fi
if [[ -s "$tmp/http-requests.log" ]]; then
  echo "FAIL: NETWORK=N must not make an HTTP request" >&2
  exit 1
fi

# Scenario 5: QEMU process alive, NETWORK=Y, but dsm.url missing/empty -> non-zero
rm -f "$tmp/shm/dsm.url"
if NETWORK=Y run_check; then
  echo "FAIL: Expected non-zero exit status when dsm.url is missing" >&2
  exit 1
fi

touch "$tmp/shm/dsm.url"
if NETWORK=Y run_check; then
  echo "FAIL: Expected non-zero exit status when dsm.url is empty" >&2
  exit 1
fi

# Scenario 6: HTTP request fails -> non-zero; HTTP request succeeds -> exit 0
echo "127.0.0.1:1" > "$tmp/shm/dsm.url"
echo "127.0.0.1" > "$tmp/shm/qemu.gw"
if NETWORK=Y DHCP=N run_check; then
  echo "FAIL: Expected non-zero exit status when HTTP request fails" >&2
  exit 1
fi

echo "127.0.0.1:$HTTP_PORT" > "$tmp/shm/dsm.url"
: > "$tmp/http-requests.log"
if ! NETWORK=Y DHCP=N run_check; then
  echo "FAIL: Expected exit 0 when HTTP request succeeds" >&2
  exit 1
fi

# Positive control: the observer must record the enabled-network request.
if [[ ! -s "$tmp/http-requests.log" ]]; then
  echo "FAIL: HTTP request observer did not record the enabled-network check" >&2
  exit 1
fi

echo "Synthetic health check regression tests passed."
