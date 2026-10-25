#!/bin/sh
set -eu

: "${BINARIES_DIR:?Buildroot did not set BINARIES_DIR}"
script_dir=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
efi_boot="$BINARIES_DIR/efi-part/EFI/BOOT"
grub_efi=
for candidate in "$efi_boot/BOOTAA64.EFI" "$efi_boot/bootaa64.efi"; do
  if [ -s "$candidate" ]; then
    grub_efi=$candidate
    break
  fi
done
if [ -z "$grub_efi" ]; then
  echo 'ERROR: Buildroot did not produce the ARM64 removable-media GRUB EFI image.' >&2
  exit 1
fi
for artifact in Image dockdsm-loader.cpio.gz; do
  if [ ! -s "$BINARIES_DIR/$artifact" ]; then
    echo "ERROR: missing ARM64 GRUB input: $BINARIES_DIR/$artifact" >&2
    exit 1
  fi
done
cp -- "$script_dir/grub.cfg" "$efi_boot/grub.cfg"
