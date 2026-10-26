# Open x86_64 GRUB to Linux boot test

This isolated Buildroot target creates a BIOS and UEFI bootable GRUB ISO
containing a locked Linux 6.12.112 kernel and a small initramfs. GRUB loads the
kernel and initramfs in the same QEMU VM; PID 1 prints
`DOCKDSM_X86_GRUB_LINUX_BOOTED` and powers off. This demonstrates the
GRUB-to-Linux boot path only. It does not test DSM, kexec, installation, or a
product data disk.

The experiment does not use ARC, DSM PAT files, production QEMU patches, or the
existing `virtualdsm` storage directory. Its provider remains internal and is
not registered as a `DSM_PLATFORM` option. Build output and package downloads
must be placed in an external dedicated directory.

## Inputs and commands

`research/buildroot/source-lock.json` is the shared lock for Buildroot
2025.02.19 and Linux 6.12.112. The build script checks the Buildroot version
and Linux hash entries in both source hash databases, verifies the fetched
source-tree fingerprint, then checks through the shared
[`check_inputs.py`](../../buildroot/check_inputs.py) that resolved
`olddefconfig` still selects the locked Linux version. Buildroot's forced
hash checking validates package downloads. GRUB2 is built from Buildroot's
GPL-3.0-or-later source package; no prebuilt loader binary is imported.

Run on Linux with Buildroot host prerequisites, `qemu-system-x86_64`, xorriso,
and OVMF firmware:

```bash
research/arm64/loader/fetch-buildroot.sh "$HOME/src/buildroot-2025.02.19"
output_dir=$(mktemp -d)
downloads_dir=$(mktemp -d)
BUILDROOT_DIR="$HOME/src/buildroot-2025.02.19" \
OUTPUT_DIR="$output_dir" DOWNLOADS_DIR="$downloads_dir" JOBS=4 \
  research/x86_64/grub-loader/build.sh
research/x86_64/grub-loader/test.sh "$output_dir" --uefi \
  /usr/share/OVMF/OVMF_CODE_4M.fd /usr/share/OVMF/OVMF_VARS_4M.fd
```

`--firmware-vars` must name a writable disposable copy of the OVMF template;
QEMU may modify it. The repository test runner creates and removes that copy.

`build.sh` refuses macOS, a mismatched Buildroot release, repository-local
output, an unmarked nonempty output directory, or a download cache that overlaps
the repository or output. `DOWNLOADS_DIR` is optional; if omitted, downloads
stay under `OUTPUT_DIR/downloads`. A separate cache can be shared between the
ARM64 and x86_64 builds. The QEMU plan forces TCG,
disables networking, and attaches only the read-only boot ISO. Its CLI emits
NUL-delimited argv for inspection; the runner executes it through the
`qemu-process` adapter, which replaces itself with QEMU using `execvpe` and
never evaluates a command string.

## Evidence boundary

`tests/x86_64-grub-loader.py` checks provider contracts, architecture
separation, BIOS/UEFI QEMU argv, the Buildroot configuration intent, and strict
serial transcript handling. The build also rejects an in-kernel initramfs
because the ISO menu must load a separate initrd. Parsing `defconfig` is not a
kernel/GRUB build. A real QEMU serial marker from each firmware mode is required
before claiming that mode's GRUB-to-Linux boot. This experiment does not
establish the ARC source or license admission needed for DSM integration.

## Local verification record

On 2026-10-25, Buildroot 2025.02.19 produced
`/var/tmp/dockdsm-x86_64-grub/images/rootfs.iso9660` in the isolated ARM64
Linux container. One `test.sh --uefi` run booted the same ISO through SeaBIOS
and OVMF under QEMU TCG; both loaded Linux 6.12.112, printed
`DOCKDSM_X86_GRUB_LINUX_BOOTED`, reported `reboot: Power down`, and passed; the
runner returned 0. ISO SHA256:
`7648a37baee06c313b55928106390d516856c950aecb5c272cc5120bb8faca9f`.
Ignored original serial logs:
`research/x86_64/work/2026-10-25/grub-boot-bios.log` (SHA256
`1fc2ec9c9a4445e9a5fabf59748048d19a7a9b1dc1c7ad7e583aef3bbbc6dc4b`) and
`grub-boot-uefi.log` (SHA256
`26e80236b4eb8c7d16628a3bf8e0c77e35be26fe630a4d0ceab4aa4c8aaccf8f`).
The current provider/runtime was rerun against the preserved ISO in a new test
directory; BIOS and UEFI both exited 0 with the same marker and guest powerdown.
Those logs are `current-provider-rerun-bios.log` (SHA256
`1fb79ffa4beaf3ab24c169922cd2083765465021fe9b24269c7791c387abd378`) and
`current-provider-rerun-uefi.log` (SHA256
`c078545492a49298c2ceb9fcd29433fd120c99c8bb96324d57694f014051c36f`) in the
same ignored evidence directory. This remains an open-Linux test, not a DSM
boot or lifecycle result.

On 2026-10-25, the current build script was also run from a fresh Linux Docker
volume on the Colima ARM64 VM with the shared, verified `DOWNLOADS_DIR`. Buildroot
produced a bootable ISO (SHA256
`0a15beab44c7573ff0b80471e56266d7a95ffdebb99dee358dcbafc487947548`); QEMU
8.2.2 TCG booted it through SeaBIOS and OVMF. Both runs printed the exact marker,
powered down cleanly, and passed the serial verifier. This verifies the actual
Buildroot build and the external-cache path; DSM remains untested.

The ISO is now made byte-reproducible by exporting the locked Buildroot release
epoch (`BR2_VERSION_EPOCH`) to every Buildroot `make`, then normalizing all
entries in `build/buildroot-fs/rootfs.iso9660.tmp` before re-running the locked
Buildroot xorriso BIOS/UEFI command with `--modification-date` and
`--set_all_file_dates`. On 2026-10-25, two consecutive builds on the same
verified Buildroot 2025.02.19 source and download cache produced identical ISO
SHA256 `3514a75682f03b8c985b369629b6f3b80fb3340fb6e4a240bf39fd5738dce41c`.
The resulting ISO again booted under QEMU TCG through SeaBIOS and OVMF, printed
the marker, and powered down cleanly. Serial log SHA256 values are
`cbaafffac4eec33a91fd46c8bb45ee65d8242a3097d934b5655f63ee6b886f61` (BIOS)
and `ff436389f07926502d3c088909c0c346f804c080dec86b729423978b42d9155d`
(UEFI). The ISO and logs are retained outside Git in the task-private evidence
directory `x86-reproducibility-20261025/evidence/output/`.
