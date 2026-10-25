"""Internal QEMU provider for the open ARM64 Linux kexec research chain."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from boot_provider import (  # imported from the adjacent platform module
    ContractError,
    HostCapabilities,
    LaunchPlan,
    Profile,
    VMConfig,
)


PROVIDER_ID = "arm64-linux-kexec"
DSM_PROVIDER_ID = "arm64-dsm-kexec"
DSM_SCRATCH_DISK = "dockdsm-ds124-scratch-sata1.img"
DSM_SCRATCH_DISK_BYTES = 2 * 1024 * 1024 * 1024
BOOTARGS = "console=ttyAMA0,115200 earlycon=pl011,0x09000000 rdinit=/init loglevel=7 nokaslr"
_PROFILES = {
    PROVIDER_ID: ("research-arm64-linux-kexec", "open-linux"),
    DSM_PROVIDER_ID: ("research-arm64-dsm-kexec", "rtd1619b"),
}


@dataclass(frozen=True)
class LinuxKexecProvider:
    """Create an isolated TCG plan for the ARM64 Linux/DS124 kexec lab."""

    provider_id: str = PROVIDER_ID

    def build_plan(self, profile: Profile, config: VMConfig,
                   host: HostCapabilities, kernel_image: str,
                   loader_initrd: str,
                   qemu_binary: str = "qemu-system-aarch64",
                   cpu: str = "cortex-a57", gic_version: int = 2,
                   its: bool | None = None,
                   loader_disable_lpi: bool = False,
                   serial_route: str = "pl011",
                   scratch_sata1: str | None = None,
                   scratch_sata1_snapshot: bool = False) -> LaunchPlan:
        expected = _PROFILES.get(self.provider_id)
        if expected is None or (profile.id, profile.dsm_platform) != expected \
                or profile.boot_provider != self.provider_id:
            raise ContractError("profile/provider mismatch")
        if (profile.guest_arch, profile.bootloader_arch, profile.qemu_machine) != (
                "arm64", "arm64", "virt"):
            raise ContractError("ARM64 kexec provider requires an ARM64 virt profile")
        if config.profile_id != profile.id:
            raise ContractError("config/profile mismatch")
        if config.runtime_adapter != "qemu-process":
            raise ContractError("ARM64 kexec research requires a qemu-process runtime")
        if type(scratch_sata1_snapshot) is not bool:
            raise ContractError("scratch SATA snapshot setting must be a boolean")
        if self.provider_id == PROVIDER_ID:
            if (config.storage_ref != "none" or scratch_sata1 is not None
                    or scratch_sata1_snapshot):
                raise ContractError("open Linux handoff requires a diskless QEMU process")
        elif scratch_sata1 is None:
            if scratch_sata1_snapshot:
                raise ContractError("SATA snapshot mode requires the isolated scratch disk")
            if config.storage_ref != "none":
                raise ContractError("diskless DS124 handoff requires storage_ref=none")
        else:
            expected_storage = "scratch-sata1-snapshot" if scratch_sata1_snapshot else "scratch-sata1"
            if config.storage_ref != expected_storage:
                raise ContractError(f"DS124 disk probe requires storage_ref={expected_storage}")
            scratch_sata1 = self._scratch_disk(scratch_sata1)
        if cpu not in ("cortex-a57", "cortex-a55", "max,lpa2=off"):
            raise ContractError("unsupported ARM64 kexec research CPU model")
        if gic_version not in (2, 3):
            raise ContractError("ARM64 kexec research GIC version must be 2 or 3")
        if its is not None and type(its) is not bool:
            raise ContractError("ARM64 kexec research ITS setting must be true, false, or omitted")
        if gic_version == 2 and its is not None:
            raise ContractError("QEMU ITS setting is valid only with GICv3")
        if type(loader_disable_lpi) is not bool:
            raise ContractError("loader LPI setting must be a boolean")
        if loader_disable_lpi and (gic_version != 3 or its is False):
            raise ContractError("loader LPI suppression requires GICv3 with ITS enabled")
        if config.vcpus not in (1, 2, 4) or config.memory_mib not in (512, 1024, 2048):
            raise ContractError("unsupported ARM64 kexec research vCPU or memory size")
        if serial_route not in ("pl011", "dsm-mmio16550"):
            raise ContractError("unsupported ARM64 kexec research serial route")
        if self.provider_id == DSM_PROVIDER_ID and (
                cpu != "max,lpa2=off" or gic_version != 3 or its is not True
                or not loader_disable_lpi or config.vcpus != 2
                or config.memory_mib != 2048 or serial_route != "dsm-mmio16550"):
            raise ContractError("DS124 kexec lab requires max,lpa2=off, GICv3 ITS, loader LPI suppression, 2 vCPUs, 2048 MiB, and the DSM MMIO serial route")
        if self.provider_id == PROVIDER_ID and serial_route != "pl011":
            raise ContractError("open Linux kexec tests require the PL011 serial route")
        if host.host_arch != host.container_arch:
            raise ContractError("research QEMU process must run in its native container architecture")
        if (not isinstance(qemu_binary, str) or not qemu_binary
                or "\x00" in qemu_binary
                or Path(qemu_binary).name != "qemu-system-aarch64"):
            raise ContractError("QEMU executable must be qemu-system-aarch64")
        if Path(qemu_binary).name not in host.qemu_binaries:
            raise ContractError("qemu-system-aarch64 is not available")

        kernel = self._artifact(kernel_image, "kernel image")
        initrd = self._artifact(loader_initrd, "loader initramfs")
        machine = f"virt,accel=tcg,gic-version={gic_version},dtb-kaslr-seed=off"
        if its is not None:
            machine += f",its={'on' if its else 'off'}"
        bootargs = BOOTARGS
        if loader_disable_lpi:
            bootargs += " irqchip.gicv3_nolpi=1"
        argv: Sequence[str] = (
            qemu_binary,
            "-machine", machine,
            "-cpu", cpu,
            "-smp", str(config.vcpus),
            "-m", str(config.memory_mib),
            "-nic", "none",
            "-kernel", kernel,
            "-initrd", initrd,
            "-append", bootargs,
            "-nographic",
            "-monitor", "none",
        )
        if scratch_sata1 is not None:
            drive = f"file={scratch_sata1},format=raw,if=ide,index=0"
            if scratch_sata1_snapshot:
                drive += ",snapshot=on"
            argv += ("-drive", drive)
        if serial_route == "dsm-mmio16550":
            argv += ("-serial", "null", "-serial", "stdio")
        argv += ("-no-reboot",)
        return LaunchPlan(
            profile_id=profile.id,
            boot_provider=self.provider_id,
            host_arch=host.host_arch,
            container_arch=host.container_arch,
            guest_arch=profile.guest_arch,
            bootloader_arch=profile.bootloader_arch,
            qemu_machine=profile.qemu_machine,
            runtime_adapter=config.runtime_adapter,
            storage_ref=config.storage_ref,
            qemu_argv=tuple(argv),
            accelerator="tcg",
        )

    @staticmethod
    def _artifact(value: str, name: str) -> str:
        if not isinstance(value, str) or not value or "\x00" in value:
            raise ContractError(f"{name} path must be a nonempty string without NUL")
        try:
            path = Path(value).resolve(strict=True)
            if not path.is_file() or path.stat().st_size == 0:
                raise ContractError(f"{name} is missing, not a regular file, or empty")
        except OSError as error:
            raise ContractError(f"{name} cannot be read") from error
        return str(path)

    @staticmethod
    def _scratch_disk(value: str) -> str:
        """Accept only the fresh, private, fixed-size SATA probe image."""
        if not isinstance(value, str) or not value or "\x00" in value:
            raise ContractError("scratch SATA image path must be a nonempty string")
        raw = Path(value)
        if raw.name != DSM_SCRATCH_DISK or raw.is_symlink():
            raise ContractError("DS124 probe requires its fixed regular scratch image")
        try:
            path = raw.resolve(strict=True)
            metadata = path.stat()
            repo_root = Path(__file__).resolve().parents[2]
            if (not path.is_file() or metadata.st_size != DSM_SCRATCH_DISK_BYTES
                    or metadata.st_nlink != 1 or metadata.st_blocks != 0
                    or path.parent.stat().st_mode & 0o077
                    or repo_root == path or repo_root in path.parents):
                raise ContractError("DS124 scratch SATA image is not private, isolated, and exactly 2 GiB")
        except OSError as error:
            raise ContractError("DS124 scratch SATA image cannot be read") from error
        if any(character in str(path) for character in (",", "\n", "\r")):
            raise ContractError("scratch SATA image path contains a QEMU drive-option separator")
        return str(path)
