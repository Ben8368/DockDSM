#!/usr/bin/env bash
set -Eeuo pipefail

usage() {
  echo "Usage: $0 /path/to/Buildroot/output [--uefi /path/to/OVMF_CODE.fd /path/to/OVMF_VARS.fd]" >&2
}
if [[ $# -lt 1 ]]; then usage; exit 2; fi
output_arg=$1
shift
uefi=no
firmware_code=
firmware_vars=
if [[ $# -gt 0 ]]; then
  if [[ $# -ne 3 || $1 != --uefi ]]; then usage; exit 2; fi
  uefi=yes
  firmware_code=$2
  firmware_vars=$3
fi
if [[ ! -d "$output_arg/images" ]]; then usage; exit 2; fi
output=$(cd -- "$output_arg" && pwd -P)
qemu=${QEMU:-qemu-system-x86_64}
timeout_bin=${TIMEOUT:-timeout}
if ! command -v "$timeout_bin" >/dev/null 2>&1 && [[ $timeout_bin == timeout ]] \
  && command -v gtimeout >/dev/null 2>&1; then
  timeout_bin=gtimeout
fi
for tool in "$qemu" "$timeout_bin" python3; do
  command -v "$tool" >/dev/null 2>&1 || {
    echo "ERROR: required command is unavailable: $tool" >&2
    exit 3
  }
done
iso="$output/images/rootfs.iso9660"
[[ -s "$iso" ]] || {
  echo "ERROR: missing or empty test ISO: $iso" >&2
  exit 4
}

run_mode() {
  local mode=$1
  shift
  local log="$output/grub-boot${mode}.log"
  local cmd=(python3 "$(dirname -- "$0")/qemu-plan.py" --execute \
    --qemu "$qemu" --iso "$iso" "$@")
  set +e
  "$timeout_bin" --signal=TERM --kill-after=5s 120s "${cmd[@]}" 2>&1 | tee "$log"
  local qemu_status=${PIPESTATUS[0]}
  set -e
  if [[ $qemu_status -ne 0 ]]; then
    echo "ERROR: QEMU $mode boot exited with status $qemu_status" >&2
    return "$qemu_status"
  fi
  python3 "$(dirname -- "$0")/verify-boot.py" "$log"
}

run_mode "-bios"
if [[ $uefi == yes ]]; then
  [[ -s "$firmware_code" && -s "$firmware_vars" ]] || {
    echo 'ERROR: UEFI code and variable-store template must be nonempty files.' >&2
    exit 3
  }
  vars_copy=$(mktemp "${TMPDIR:-/tmp}/dockdsm-ovmf-vars.XXXXXX")
  trap 'rm -f -- "$vars_copy"' EXIT
  cp -- "$firmware_vars" "$vars_copy"
  run_mode "-uefi" --uefi --firmware-code "$firmware_code" \
    --firmware-vars "$vars_copy"
fi
