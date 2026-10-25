#!/usr/bin/env bash
set -Eeuo pipefail

output_arg=
cpu=cortex-a57
gic_version=2
memory_mib=512
its=
loader_disable_lpi=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --cpu)
      [[ $# -ge 2 ]] || { echo "ERROR: --cpu requires a value" >&2; exit 2; }
      cpu=$2; shift 2 ;;
    --gic-version)
      [[ $# -ge 2 ]] || { echo "ERROR: --gic-version requires a value" >&2; exit 2; }
      gic_version=$2; shift 2 ;;
    --memory-mib)
      [[ $# -ge 2 ]] || { echo "ERROR: --memory-mib requires a value" >&2; exit 2; }
      memory_mib=$2; shift 2 ;;
    --its)
      [[ $# -ge 2 ]] || { echo "ERROR: --its requires on or off" >&2; exit 2; }
      its=$2; shift 2 ;;
    --loader-disable-lpi) loader_disable_lpi=1; shift ;;
    -*) echo "ERROR: unsupported option: $1" >&2; exit 2 ;;
    *)
      [[ -z "$output_arg" ]] || { echo "ERROR: only one output directory is accepted" >&2; exit 2; }
      output_arg=$1; shift ;;
  esac
done
if [[ -z "$output_arg" || ! -d "$output_arg/images" ]]; then
  echo "Usage: $0 /path/to/Buildroot/output [--cpu cortex-a57|cortex-a55] [--gic-version 2|3] [--memory-mib 512|1024] [--its on|off] [--loader-disable-lpi]" >&2
  exit 2
fi
[[ "$cpu" == cortex-a57 || "$cpu" == cortex-a55 ]] || { echo "ERROR: unsupported ARM64 research CPU: $cpu" >&2; exit 2; }
[[ "$gic_version" == 2 || "$gic_version" == 3 ]] || { echo "ERROR: GIC version must be 2 or 3" >&2; exit 2; }
[[ "$memory_mib" == 512 || "$memory_mib" == 1024 ]] || { echo "ERROR: memory must be 512 or 1024 MiB" >&2; exit 2; }
[[ -z "$its" || "$its" == on || "$its" == off ]] || { echo "ERROR: --its must be on or off" >&2; exit 2; }
[[ "$gic_version" == 3 || -z "$its" ]] || { echo "ERROR: --its is valid only with GICv3" >&2; exit 2; }
[[ "$loader_disable_lpi" == 0 || ( "$gic_version" == 3 && "$its" != off ) ]] || { echo "ERROR: --loader-disable-lpi requires GICv3 with ITS enabled or default" >&2; exit 2; }
output=$(cd -- "$output_arg" && pwd -P)
qemu=${QEMU:-qemu-system-aarch64}
timeout_bin=${TIMEOUT:-timeout}
for tool in "$qemu" "$timeout_bin" python3; do
  command -v "$tool" >/dev/null 2>&1 || {
    echo "ERROR: required command is unavailable: $tool" >&2
    exit 3
  }
done
for artifact in Image dockdsm-loader.cpio.gz dockdsm-target.cpio.gz; do
  [[ -s "$output/images/$artifact" ]] || {
    echo "ERROR: missing or empty test artifact: $output/images/$artifact" >&2
    exit 4
  }
done

if [[ "$cpu" == cortex-a57 && "$gic_version" == 2 && -z "$its" && "$memory_mib" == 512 && "$loader_disable_lpi" == 0 ]]; then
  log="$output/kexec-handoff.log"
else
  log="$output/kexec-handoff-${cpu}-gicv${gic_version}-its-${its:-default}-mem-${memory_mib}-loader-nolpi-${loader_disable_lpi}.log"
fi
cmd=(python3 "$(dirname -- "$0")/qemu-plan.py" --execute \
  --qemu "$qemu" \
  --kernel "$output/images/Image" \
  --initrd "$output/images/dockdsm-loader.cpio.gz")
cmd+=(--cpu "$cpu" --gic-version "$gic_version" --memory-mib "$memory_mib")
if [[ -n "$its" ]]; then
  cmd+=(--its "$its")
fi
if [[ "$loader_disable_lpi" == 1 ]]; then
  cmd+=(--loader-disable-lpi)
fi
set +e
"$timeout_bin" --signal=TERM --kill-after=5s 120s "${cmd[@]}" 2>&1 | tee "$log"
qemu_status=${PIPESTATUS[0]}
set -e
if [[ $qemu_status -ne 0 ]]; then
  echo "ERROR: QEMU exited with status $qemu_status" >&2
  exit "$qemu_status"
fi
python3 "$(dirname -- "$0")/verify-handoff.py" "$log"
echo "Serial log: $log"
