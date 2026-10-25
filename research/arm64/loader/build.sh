#!/usr/bin/env bash
set -Eeuo pipefail

repo_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../../.." && pwd)
external="$repo_root/research/arm64/loader"
buildroot=${BUILDROOT_DIR:-}
output=${OUTPUT_DIR:-}
downloads=${DOWNLOADS_DIR:-}

[[ -n "$buildroot" && -f "$buildroot/Makefile" ]] || {
  echo 'ERROR: set BUILDROOT_DIR to the verified Buildroot source.' >&2
  exit 2
}
[[ "$(uname -s)" == Linux ]] || {
  echo 'ERROR: Buildroot builds must run on Linux; use an isolated Linux VM/container.' >&2
  exit 2
}
python3 "$repo_root/research/buildroot/check_inputs.py" \
  --buildroot "$buildroot" \
  --defconfig "$external/configs/dockdsm_arm64_kexec_defconfig"
[[ -n "$output" && "$output" != / ]] || {
  echo 'ERROR: set OUTPUT_DIR to a dedicated external build directory.' >&2
  exit 2
}
output=$(python3 "$repo_root/research/buildroot/check_inputs.py" \
  --check-output "$output" --repo-root "$repo_root")
if [[ -n "$downloads" ]]; then
  downloads=$(python3 "$repo_root/research/buildroot/check_inputs.py" \
    --check-output "$downloads" --repo-root "$repo_root")
  case "$output/" in
    "$downloads/"*) echo 'ERROR: DOWNLOADS_DIR must be separate from OUTPUT_DIR.' >&2; exit 2 ;;
  esac
  case "$downloads/" in
    "$output/"*) echo 'ERROR: DOWNLOADS_DIR must be separate from OUTPUT_DIR.' >&2; exit 2 ;;
  esac
fi
mkdir -p -- "$output"
output=$(cd -- "$output" && pwd -P)
case "$output/" in
  "$repo_root/"*) echo 'ERROR: OUTPUT_DIR must be outside the repository.' >&2; exit 2 ;;
esac
[[ -n "$downloads" ]] || downloads="$output/downloads"
marker="$output/.dockdsm-arm64-kexec-build"
if [[ -e "$marker" ]]; then
  [[ "$(<"$marker")" == dockdsm-arm64-kexec-v1 ]] || {
    echo 'ERROR: output marker does not match this build.' >&2; exit 2;
  }
elif [[ -n "$(find "$output" -mindepth 1 -maxdepth 1 -print -quit)" ]]; then
  echo 'ERROR: OUTPUT_DIR is nonempty and has no DockDSM build marker; refusing to reuse it.' >&2
  exit 2
else
  printf '%s\n' dockdsm-arm64-kexec-v1 > "$marker"
fi

jobs=${JOBS:-4}
[[ "$jobs" =~ ^[1-9][0-9]*$ ]] || { echo 'ERROR: JOBS must be a positive integer.' >&2; exit 2; }
mkdir -p -- "$downloads"
downloads=$(cd -- "$downloads" && pwd -P)
make -C "$buildroot" O="$output" BR2_EXTERNAL="$external" BR2_DL_DIR="$downloads" \
  dockdsm_arm64_kexec_defconfig
make -C "$buildroot" O="$output" BR2_EXTERNAL="$external" BR2_DL_DIR="$downloads" olddefconfig
python3 "$repo_root/research/buildroot/check_inputs.py" \
  --buildroot "$buildroot" \
  --defconfig "$external/configs/dockdsm_arm64_kexec_defconfig" \
  --config "$output/.config"
make -C "$buildroot" O="$output" BR2_EXTERNAL="$external" BR2_DL_DIR="$downloads" dependencies

grep -qx 'BR2_aarch64=y' "$output/.config"
grep -qx 'BR2_PACKAGE_KEXEC=y' "$output/.config"
grep -qx 'BR2_TARGET_ROOTFS_CPIO=y' "$output/.config"

make -C "$buildroot" O="$output" BR2_EXTERNAL="$external" BR2_DL_DIR="$downloads" -j"$jobs"
kernel_config=$(find "$output/build" -maxdepth 4 -type f -path '*/linux-*/.config' -print -quit)
if [[ -z "$kernel_config" ]]; then
  echo 'ERROR: Buildroot produced no Linux kernel configuration.' >&2
  exit 1
fi
for required in CONFIG_KEXEC=y CONFIG_KEXEC_FILE=y CONFIG_ARM64_VA_BITS_48=y \
  CONFIG_BLK_DEV_INITRD=y CONFIG_RD_GZIP=y \
  CONFIG_DEVTMPFS=y CONFIG_DEVTMPFS_MOUNT=y \
  CONFIG_PROC_KCORE=y \
  CONFIG_RANDOMIZE_BASE=y \
  CONFIG_SERIAL_AMBA_PL011=y CONFIG_SERIAL_AMBA_PL011_CONSOLE=y; do
  grep -Fqx "$required" "$kernel_config" || {
    echo "ERROR: built ARM64 kernel config is missing $required." >&2
    exit 1
  }
done
python3 "$external/board/arm64-kexec/make-initramfs.py" \
  "$output/target" "$output/images/Image" "$output/images" \
  "$external/board/arm64-kexec/target-init" \
  "$external/board/arm64-kexec/rootfs-overlay/init"
for artifact in Image dockdsm-loader.cpio.gz dockdsm-target.cpio.gz; do
  [[ -s "$output/images/$artifact" ]] || {
    echo "ERROR: Buildroot did not produce $artifact" >&2
    exit 1
  }
done
printf 'Buildroot loader artifacts: %s/images\n' "$output"
