# ARM64 UEFI GRUB to Linux loader handoff

This isolated research chain exercises the ARM64 first-stage path that the
current ARC snapshot lacks: AArch64 UEFI firmware loads GRUB from a GPT EFI
system partition, GRUB loads the existing Buildroot ARM64 kernel and kexec
loader initramfs, and that loader hands off to the open Linux target kernel.
The DSM kernel/initrd can be evaluated only in the separate DS124 research
profile. This experiment does not run ARC user space or an ARC-built DSM loader.

## Build

Use the verified Buildroot source tree and a fresh external output directory.
Buildroot creates the `arm64-efi` GRUB application from source and packages it
with `Image` and `dockdsm-loader.cpio.gz` in an isolated GPT/EFI disk image.
The firmware is supplied by the Linux test environment; it is not copied into
the repository or the image.

```bash
DEFCONFIG=dockdsm_arm64_grub_defconfig \
BUILDROOT_DIR=/path/to/buildroot-2025.02.19 \
OUTPUT_DIR=/var/tmp/dockdsm-arm64-grub-output \
DOWNLOADS_DIR=/var/tmp/dockdsm-buildroot-downloads \
research/arm64/loader/build.sh
```

The output and download directories must be separate from the repository and
from each other. The build script accepts only the two tracked ARM64
defconfigs, verifies the shared Buildroot/Linux source lock, and uses a distinct
marker for the GRUB build output.

## QEMU boot

Use a Linux ARM64 QEMU environment with AArch64 EFI firmware, for example a
distribution-provided `QEMU_EFI.fd` or AAVMF firmware. The UEFI firmware is an
explicit local input. The QEMU plan forces TCG, disables networking and mounts
the research boot image read-only.

```bash
research/arm64/grub-loader/test.sh \
  /var/tmp/dockdsm-arm64-grub-output \
  /usr/share/edk2/aarch64/QEMU_EFI.fd
```

Success requires the GRUB menu marker, the existing loader/kernel handoff
markers in order, target poweroff, and QEMU exit status 0. This proves only the
open ARM64 UEFI → GRUB → Buildroot loader → kexec chain. It does not establish
ARC compatibility, DSM installation, persistent storage, management,
hardware support or production `full-arm64` support.

## Verification status

The synthetic provider and transcript contracts pass on the macOS arm64 host.
The GRUB configuration explicitly routes its serial terminal through the
`virt` PL011 MMIO UART so QEMU can capture the entry marker without a display.
An isolated ARM64 Colima VM starts on the macOS host, and the locked Buildroot
source tree passes its provenance check when read directly from the shared
mount. A build attempt using VM-local output reached the full glibc Git history
download and was stopped before image creation; no UEFI QEMU boot was run.
Treat this loader as implemented but unverified until the documented Linux
build and boot complete.
