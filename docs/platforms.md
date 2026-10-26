# DSM platform interface

`DSM_PLATFORM=virtualdsm` remains the default and stable x86 VirtualDSM path.
`DSM_PLATFORM=rtd1619b` selects experimental DS124 DSM 7.2.2-72806 support.
It describes the validated DS124 hardware contract, not every rtd1619b NAS.
A container's image architecture does not select the DSM model.
Planned DockDSM Bootloader selectors `full-x86_64` / `full-arm64` are not
implemented or accepted values; ARM64 direct boot is not a loader port.
Host, container, QEMU guest, DSM model and bootloader architectures remain distinct.

This document defines implemented behavior. Proposed Profile/Boot Provider/Runtime
interfaces are in [runtime architecture](runtime-architecture.md); device validation
scope, including RK3588 Docker-only and Mac container selection, is in the
[test matrix](test-matrix.md). Proposed selectors and options are not accepted here.

| Selector | CONTAINER_ARCH | GUEST_ARCH | qemux PLATFORM | QEMU_BIN | Machine | Boot |
|---|---|---|---|---|---|---|
| `virtualdsm` | detected `amd64` or `arm64` | `amd64` | `x64` | `qemu-system-x86_64` | `q35` | legacy |
| `rtd1619b` | detected `amd64` or `arm64` | `arm64` | `arm64` | `qemu-system-aarch64` | `virt`, GICv3 | direct kernel |

`CONTAINER_ARCH` describes the runtime container CPU (`uname -m`, normalized); it
does not identify the Docker host when emulation is involved. The inherited
qemux `ARCH` continues to describe its Debian image. Only `DSM_PLATFORM` selects
DSM hardware policy. Unknown selectors fail early.

`DOCKDSM_HOST_ARCH` optionally supplies the Docker host CPU when the runtime
cannot detect it. It accepts normalized `amd64`/`arm64` and `uname -m` spellings
`x86_64`/`x86_64h`/`aarch64`; these are canonicalized before architecture checks.

## VirtualDSM installation recovery

The x86 installer reuses a complete nonempty boot/system image pair for the
selected PAT base. If either path exists but the pair is incomplete (including
empty files or broken symlinks), startup fails with exit 65 before deleting the
selected images or cached PAT. The check also applies after default URL discovery.
Restore the matching pair from a backup, or use a separate empty storage directory
for a new installation; startup does not automatically repair a partial pair.

## Shared lifecycle and platform API

`entry.sh` sources `platform/common.sh` after the startup hook and utilities,
and selects policy before inherited initialization or argument construction.
Common initialization, memory checks, startup page preparation, download helpers,
launch preparation, shutdown handling and the final QEMU launch remain shared.

- `platformInit` validates the selector, loads one whitelisted implementation,
  detects host architecture and calls `platformDefaults`.
- `platformDefaults` sets guest architecture, the qemux architecture alias,
  emulator, machine and boot policy.
- `platformRunStage` runs a named lifecycle stage. VirtualDSM sources the original
  install/disk/display/network/boot/proc/serial/balloon/config scripts in their
  original order. DS124 substitutes only its hardware-specific policies, and
  never enters the VirtualDSM installer.
- `platformPrepareSystemDisks` retains VirtualDSM `createDevice` calls, synoboot,
  synosys and PCI addresses; DS124 attaches one IDE backend to patched sysbus AHCI.
- `platformValidateBinary` accepts only the two known executable names and
  verifies the selected executable exists.
- `platformBuildCommand` produces `QEMU_ARGS`, an argv array used directly by
  the shared launcher. VirtualDSM splits its existing argument string once;
  DS124 constructs arrays throughout. Neither path evaluates shell code.
- `platformInteractiveConsole` retains the x86 managed console. DS124 uses
  MMIO ttyS0 through stdio, without the qemu-host VirtIO channel.
- `platformGuestShutdown` retains the x86 serial API. Phase 1 DS124 has no
  supported shutdown agent: shut down DSM through its UI before container stop;
  the fallback terminates QEMU within the existing shutdown lifecycle.

The DS124 implementation additionally exposes `platformValidateArtifacts`,
`platformConfigureCpu`, `platformKvmProbe`, `platformConfigureNetwork`,
`platformNetworkBackend`, `platformNetworkDevice`, and
`platformConfigureArguments`. Backend forwarding and USB device presentation
are independent decisions. Machine devices and LED nodes come from the two
production patches, rather than extra PCI command-line devices.

