#!/usr/bin/env bash
set -Eeuo pipefail

repo_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../../.." && pwd)
external="$repo_root/research/x86_64/grub-loader"
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
  --defconfig "$external/configs/dockdsm_x86_64_grub_defconfig"
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
marker="$output/.dockdsm-x86_64-grub-build"
if [[ -e "$marker" ]]; then
  [[ "$(<"$marker")" == dockdsm-x86_64-grub-v1 ]] || {
    echo 'ERROR: output marker does not match this build.' >&2; exit 2;
  }
elif [[ -n "$(find "$output" -mindepth 1 -maxdepth 1 -print -quit)" ]]; then
  echo 'ERROR: OUTPUT_DIR is nonempty and has no DockDSM build marker; refusing to reuse it.' >&2
  exit 2
else
  printf '%s\n' dockdsm-x86_64-grub-v1 > "$marker"
fi

jobs=${JOBS:-4}
[[ "$jobs" =~ ^[1-9][0-9]*$ ]] || { echo 'ERROR: JOBS must be a positive integer.' >&2; exit 2; }
buildroot_epoch=$(sed -n 's/^BR2_VERSION_EPOCH = \([0-9][0-9]*\)$/\1/p' "$buildroot/Makefile")
[[ "$buildroot_epoch" =~ ^[1-9][0-9]*$ ]] || {
  echo 'ERROR: could not read the pinned Buildroot release epoch.' >&2
  exit 2
}
iso_date=$(date -u -d "@$buildroot_epoch" +%Y%m%d%H%M%S00)
if [[ -n "$downloads" ]]; then
  mkdir -p -- "$downloads"
  downloads=$(cd -- "$downloads" && pwd -P)
else
  downloads="$output/downloads"
fi
mkdir -p -- "$downloads"
SOURCE_DATE_EPOCH="$buildroot_epoch" make -C "$buildroot" O="$output" BR2_EXTERNAL="$external" BR2_DL_DIR="$downloads" \
  dockdsm_x86_64_grub_defconfig
SOURCE_DATE_EPOCH="$buildroot_epoch" make -C "$buildroot" O="$output" BR2_EXTERNAL="$external" BR2_DL_DIR="$downloads" olddefconfig
python3 "$repo_root/research/buildroot/check_inputs.py" \
  --buildroot "$buildroot" \
  --defconfig "$external/configs/dockdsm_x86_64_grub_defconfig" \
  --config "$output/.config"
SOURCE_DATE_EPOCH="$buildroot_epoch" make -C "$buildroot" O="$output" BR2_EXTERNAL="$external" BR2_DL_DIR="$downloads" dependencies

for required in BR2_x86_64=y BR2_REPRODUCIBLE=y BR2_TARGET_GRUB2=y \
  BR2_TARGET_GRUB2_I386_PC=y BR2_TARGET_GRUB2_X86_64_EFI=y \
  BR2_TARGET_ROOTFS_ISO9660=y BR2_TARGET_ROOTFS_ISO9660_INITRD=y; do
  grep -qx "$required" "$output/.config" || {
    echo "ERROR: resolved Buildroot config is missing $required." >&2
    exit 1
  }
done
if grep -qx 'BR2_TARGET_ROOTFS_INITRAMFS=y' "$output/.config"; then
  echo 'ERROR: the GRUB ISO test requires an external initrd, not a kernel built-in initramfs.' >&2
  exit 1
fi

# Buildroot does not automatically reconfigure an already-built package when
# its target tuple list changes. Track the GRUB/ISO selections and menus so a
# reused output directory regenerates the BIOS and EFI GRUB images safely.
grub_config_fingerprint=$(
  {
    grep -E '^(BR2_TARGET_GRUB2|BR2_TARGET_ROOTFS_ISO9660)' "$output/.config"
    sha256sum \
      "$external/board/x86_64-grub/grub.cfg" \
      "$external/board/x86_64-grub/grub-efi.cfg"
  } | sha256sum | cut -d ' ' -f 1
)
grub_config_marker="$output/.dockdsm-x86_64-grub-config-sha256"
previous_grub_config=
if [[ -f "$grub_config_marker" ]]; then
  previous_grub_config=$(<"$grub_config_marker")
fi
if [[ "$grub_config_fingerprint" != "$previous_grub_config" ]]; then
  SOURCE_DATE_EPOCH="$buildroot_epoch" make -C "$buildroot" O="$output" BR2_EXTERNAL="$external" BR2_DL_DIR="$downloads" \
    grub2-reconfigure
  printf '%s\n' "$grub_config_fingerprint" > "$grub_config_marker"
fi

SOURCE_DATE_EPOCH="$buildroot_epoch" make -C "$buildroot" O="$output" BR2_EXTERNAL="$external" BR2_DL_DIR="$downloads" -j"$jobs"
kernel_config=$(find "$output/build" -maxdepth 4 -type f -path '*/linux-*/.config' -print -quit)
if [[ -z "$kernel_config" ]]; then
  echo 'ERROR: Buildroot produced no Linux kernel configuration.' >&2
  exit 1
fi
for required in CONFIG_BLK_DEV_INITRD=y CONFIG_RD_GZIP=y CONFIG_EFI=y CONFIG_EFI_STUB=y \
  CONFIG_SERIAL_8250=y CONFIG_SERIAL_8250_CONSOLE=y \
  CONFIG_DEVTMPFS=y CONFIG_DEVTMPFS_MOUNT=y; do
  grep -Fqx "$required" "$kernel_config" || {
    echo "ERROR: built x86_64 kernel config is missing $required." >&2
    exit 1
  }
done
[[ -s "$output/images/rootfs.iso9660" ]] || {
  echo 'ERROR: Buildroot did not produce images/rootfs.iso9660.' >&2
  exit 1
}
# Buildroot's ISO staging tree can retain wall-clock mtimes even when
# BR2_REPRODUCIBLE is enabled. Normalize every entry, then use xorriso's
# timestamp controls so both directory records and the volume descriptor use
# the locked release epoch.
iso_stage="$output/build/buildroot-fs/rootfs.iso9660.tmp"
[[ -d "$iso_stage" ]] || {
  echo 'ERROR: Buildroot did not retain the ISO9660 staging tree.' >&2
  exit 1
}
find "$iso_stage" -depth -exec touch -h -d "@$buildroot_epoch" -- {} +
reproducible_iso="$output/images/rootfs.iso9660.reproducible"
"$output/host/bin/xorriso" -as mkisofs -J -R \
  -b boot/grub/grub-eltorito.img -no-emul-boot -boot-load-size 4 -boot-info-table \
  -eltorito-alt-boot --efi-boot boot/fat.efi -no-emul-boot \
  --modification-date="$iso_date" --set_all_file_dates "$iso_date" \
  -o "$reproducible_iso" "$iso_stage"
mv -f -- "$reproducible_iso" "$output/images/rootfs.iso9660"
for required in grub-eltorito.img efi-part/EFI/BOOT/bootx64.efi; do
  [[ -s "$output/images/$required" ]] || {
    echo "ERROR: Buildroot did not produce the BIOS/UEFI boot artifact $required." >&2
    exit 1
  }
done
printf 'Buildroot x86_64 GRUB ISO: %s/images/rootfs.iso9660\n' "$output"
