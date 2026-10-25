# Open ARM64 Linux kexec handoff

This isolated research target builds a minimal ARM64 Buildroot Linux system
whose PID 1 loads the Buildroot `Image` plus a second initramfs with `kexec`,
then transfers control to that Linux kernel in the same QEMU VM. The target
initramfs prints a unique serial marker and powers off the guest. The loader and
target deliberately use the same open kernel image in this first handoff test;
this verifies the kexec transfer path, not a DSM kernel or a different kernel
build. The verified smoke-test LaunchPlan uses QEMU `virt`, GICv2, Cortex-A57,
one vCPU, 512 MiB, and a zero KASLR seed, matching Buildroot's upstream kexec
runtime-test baseline.

It does not use ARC, DSM PAT files, DSM disks, production QEMU patches, or the
existing `rtd1619b` data directory. It does not register a `DSM_PLATFORM` value
or change the production image. Build outputs and package downloads must live
outside the repository in a dedicated directory.

The isolated runner obtains its QEMU argv from the research-only
`LinuxKexecProvider` LaunchPlan. That provider is not part of the production
profile registry. The open-Linux profile supports Cortex-A57/A55, GICv2/v3,
and an optional explicit ITS state for GICv3. A separate fixed DS124 research
profile uses `max,lpa2=off`, GICv3 ITS-on, loader-only LPI suppression, a
`kexec_load` memory floor at `0x42000000`, 2 vCPUs, 2048 MiB and the patched
MMIO 16550 console route. Neither profile accepts
arbitrary QEMU argument passthrough. The command-line adapter emits NUL-delimited arguments for
inspection or executes the plan through `qemu-process`; the runtime replaces
itself with QEMU using `execvpe`, without a shell command string.

The ARM64 loader now forces the legacy `kexec_load` syscall (`-c`) and sets
`--mem-min=0x42000000`. The initially tested `kexec_file_load` path (`-s`)
ignored this lower bound and still placed the target at `0x41000000`; with the
loader LPI property table at `0x41060000`, Linux 6.12.112 reset that 64 KiB
table over its own text and faulted. With `kexec_load`, the open-Linux GICv3 /
Cortex-A55 / ITS-on run places the target at `0x42000000`, keeps the loader's
LPIs enabled, reaches the target marker, and powers down. The target allocates
new LPI tables at `0x40060000`/`0x40070000`. GICv2 and GICv3 ITS-off runs also
pass.

The DS124 kernel has an additional constraint: when the loader enters kexec
with LPIs enabled, DSM prints `Booted with LPIs enabled, memory probably
corrupted`, taints itself, and disables LPIs in its damage-control path, even
when the kernel segment is above the old tables. Therefore the DS124 research
profile continues to set `irqchip.gicv3_nolpi=1` on the loader only. With that
setting plus `kexec_load` and the memory floor, the official kernel/initrd
reaches login without the warning; the target allocates fresh LPI tables. This
is a QEMU-specific bounded result, not evidence that an LPI-enabled loader is
safe for DSM or that the physical DS124 GIC contract is satisfied.

## Locked input

