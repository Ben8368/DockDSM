#!/usr/bin/env bash
set -Eeuo pipefail

repo_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../../.." && pwd)
if [[ $# -lt 3 ]]; then
  echo "Usage: $0 BUILDROOT_OUTPUT DSM_KERNEL NEW_TEST_OUTPUT [--qemu PATH] [--timeout-seconds N]" >&2
  exit 2
fi
buildroot_output=$1
dsm_kernel=$2
output_arg=$3
shift 3
qemu=${QEMU:-qemu-system-aarch64}
timeout_seconds=${TIMEOUT_SECONDS:-180}
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

[[ -d "$buildroot_output/target" && -s "$buildroot_output/images/Image" ]] || {
  echo 'ERROR: BUILDROOT_OUTPUT must contain target/ and images/Image.' >&2
  exit 2
}
[[ -f "$dsm_kernel" && -s "$dsm_kernel" && ! -L "$dsm_kernel" ]] || {
  echo 'ERROR: DSM_KERNEL must be a nonempty regular file, not a symlink.' >&2
  exit 2
}
[[ "$timeout_seconds" =~ ^[0-9]+$ && "$timeout_seconds" -ge 60 && "$timeout_seconds" -le 600 ]] || {
  echo 'ERROR: timeout must be an integer from 60 to 600 seconds.' >&2
  exit 2
}
[[ ! -e "$output_arg" && ! -L "$output_arg" ]] || {
  echo 'ERROR: test output already exists; use a new dedicated directory.' >&2
  exit 2
}
python3 "$repo_root/research/buildroot/check_inputs.py" \
  --check-output "$output_arg" --repo-root "$repo_root" >/dev/null

timeout_bin=${TIMEOUT:-timeout}
if ! command -v "$timeout_bin" >/dev/null 2>&1 && [[ $timeout_bin == timeout ]] \
  && command -v gtimeout >/dev/null 2>&1; then
  timeout_bin=gtimeout
fi
for tool in python3 "$timeout_bin" "$qemu"; do
  command -v "$tool" >/dev/null 2>&1 || {
    echo "ERROR: required command is unavailable: $tool" >&2
    exit 3
  }
done

umask 077
mkdir -m 0700 -- "$output_arg"
output=$(cd -- "$output_arg" && pwd -P)
chmod 0700 "$output"
probe_initrd="$output/dockdsm-ds124-sata-probe-initrd.cpio"
loader_initrd="$output/dockdsm-ds124-sata-probe-loader.cpio.gz"
python3 "$repo_root/research/arm64/loader/make-dsm-sata-probe-initrd.py" \
  "$buildroot_output/target" "$probe_initrd"
python3 "$repo_root/research/arm64/loader/prepare-dsm-kexec.py" \
  "$buildroot_output/target" "$dsm_kernel" "$probe_initrd" "$loader_initrd"

log="$output/dsm-sata-probe.log"
set +e
"$timeout_bin" --signal=TERM --kill-after=5s "${timeout_seconds}s" \
  python3 "$repo_root/research/arm64/loader/qemu-plan.py" \
    --profile research-arm64-dsm-kexec --execute --qemu "$qemu" \
    --kernel "$buildroot_output/images/Image" --initrd "$loader_initrd" \
    --cpu max,lpa2=off --gic-version 3 --its on --loader-disable-lpi \
    --memory-mib 2048 --vcpus 2 --serial-route dsm-mmio16550 \
    --scratch-sata1-dir "$output" 2>&1 | tee "$log"
qemu_status=${PIPESTATUS[0]}
set -e
if [[ $qemu_status -ne 0 ]]; then
  echo "ERROR: DS124 SATA probe QEMU must power off cleanly; status=$qemu_status" >&2
  exit "$qemu_status"
fi
python3 "$repo_root/research/arm64/loader/verify-dsm-sata-probe.py" "$log"
echo "Isolated DS124 SATA probe passed. The new 2 GiB scratch image and serial log remain under: $output"
