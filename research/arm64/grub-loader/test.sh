#!/usr/bin/env bash
set -Eeuo pipefail

repo_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../../.." && pwd)
output_arg=${1:-}
firmware=${2:-}
qemu=${QEMU:-qemu-system-aarch64}
timeout_bin=${TIMEOUT:-timeout}
timeout_seconds=${TIMEOUT_SECONDS:-180}

if [[ -z "$output_arg" || -z "$firmware" ]]; then
  echo "Usage: $0 BUILDROOT_OUTPUT AARCH64_UEFI_FIRMWARE [--qemu PATH] [--timeout-seconds N]" >&2
  exit 2
fi
shift 2
while [[ $# -gt 0 ]]; do
  case "$1" in
    --qemu)
      [[ $# -ge 2 ]] || { echo 'ERROR: --qemu requires a path.' >&2; exit 2; }
      qemu=$2; shift 2 ;;
    --timeout-seconds)
      [[ $# -ge 2 ]] || { echo 'ERROR: --timeout-seconds requires a value.' >&2; exit 2; }
      timeout_seconds=$2; shift 2 ;;
    *) echo "ERROR: unsupported option: $1" >&2; exit 2 ;;
  esac
done
[[ "$timeout_seconds" =~ ^[1-9][0-9]*$ ]] || {
  echo 'ERROR: timeout must be a positive integer.' >&2
  exit 2
}
output=$(python3 "$repo_root/research/buildroot/check_inputs.py" \
  --check-output "$output_arg" --repo-root "$repo_root")
for tool in "$qemu" "$timeout_bin" python3; do
  command -v "$tool" >/dev/null 2>&1 || {
    echo "ERROR: required command is unavailable: $tool" >&2
    exit 3
  }
done
[[ -s "$output/images/dockdsm-arm64-grub.img" ]] || {
  echo 'ERROR: missing or empty ARM64 GRUB disk image.' >&2
  exit 4
}
[[ -s "$firmware" ]] || {
  echo 'ERROR: missing or empty AArch64 UEFI firmware image.' >&2
  exit 4
}

log="$output/arm64-grub-handoff.log"
cmd=(python3 "$(dirname -- "$0")/qemu-plan.py" --execute \
  --qemu "$qemu" --disk "$output/images/dockdsm-arm64-grub.img" \
  --firmware "$firmware")
set +e
"$timeout_bin" --signal=TERM --kill-after=5s "${timeout_seconds}s" \
  "${cmd[@]}" 2>&1 | tee "$log"
qemu_status=${PIPESTATUS[0]}
set -e
if [[ $qemu_status -ne 0 ]]; then
  echo "ERROR: QEMU exited with status $qemu_status" >&2
  exit "$qemu_status"
fi
python3 "$(dirname -- "$0")/verify-grub.py" "$log"
echo "Serial log: $log"