[`research/buildroot/source-lock.json`](../../buildroot/source-lock.json) pins
the official Buildroot 2025.02.19 LTS source archive by its SHA256 measured
from that archive, and Linux 6.12.112 by the SHA256 present in that Buildroot
release's `linux/linux.hash` (sourced from kernel.org).
The fetch script records the verified archive digest and an extracted-source
tree fingerprint; build preflight rejects a missing marker or source drift.
`BR2_DOWNLOAD_FORCE_CHECK_HASHES` also requires hashes for kexec-tools,
toolchain, and package inputs. Build scripts verify the pinned kernel entry
before configuring, then confirm `olddefconfig` preserves the locked version via the shared
[`check_inputs.py`](../../buildroot/check_inputs.py). Buildroot 2025.02.x is the upstream LTS series,
maintained through March 2028 ([official release table](https://buildroot.org/download.html)).

The resulting userspace includes upstream Buildroot BusyBox and kexec-tools.
The Linux kernel source version is selected in the defconfig and resolved
through Buildroot's own package hash database. Nothing from the generated root
filesystem or kernel is checked into Git.
By default, Buildroot package downloads live in `OUTPUT_DIR/downloads`. Set
`DOWNLOADS_DIR` to a separate path outside the repository to reuse a copied
download cache while building into a fresh output directory; the two paths may
not overlap.

## Build and run on Linux

Install the Buildroot host prerequisites and QEMU AArch64 system emulator. On
Ubuntu/Debian, the CI workflow's package list is a working reference. Then:

```bash
mkdir -p "$HOME/src"
research/arm64/loader/fetch-buildroot.sh "$HOME/src/buildroot-2025.02.19"
output_dir=$(mktemp -d)
BUILDROOT_DIR="$HOME/src/buildroot-2025.02.19" \
OUTPUT_DIR="$output_dir" JOBS=4 \
  research/arm64/loader/build.sh
research/arm64/loader/test.sh "$output_dir"
research/arm64/loader/test.sh "$output_dir" --cpu cortex-a55 --gic-version 3 --its off
research/arm64/loader/test.sh "$output_dir" --cpu cortex-a55 --gic-version 3 --its on
research/arm64/loader/test.sh "$output_dir" --cpu cortex-a55 --gic-version 3 \
  --memory-mib 1024 --its on --loader-disable-lpi
```

`build.sh` refuses a source tree with another Buildroot release, macOS as the
build host, a repository-local output path, or an unmarked nonempty output
directory. `test.sh` forces QEMU TCG and requires the guest to power off after
the target initramfs marker. Its success means only that the open Linux
Loader→Kernel handoff worked under the selected research configuration.

The deterministic newc packer emits root-owned entries and the minimum
`/dev/console` and `/dev/null` devices without running privileged `mknod`.
`tests/arm64-loader.py` checks its archive contents and the serial transcript
verifier without claiming a VM boot.

## Current evidence boundary

The pinned Buildroot 2025.02.19 / Linux 6.12.112 build and QEMU serial handoff
have completed locally for GICv2/A57, GICv3/A55/ITS-off, and GICv3/A55/ITS-on
with loader LPIs enabled under TCG. A fresh output directory and separate copy
of the package cache also completed the full build and the earlier handoff
matrix. The success transcripts include
`DOCKDSM_KEXEC_TARGET_BOOTED`, guest `Power down`, and QEMU exit status 0.
The target kernel segment starts at `0x42000000` when loaded with `kexec_load`.
Host-only tests do not run QEMU. DSM kernel/initrd evidence is separate and
described below; this open-Linux test does not cover DSM installation,
persistence, or recovery.
The dated serial transcripts and hashes are preserved under the ignored
`research/arm64/work/arm64-kexec/2026-10-25/` and
`research/arm64/work/its-memmin-20261025/` evidence directories.

## Diskless DS124 kernel/initrd kexec experiment

`research-arm64-dsm-kexec` is an internal research profile, not a
`DSM_PLATFORM` selector. `prepare-dsm-kexec.py` accepts either an uncompressed
ARM64 `Image` and newc initrd or the PAT's LZMA-alone `zImage` and `rd.bin`;
it validates their magic, embeds them in a private Buildroot loader initramfs,
and refuses to overwrite an output or write inside the repository. The source
files and generated initramfs must remain in ignored/private storage.

`test-dsm-kexec.sh` uses a fixed LaunchPlan: QEMU `virt`, TCG, GICv3 ITS-on,
`max,lpa2=off`, `kexec_load` with `--mem-min=0x42000000`, 2 vCPUs, 2048 MiB,
loader-only `irqchip.gicv3_nolpi=1`, and the patched MMIO 16550 serial route.
The DS124 target command line does not disable LPI. It attaches no disk and no
network. A bounded timeout is the expected end of the observation window after DSM reaches its diskless login prompt; the
runner accepts only that timeout plus all target-kernel/initrd/login markers,
and rejects panic, oops, BUG, undefined-instruction and soft-lockup signatures.

On 2026-10-25, the exact official DS124 7.2.2-72806 kernel and initrd reached
`SynologyNAS login:` through kexec in the same QEMU VM. The loader debug log
shows the kernel segment at `0x42000000` (`0x18e0000` bytes), initrd at
`0x438e0000` (`0xe9e000` bytes), and all four kexec segments above the loader
LPI tables at `0x41060000`/`0x41070000`. The loader command line disables LPI
only in the loader; DSM still initializes GICv3 ITS and allocates fresh tables
at `0x40170000`, `0x40180000`, and `0x40190000`, without the corruption warning.
The target reported
`linux,dummy-virt`, GICv3, approximately 2 GiB RAM, booted CPU1, and allocated a
`synobios` opened the patched `/dev/ttyS1` and identified Model DS-124.
`linuxrc.syno` stopped at
`DISK NOT INSTALLED`, after which `/etc/rc` started. The runner returned 0
after its expected 150-second QEMU timeout. This proves the bounded Loader→DSM
kernel/initrd handoff for this QEMU configuration only. There was no DSM system
disk, network, install, configuration, storage volume, clean shutdown, or
recovery test, and the generic virt DTB is not the physical DS124 DTB. The
serial log and private generated initramfs are retained under the ignored
`research/arm64/work/dsm-kexec/2026-10-25-its-on/` directory. The target
serial log SHA256 is `a328b410f8bf3154eb5e65faf8763f26c20a9e10c10d4ee2d4a1c233a99f494c`;
the loader debug log SHA256 is
`8c5ae2cfc7370a7b9ad56701ed2a5fc3cc452a4a2cade78c5b6fe64ae78955e7`.

Reproduce with a verified Buildroot output, private PAT boot files and the
patched QEMU binary:

```bash
research/arm64/loader/test-dsm-kexec.sh \
  "$BUILDROOT_OUTPUT" /path/to/DSM_DS124_72806.Image \
  /path/to/DSM_DS124_72806.initrd.cpio "$NEW_TEST_OUTPUT" \
  --qemu /path/to/patched/qemu-system-aarch64 --timeout-seconds 150
```

The private inputs may instead be the original `zImage` and `rd.bin` files.
Use a new output directory outside the repository for every run.

## DS124 kernel SATA discovery probe

`test-dsm-sata-probe.sh` isolates the next storage contract without reusing a
DSM data disk. It kexecs the exact DS124 DSM kernel with a small diagnostic
initramfs built from the locked Buildroot userspace. The diagnostic waits for
`/dev/sata1`, checks the 2 GiB block geometry, and powers off. The QEMU provider
creates a new 2 GiB sparse file with exclusive-create semantics in the runner's
private output directory, then attaches it through the patched sysbus AHCI at
`if=ide,index=0`; the target command line carries the already validated
`libata.force=noncq` setting. It refuses to reuse a path, follow a symlink, accept an
allocated or incorrectly sized image, or place the scratch disk inside the
repository. No DSM userspace or original DSM initrd is run in this diagnostic.

Run it with a verified Buildroot output, the private official DS124 kernel, and
the patched QEMU 8.2.2 binary:

```bash
research/arm64/loader/test-dsm-sata-probe.sh \
  "$BUILDROOT_OUTPUT" /path/to/DSM_DS124_72806.Image "$NEW_TEST_OUTPUT" \
  --qemu /path/to/patched/qemu-system-aarch64 --timeout-seconds 180
```

The tracked probe contract and runner pass synthetic tests. On 2026-10-25 the
real probe also passed in patched QEMU `v8.2.2-dirty`, using the verified
Buildroot 2025.02.19 / Linux 6.12.112 loader and the official DS124 7.2.2-72806
kernel. The kernel bound `rtk_ahci`, negotiated a SATA link, identified
`QEMU HARDDISK`, and reported `/dev/sata1` with 4,194,304 sectors (2 GiB).
The diagnostic init printed the pass marker, synchronized and powered off;
QEMU returned 0. LaunchPlan SHA256:
`af74c2a4a338cde5cc5ad9aa603eaf2117386b47476fdd7fd08200ae35814eea`.

The only attached disk was a new sparse scratch image (2,147,483,648 bytes,
zero allocated blocks, mode 0600). No DSM userspace, DSM data disk, install,
volume initialization, network, management service or persistence path was
run. The serial log is retained outside the repository at
`dockdsm-arm64-sata-run-2026-10-25/evidence/dsm-sata-probe-attempt2.log`
(SHA256 `2dbb018856c7d8dcc72f9419eb1e1efd1d720e3319d499af639e4d47f4f506ec`);
the unused blank scratch image and complete raw run output remain in the
private Docker volume `dockdsm-arm64-sata-run-20261025`.

## Stock DS124 initrd with a blank SATA scratch disk

`test-dsm-initrd-sata.sh` embeds the supplied official kernel and original
initrd unchanged, creates a fresh private 2 GiB sparse SATA backing image, and
attaches it with QEMU `snapshot=on`. QEMU presents a writable disposable
copy-on-write overlay to the guest and discards that overlay on exit; the base
scratch image remains protected. After the bounded run the harness rejects any
backing image that is no longer mode 0600, 2 GiB, single-link, and unallocated.
The success gate requires the target kernel to enumerate the QEMU disk and
reach the DSM login prompt before timeout. It does not issue DSM installer
commands. This test verifies disk discovery only; it does not measure installer
writes, DSM persistence, or physical read-only behavior. On 2026-10-25, the
stock DS124 initrd reached `SynologyNAS login:` after detecting `/dev/sata1`
with the snapshot-backed 2 GiB disk under patched QEMU 8.2.2 TCG. QEMU exited
at the expected 180-second observation timeout; the backing image remained
mode 0600, 2 GiB, single-link, and 0 allocated blocks. A direct `readonly=on`
comparison failed during QEMU block-device initialization (`Block node is
read-only`), which is why the validated harness uses the temporary overlay.
LaunchPlan SHA256: `30c333387f49823adaaf8e113695f129e1f8be616ceeb11fa6fc479e0b24037f`.
The serial log SHA256 is
`5a251967de586b0e5c543a0a8ac5b649aff1a2b7909e9b9c49318fef536ffe22`. The
scratch backing retained mode 0600, 2 GiB size, one link, and zero allocated
blocks. The log and generated loader initrd are kept outside Git under the
task-private `arm64-stock-initrd-sata-20261025/run-validated/` evidence
directory.

Run with verified private Buildroot output, DS124 kernel/initrd files, patched
QEMU and a new output directory outside the repository:

```bash
research/arm64/loader/test-dsm-initrd-sata.sh \
  "$BUILDROOT_OUTPUT" /path/to/DSM_DS124_72806.Image \
  /path/to/DSM_DS124_72806.initrd.cpio "$NEW_TEST_OUTPUT" \
  --qemu /path/to/patched/qemu-system-aarch64 --timeout-seconds 180
```
