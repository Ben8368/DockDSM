"""Internal ARM64 UEFI/GRUB provider for the open Linux research chain."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from boot_provider import ContractError, HostCapabilities, LaunchPlan, Profile, VMConfig


PROVIDER_ID = "arm64-grub-efi"
PROFILE_ID = "research-arm64-grub-linux"


@dataclass(frozen=True)
class Arm64GrubProvider:
    """Build a read-only, disk-isolated ARM64 UEFI/GRUB TCG plan."""

    provider_id: str = PROVIDER_ID

    def build_plan(self, profile: Profile, config: VMConfig,
                   host: HostCapabilities, disk_image: str, firmware: str,
                   qemu_binary: str = "qemu-system-aarch64",
                   cpu: str = "cortex-a57") -> LaunchPlan:
        if self.provider_id != PROVIDER_ID or (
                profile.id, profile.dsm_platform, profile.boot_provider) != (
                PROFILE_ID, "open-linux", self.provider_id):
            raise ContractError("profile/provider mismatch")
        if (profile.guest_arch, profile.bootloader_arch, profile.qemu_machine) != (
                "arm64", "arm64", "virt"):
            raise ContractError("ARM64 GRUB provider requires an ARM64 virt profile")
        if config.profile_id != profile.id:
            raise ContractError("config/profile mismatch")
        if config.runtime_adapter != "qemu-process":
            raise ContractError("ARM64 GRUB research requires a qemu-process runtime")
        if config.storage_ref != "none":
            raise ContractError("ARM64 GRUB research requires isolated read-only boot media")
        if config.vcpus not in (1, 2, 4) or config.memory_mib not in (512, 1024, 2048):
            raise ContractError("unsupported ARM64 GRUB research vCPU or memory size")
        if cpu != "cortex-a57":
            raise ContractError("unsupported ARM64 GRUB research CPU model")
        if (not isinstance(qemu_binary, str) or not qemu_binary
                or "\x00" in qemu_binary
                or Path(qemu_binary).name != "qemu-system-aarch64"):
            raise ContractError("QEMU executable must be qemu-system-aarch64")
        if Path(qemu_binary).name not in host.qemu_binaries:
            raise ContractError("qemu-system-aarch64 is not available")

        image = self._artifact(disk_image, "ARM64 GRUB disk image")
        firmware_path = self._artifact(firmware, "AArch64 UEFI firmware")
        if "," in image:
            raise ContractError("ARM64 GRUB disk path cannot contain QEMU drive-option separators")

        argv: Sequence[str] = (
            qemu_binary,
            "-machine", "virt,accel=tcg",
            "-cpu", cpu,
            "-smp", str(config.vcpus),
            "-m", f"{config.memory_mib}M",
            "-bios", firmware_path,
            "-drive", f"file={image},format=raw,if=none,id=boot,readonly=on",
            "-device", "virtio-blk-device,drive=boot",
            "-boot", "order=c",
            "-nic", "none",
            "-nographic",
            "-monitor", "none",
            "-no-reboot",
        )
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
