#!/usr/bin/env bash
set -Eeuo pipefail

repo=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
tmp=$(mktemp -d)

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
    ./check.sh >/dev/null 2>&1
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

cleanup() {
  kill "$DUMMY_PID" "$HTTP_PID" 2>/dev/null || true
  rm -rf -- "$tmp"
}
trap cleanup EXIT

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

echo "999999" > "$tmp/shm/qemu.pid"
if run_check; then
  echo "FAIL: Expected non-zero exit status when qemu.pid process does not exist" >&2
  exit 1
fi

# Scenario 4: QEMU process alive and NETWORK=N -> exit 0
echo "$DUMMY_PID" > "$tmp/shm/qemu.pid"
if ! NETWORK=N run_check; then
  echo "FAIL: Expected exit 0 when QEMU is alive and NETWORK=N" >&2
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
if ! NETWORK=Y DHCP=N run_check; then
  echo "FAIL: Expected exit 0 when HTTP request succeeds" >&2
  exit 1
fi

echo "Synthetic health check regression tests passed."
