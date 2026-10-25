#!/bin/sh
set -eu

script_dir=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
python3 "$script_dir/make-initramfs.py" \
  "$TARGET_DIR" "$BINARIES_DIR/Image" "$BINARIES_DIR" \
  "$script_dir/target-init" "$script_dir/rootfs-overlay/init"