## Phase 2 automatic artifacts

Experimental ARM support is limited to Synology DS124 / rtd1619b running DSM
7.2.2-72806. The accepted official PAT SHA256 is
`17f48a9a4572c9b3b994921d3fb410d8186e9c4bf02cf9334e37897e5752e1dd`;
other DSM builds and other Realtek models are unvalidated. Automatic preparation
requires this exact official PAT. See [automatic preparation](arm64-auto-install.md)
for supported identity, safety, root construction, generation publication,
cache/legacy policy. See the [Phase 3 local setup and storage evidence](../research/arm64/production-phase3.md)
for the official administrator wizard, bundled Storage Manager prerequisite and
single-disk Basic/Btrfs creation.

New seeds include clock initialization and bundled-package handoff, described in
[package installation](package-installation.md). Older setup evidence predates
these integrations; existing runtime disks require the documented explicit migration.

```text
/storage/DSM_DS124_72806.kernel
/storage/DSM_DS124_72806.initrd
/storage/DSM_DS124_72806.system.img
/storage/DSM_DS124_72806.arm.json
```

The production runtime retains the validated Phase 1 hardware contract and
adds the Phase 3 control UART and private QMP shutdown observer. Stock
kernel/initramfs stay unmodified. The builder uses the validated research p1 geometry and does
not produce p2/p3 or canonical physical DS124 geometry. `platformPrepareArtifacts`
shares PAT acquisition and extraction with VirtualDSM; ARM-specific construction
is owned by production helpers. `platformSealArtifacts` validates and records the
runtime shutdown observations after QEMU stops; mutable disk hashes never
trigger rebuilding. See [ARM runtime state](arm64-runtime-state.md).

## CPU and hardware policy

DS124 on an amd64 host uses `-accel tcg,thread=multi -cpu max,lpa2=off`; startup
is substantially slower than KVM. On ARM64, requested KVM requires matching
host/guest architecture and accessible `/dev/kvm`. A successful paused
virt/GICv3 initialization probe using `-accel kvm -cpu host` permits launch;
missing or inaccessible KVM, or a failed probe, falls back to TCG with one
actionable warning. A probe timeout is inconclusive, so DockDSM attempts the
requested KVM launch and reports any QEMU failure without claiming that KVM
works. `KVM=N` explicitly selects TCG without a downgrade warning. CPU policies
remain accelerator-specific; `lpa2=off` is not added to KVM.

Accepted KVM evidence is Apple MacBook Air M5 running macOS, Colima Apple VZ,
ARM64 Ubuntu and nested KVM. It validates that environment only. Bare-metal
ARM64 Linux and other CPU hosts remain untested. The guest watchdog was not
changed. QEMU patch 0004 addresses the TCG AArch64 DC ZVA code-protection slow
path with conservative full-page translated-code invalidation; it does not
disable or reconfigure the guest watchdog. See the
[Phase 4A validation and evidence](../research/arm64/production-phase4a.md).

## Storage and lifecycle boundaries

The proven disk is a **DSM-compatible virtual storage layout**, not the
canonical physical DS124 layout. It has a fixed installed root seed, sparse
total SATA capacity, and a DSM-created data partition and volume. Only the
single-disk Basic/Btrfs path is validated; RAID and other disk layouts are
unvalidated. Existing runtime state is protected from automatic replacement.
For reinstall, stop the container, retain the old storage directory for
recovery, and explicitly select a new empty storage location. DSM upgrades
beyond 7.2.2-72806 are unsupported/unvalidated.

Use DSM's normal UI shutdown before stopping the container. A private QMP
receipt is clean only when QEMU reports guest `guest-shutdown` and exits 0.
Container SIGTERM/SIGKILL after a timeout is a bounded host fallback and is
recorded as unclean. The global Docker healthcheck start period remains 900
seconds because amd64-to-ARM TCG startup can take several minutes; shortening
the global window risks marking a valid TCG boot unhealthy.

## Validated network path

The DS124 guest uses sysbus XHCI, USB CDC ECM, QEMU user-mode NAT and `hostfwd`
for management ports. The guest is not transparently present on the host's
layer-2 LAN. Discovery protocols and camera/device discovery may not work as
they do on a bridged NAS. TAP and bridge networking are not the default and
have not been validated.

Surveillance Station manual-IP/RTSP use has not been validated on this path.
The read-only probe and per-platform acceptance steps are in
[Surveillance Station verification](surveillance-station.md).

