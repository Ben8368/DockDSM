"""Internal QEMU provider for the open x86_64 GRUB ISO research chain."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from boot_provider import ContractError, HostCapabilities, LaunchPlan, Profile, VMConfig


PROVIDER_ID = "x86_64-grub-iso"


@dataclass(frozen=True)
class GrubIsoProvider:
    """Build a diskless TCG BIOS or UEFI plan for the x86_64 GRUB ISO test VM."""

    provider_id: str = PROVIDER_ID

    def build_plan(self, profile: Profile, config: VMConfig,
                   host: HostCapabilities, iso_image: str,
                   qemu_binary: str = "qemu-system-x86_64",
                   firmware_code: str | None = None,
                   firmware_vars: str | None = None) -> LaunchPlan:
        if self.provider_id != PROVIDER_ID or profile.boot_provider != self.provider_id:
            raise ContractError("profile/provider mismatch")
        if profile.dsm_platform != "open-linux":
            raise ContractError("GRUB ISO provider is reserved for open Linux research")
        if (profile.guest_arch, profile.bootloader_arch, profile.qemu_machine) != (
                "amd64", "amd64", "q35"):
            raise ContractError("GRUB ISO provider requires an x86_64 q35 profile")
        if config.profile_id != profile.id:
            raise ContractError("config/profile mismatch")
        if config.runtime_adapter != "qemu-process" or config.storage_ref != "none":
            raise ContractError("GRUB ISO research requires a diskless QEMU process")
        if (not isinstance(qemu_binary, str) or not qemu_binary
                or "\x00" in qemu_binary
                or Path(qemu_binary).name != "qemu-system-x86_64"):
            raise ContractError("QEMU executable must be qemu-system-x86_64")
        if Path(qemu_binary).name not in host.qemu_binaries:
            raise ContractError("qemu-system-x86_64 is not available")

        iso = self._artifact(iso_image)
        if (firmware_code is None) != (firmware_vars is None):
            raise ContractError("UEFI requires both firmware code and variable-store template")
        firmware_args: tuple[str, ...] = ()
        if firmware_code is not None and firmware_vars is not None:
            code = self._artifact(firmware_code, "UEFI firmware code")
            variables = self._artifact(firmware_vars, "UEFI variable-store template")
            if "," in code or "," in variables:
                raise ContractError("UEFI firmware paths cannot contain QEMU drive-option separators")
            firmware_args = (
                "-drive", f"if=pflash,format=raw,readonly=on,file={code}",
                "-drive", f"if=pflash,format=raw,file={variables}",
            )
        argv: Sequence[str] = (
            qemu_binary,
            "-machine", "q35,accel=tcg",
            "-cpu", "max",
            "-smp", str(config.vcpus),
            "-m", str(config.memory_mib),
            *firmware_args,
            "-nic", "none",
            "-cdrom", iso,
            "-boot", "order=d",
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
    def _artifact(value: str, name: str = "GRUB ISO") -> str:
        if not isinstance(value, str) or not value or "\x00" in value:
            raise ContractError(f"{name} path must be a nonempty string without NUL")
        try:
            path = Path(value).resolve(strict=True)
            if not path.is_file() or path.stat().st_size == 0:
                raise ContractError(f"{name} is missing, not a regular file, or empty")
        except OSError as error:
            raise ContractError(f"{name} cannot be read") from error
        return str(path)
