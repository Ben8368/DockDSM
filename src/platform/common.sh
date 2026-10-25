#!/usr/bin/env bash
# Platform policy is selected before qemux initialization, never from ARCH.
set -Eeuo pipefail

platformInit() {
  : "${DSM_PLATFORM:=virtualdsm}"
  case "$DSM_PLATFORM" in
    virtualdsm|rtd1619b) ;;
    *) printf 'Unknown DSM_PLATFORM: %s (expected virtualdsm or rtd1619b)\n' "$DSM_PLATFORM" >&2; return 64 ;;
  esac
  local directory
  directory=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
  # This path comes exclusively from the whitelist above.
  # shellcheck source=/dev/null
  . "$directory/$DSM_PLATFORM.sh"
  # uname runs inside the container; it cannot identify the Docker host's CPU.
  CONTAINER_ARCH=$(uname -m)
  case "$CONTAINER_ARCH" in
    x86_64) CONTAINER_ARCH=amd64 ;;
    aarch64) CONTAINER_ARCH=arm64 ;;
  esac
  platformDefaults
  DSM_PLATFORM="$DSM_PLATFORM" GUEST_ARCH="$GUEST_ARCH" \
    PLATFORM="$PLATFORM" QEMU_BIN="$QEMU_BIN" \
    MACHINE="$MACHINE" BOOT_MODE="$BOOT_MODE" \
    python3 "$directory/legacy_provider.py" --check-env
}

platformValidateBinary() {
  # No user-controlled executable or shell command is accepted.
  case "$GUEST_ARCH:$QEMU_BIN" in
    amd64:qemu-system-x86_64|arm64:qemu-system-aarch64) ;;
    *) error 'Invalid platform QEMU executable'; return 64 ;;
  esac
  command -v "$QEMU_BIN" >/dev/null || { error "Missing platform emulator: $QEMU_BIN"; return 69; }
}