The stock drivers use the production patches' MMIO 16550 at `0x0b000000`,
`realtek,ahci-sata` sysbus AHCI, and `generic-xhci` sysbus XHCI. The system disk
uses `-drive file=...,format=raw,if=ide,index=0`. The serial sequence is
`-serial null -serial stdio -serial null`: QEMU's original PL011 consumes serial index 0,
the console MMIO 16550 consumes index 1, and the control MMIO 16550 at
`0x0b010000` consumes index 2 as guest ttyS1. Stock DS124 writes this port
before kernel poweroff. The validated command line includes
`earlycon=uart8250,mmio32,0x0b000000 console=ttyS0,115200`, normal `/init`,
`root=/dev/sata1p1`, and `libata.force=noncq`.

The guest NIC is `usb-net`, with CDC ECM and stock `usbnet`/`cdc_ether`.
The LED patch creates syscon/simple-mfd, register-bit-led and `internal_slot@1`
to prevent the known ds124_synobios NULL LED / LedSetLock / scemd soft lockup.
It is mandatory even when management HTTP seems functional.

## Network and management ports

Phase 1 DS124 supports `NETWORK=user` (also the default `Y`) or disabled `N`.
Guest DHCP is QEMU user networking, normally `10.0.2.15`; qemux `DHCP=Y`
bridge mode is not yet available. Tap, bridge and additional guest disks are
not integrated for this platform. No x86 PCI NIC is instantiated.

| Variable | DS124 default | Meaning |
|---|---|---|
| `WEB_PORT` | `5000` | Container TCP port forwarded to guest DSM HTTP 5000 |
| `DSM_HTTPS_PORT` | `5001` | Container TCP port forwarded to guest DSM HTTPS 5001 |
| `DSM_BIND` | `0.0.0.0` | Bind inside container; only `0.0.0.0` and `127.0.0.1` accepted |
| `USER_PORTS` | empty | Opt-in comma-separated same-port forwards, e.g. `22,53/udp` |
| `VM_NET_MAC` / `MAC` | `00:16:3e:12:34:56` | USB NIC MAC property; guest CDC MAC starts with `40` in validated QEMU |

Port inputs must be decimal 1-65535, protocols TCP/UDP, without duplicates.
`HOST_PORTS`, arbitrary QEMU overrides (`ARGUMENTS`, `QMP`, `MONITOR`) and
other networking modes are rejected in this initial platform implementation.
The inherited startup web server is disabled for DS124, so it does not collide
with the direct management forward. The health check polls the forwarded HTTP
port without the x86 proprietary guest-agent channel.

Publish only the ports you choose; no host ports are opened automatically:

```bash
docker run --name ds124 --env DSM_PLATFORM=rtd1619b --env NETWORK=user \
  --volume /your/prepared/storage:/storage \
  --publish 127.0.0.1:5000:5000 --publish 127.0.0.1:5001:5001 \
  virtual-dsm:phase1
```

Do not use host networking if you want Docker publication to control exposure.
On amd64 this uses TCG and is much slower than matching-architecture KVM.

## Production emulator build and tests

`Dockerfile` builds native target-architecture QEMU v8.2.2 in a separate Debian
builder with `--target-list=aarch64-softmmu`; it does not use BUILDPLATFORM for
the emulator build. The runtime inherits qemux/qemu:7.50 unchanged and adds
`/usr/local/bin/qemu-system-aarch64`. Required runtime libraries are installed
from the runtime distribution and checked using `ldd` plus both `--version`
commands. The x86 emulator remains inherited. No proprietary artifacts enter
Git or the Docker build context.

The patch source of truth is [patches/qemu/8.2.2](../patches/qemu/8.2.2/README.md).
The research build helper consumes those same files. Lightweight CI runs
platform snapshots, invalid-input tests, research smoke checks, read-only image
validation using a synthetic ext filesystem, shellcheck and clean patch apply.
The separate manually dispatched QEMU workflow uses native amd64/arm64 runners;
it does not download DSM or compile QEMU in the lightweight test job.

Run locally:

```bash
bash tests/platform.sh
bash tests/qemu-patches.sh
python3 tests/image-validation.py
bash research/arm64/tests/smoke.sh
shellcheck -x src/*.sh src/platform/*.sh research/arm64/*.sh research/arm64/tests/*.sh
git diff --check
```

The production boot regression uses the built image's actual `/run/entry.sh`
and an official PAT and empty storage; research launchers are not used. See the
[research evidence and graduated contracts](arm64-development.md).
