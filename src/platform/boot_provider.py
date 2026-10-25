"""Versioned, side-effect-free contracts for planning a single QEMU VM launch.

This module is an internal interface foundation. It does not register DSM
platform selectors, access storage, start containers, or execute QEMU.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Protocol, Sequence


SCHEMA_VERSION = 1
ARCHITECTURES = frozenset(("amd64", "arm64"))
ACCELERATORS = frozenset(("kvm", "tcg"))


class ContractError(ValueError):
    """A closed contract or launch-plan input is invalid."""


def _object(value: object, fields: frozenset[str], name: str) -> dict:
    if not isinstance(value, dict) or set(value) != fields:
        raise ContractError(f"{name} fields do not match schema version {SCHEMA_VERSION}")
    return value


def _text(value: object, name: str) -> str:
    if not isinstance(value, str) or not value or "\x00" in value:
        raise ContractError(f"{name} must be a nonempty string without NUL")
    return value


def _architecture(value: object, name: str) -> str:
    result = _text(value, name)
    if result not in ARCHITECTURES:
        raise ContractError(f"unsupported {name}: {result}")
    return result


def _machine_from_argv(argv: tuple[str, ...]) -> str:
    values = []
    for index, item in enumerate(argv):
        if item in ("-machine", "-M"):
            if index + 1 >= len(argv):
                raise ContractError("QEMU machine option has no value")
            values.append(argv[index + 1])
        elif item.startswith("-machine="):
            values.append(item.partition("=")[2])
    if len(values) != 1:
        raise ContractError("QEMU argv must select exactly one machine")
    machine = values[0].split(",", 1)[0]
    return machine[5:] if machine.startswith("type=") else machine


def _accelerator_from_argv(argv: tuple[str, ...]) -> str:
    """Resolve QEMU accelerator spellings and reject contradictory argv."""
    requested = []
    machine_values = []
    index = 0
    while index < len(argv):
        item = argv[index]
        if item in ("-machine", "-M"):
            if index + 1 >= len(argv):
                raise ContractError("QEMU machine option has no value")
            machine_values.append(argv[index + 1])
            index += 2
            continue
        if item.startswith("-machine="):
            machine_values.append(item.partition("=")[2])
        elif item == "-enable-kvm":
            requested.append("kvm")
        elif item == "-no-kvm":
            requested.append("tcg")
        elif item in ("-accel", "-accel="):
            if item == "-accel":
                if index + 1 >= len(argv):
                    raise ContractError("QEMU accelerator option has no value")
                value = argv[index + 1]
                index += 1
            else:
                value = item.partition("=")[2]
            requested.append(value.split(",", 1)[0])
        elif item.startswith("-accel="):
            requested.append(item.partition("=")[2].split(",", 1)[0])
        index += 1

    for machine in machine_values:
        values = [part.partition("=")[2] for part in machine.split(",")
                  if part.startswith("accel=")]
        if len(values) > 1:
            raise ContractError("QEMU machine selects multiple accelerators")
        requested.extend(values)
    if any(value not in ACCELERATORS for value in requested):
        raise ContractError("QEMU argv selects an unsupported accelerator")
    if len(set(requested)) > 1:
        raise ContractError("QEMU argv contains conflicting accelerator options")
    return requested[0] if requested else "tcg"


@dataclass(frozen=True)
class Profile:
    """Describes the DSM guest and its selected boot provider."""

    id: str
    dsm_platform: str
    guest_arch: str
    boot_provider: str
    qemu_machine: str
    bootloader_arch: str | None = None
    schema_version: int = SCHEMA_VERSION

    def __post_init__(self) -> None:
        if type(self.schema_version) is not int or self.schema_version != SCHEMA_VERSION:
            raise ContractError("unsupported Profile schema version")
        for name in ("id", "dsm_platform", "boot_provider", "qemu_machine"):
            _text(getattr(self, name), name)
        _architecture(self.guest_arch, "guest_arch")
        if self.bootloader_arch is not None:
            _architecture(self.bootloader_arch, "bootloader_arch")

    def to_dict(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "id": self.id,
            "dsm_platform": self.dsm_platform,
            "guest_arch": self.guest_arch,
            "boot_provider": self.boot_provider,
            "qemu_machine": self.qemu_machine,
            "bootloader_arch": self.bootloader_arch,
        }

    @classmethod
    def from_dict(cls, value: object) -> Profile:
        data = _object(value, frozenset(("schema_version", "id", "dsm_platform",
                                         "guest_arch", "boot_provider", "qemu_machine",
                                         "bootloader_arch")), "Profile")
        version = data["schema_version"]
        if type(version) is not int or version != SCHEMA_VERSION:
            raise ContractError("unsupported Profile schema version")
        bootloader_arch = data["bootloader_arch"]
        if bootloader_arch is not None:
            _architecture(bootloader_arch, "bootloader_arch")
        return cls(data["id"], data["dsm_platform"], data["guest_arch"],
                   data["boot_provider"], data["qemu_machine"], bootloader_arch, version)


@dataclass(frozen=True)
class HostCapabilities:
    """Records outer host and container facts without inferring guest support."""

    host_arch: str | None
    container_arch: str
    qemu_binaries: tuple[str, ...]
    kvm_access: bool | None
    kvm_probe: bool | None
    schema_version: int = SCHEMA_VERSION

    def __post_init__(self) -> None:
        if type(self.schema_version) is not int or self.schema_version != SCHEMA_VERSION:
            raise ContractError("unsupported HostCapabilities schema version")
        if self.host_arch is not None:
            _architecture(self.host_arch, "host_arch")
        _architecture(self.container_arch, "container_arch")
        if not isinstance(self.qemu_binaries, tuple) or any(
                not isinstance(item, str) or not item or "\x00" in item
                for item in self.qemu_binaries):
            raise ContractError("qemu_binaries must be a tuple of executable names")
        if len(set(self.qemu_binaries)) != len(self.qemu_binaries):
            raise ContractError("qemu_binaries contains duplicates")
        for name in ("kvm_access", "kvm_probe"):
            value = getattr(self, name)
            if value is not None and type(value) is not bool:
                raise ContractError(f"{name} must be true, false, or unknown")

    def to_dict(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "host_arch": self.host_arch,
            "container_arch": self.container_arch,
            "qemu_binaries": list(self.qemu_binaries),
            "kvm_access": self.kvm_access,
            "kvm_probe": self.kvm_probe,
        }

    @classmethod
    def from_dict(cls, value: object) -> HostCapabilities:
        data = _object(value, frozenset(("schema_version", "host_arch", "container_arch",
                                         "qemu_binaries", "kvm_access", "kvm_probe")), "HostCapabilities")
        version = data["schema_version"]
        binaries = data["qemu_binaries"]
        if type(version) is not int or version != SCHEMA_VERSION:
            raise ContractError("unsupported HostCapabilities schema version")
        if not isinstance(binaries, list):
            raise ContractError("qemu_binaries must be an array")
        for name in ("kvm_access", "kvm_probe"):
            if data[name] is not None and type(data[name]) is not bool:
                raise ContractError(f"{name} must be true, false, or unknown")
        return cls(data["host_arch"], data["container_arch"], tuple(binaries),
                   data["kvm_access"], data["kvm_probe"], version)


@dataclass(frozen=True)
class VMConfig:
    """Inputs accepted by a provider when it builds a plan; never an executor."""

    profile_id: str
    runtime_adapter: str
    storage_ref: str
    vcpus: int
    memory_mib: int
    schema_version: int = SCHEMA_VERSION

    def __post_init__(self) -> None:
        if type(self.schema_version) is not int or self.schema_version != SCHEMA_VERSION:
            raise ContractError("unsupported VMConfig schema version")
        for name in ("profile_id", "runtime_adapter", "storage_ref"):
            _text(getattr(self, name), name)
        if type(self.vcpus) is not int or self.vcpus < 1:
            raise ContractError("vcpus must be a positive integer")
        if type(self.memory_mib) is not int or self.memory_mib < 1:
            raise ContractError("memory_mib must be a positive integer")

    def to_dict(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "profile_id": self.profile_id,
            "runtime_adapter": self.runtime_adapter,
            "storage_ref": self.storage_ref,
            "vcpus": self.vcpus,
            "memory_mib": self.memory_mib,
        }

    @classmethod
    def from_dict(cls, value: object) -> VMConfig:
        data = _object(value, frozenset(("schema_version", "profile_id", "runtime_adapter",
                                         "storage_ref", "vcpus", "memory_mib")), "VMConfig")
        version = data["schema_version"]
        if type(version) is not int or version != SCHEMA_VERSION:
            raise ContractError("unsupported VMConfig schema version")
        return cls(data["profile_id"], data["runtime_adapter"], data["storage_ref"],
                   data["vcpus"], data["memory_mib"], version)


@dataclass(frozen=True)
class LaunchPlan:
    """Immutable description of one VM launch, with its argv kept as an array."""

    profile_id: str
    boot_provider: str
    host_arch: str | None
    container_arch: str
    guest_arch: str
    bootloader_arch: str | None
    qemu_machine: str
    runtime_adapter: str
    storage_ref: str
    qemu_argv: tuple[str, ...]
    accelerator: str
    schema_version: int = SCHEMA_VERSION

    def __post_init__(self) -> None:
        if type(self.schema_version) is not int or self.schema_version != SCHEMA_VERSION:
            raise ContractError("unsupported LaunchPlan schema version")
        for name in ("profile_id", "boot_provider", "qemu_machine", "runtime_adapter", "storage_ref"):
            _text(getattr(self, name), name)
        if self.host_arch is not None:
            _architecture(self.host_arch, "host_arch")
        for name in ("container_arch", "guest_arch"):
            _architecture(getattr(self, name), name)
        if self.bootloader_arch is not None:
            _architecture(self.bootloader_arch, "bootloader_arch")
        if not isinstance(self.qemu_argv, tuple) or not self.qemu_argv:
            raise ContractError("qemu_argv must be a nonempty argv tuple")
        if any(not isinstance(item, str) or "\x00" in item for item in self.qemu_argv):
            raise ContractError("qemu_argv entries must be strings without NUL")
        expected_binary = "qemu-system-x86_64" if self.guest_arch == "amd64" else "qemu-system-aarch64"
        if Path(self.qemu_argv[0]).name != expected_binary:
            raise ContractError("QEMU executable does not match guest_arch")
        if _machine_from_argv(self.qemu_argv) != self.qemu_machine:
            raise ContractError("QEMU machine does not match LaunchPlan")
        if self.accelerator not in ACCELERATORS:
            raise ContractError("unsupported accelerator")
        if _accelerator_from_argv(self.qemu_argv) != self.accelerator:
            raise ContractError("QEMU argv accelerator does not match LaunchPlan")

    def to_dict(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "profile_id": self.profile_id,
            "boot_provider": self.boot_provider,
            "host_arch": self.host_arch,
            "container_arch": self.container_arch,
            "guest_arch": self.guest_arch,
            "bootloader_arch": self.bootloader_arch,
            "qemu_machine": self.qemu_machine,
            "runtime_adapter": self.runtime_adapter,
            "storage_ref": self.storage_ref,
            "qemu_argv": list(self.qemu_argv),
            "accelerator": self.accelerator,
        }

    @classmethod
    def from_dict(cls, value: object) -> LaunchPlan:
        fields = frozenset(("schema_version", "profile_id", "boot_provider", "host_arch",
                            "container_arch", "guest_arch", "bootloader_arch", "qemu_machine",
                            "runtime_adapter", "storage_ref", "qemu_argv", "accelerator"))
        data = _object(value, fields, "LaunchPlan")
        version = data["schema_version"]
        argv = data["qemu_argv"]
        if type(version) is not int or version != SCHEMA_VERSION:
            raise ContractError("unsupported LaunchPlan schema version")
        if data["bootloader_arch"] is not None:
            _architecture(data["bootloader_arch"], "bootloader_arch")
        if data["host_arch"] is not None:
            _architecture(data["host_arch"], "host_arch")
        if not isinstance(argv, list):
            raise ContractError("qemu_argv must be an array")
        return cls(data["profile_id"], data["boot_provider"], data["host_arch"],
                   data["container_arch"], data["guest_arch"], data["bootloader_arch"],
                   data["qemu_machine"],
                   data["runtime_adapter"], data["storage_ref"], tuple(argv),
                   data["accelerator"], version)

    @property
    def plan_hash(self) -> str:
        payload = json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(payload).hexdigest()


class BootProvider(Protocol):
    """A fixed in-process provider. Profiles never load executable plugins."""

    provider_id: str

    def build_plan(self, profile: Profile, config: VMConfig,
                   host: HostCapabilities, qemu_argv: Sequence[str],
                   accelerator: str) -> LaunchPlan: ...


@dataclass(frozen=True)
class QemuArgvProvider:
    """Wrap already validated legacy QEMU argv as a deterministic plan."""

    provider_id: str

    def build_plan(self, profile: Profile, config: VMConfig,
                   host: HostCapabilities, qemu_argv: Sequence[str],
                   accelerator: str) -> LaunchPlan:
        if profile.boot_provider != self.provider_id:
            raise ContractError("profile/provider mismatch")
        if config.profile_id != profile.id:
            raise ContractError("config/profile mismatch")
        if accelerator not in ACCELERATORS:
            raise ContractError("unsupported accelerator")
        if accelerator == "kvm" and (
                host.kvm_access is not True or host.kvm_probe is not True
                or host.container_arch != profile.guest_arch
                or (host.host_arch is not None and host.host_arch != profile.guest_arch)):
            raise ContractError("KVM requires device access, a successful QEMU probe, and compatible known architectures")
        argv = tuple(qemu_argv)
        expected_binary = "qemu-system-x86_64" if profile.guest_arch == "amd64" else "qemu-system-aarch64"
        if expected_binary not in host.qemu_binaries:
            raise ContractError("required QEMU binary is not available in host capabilities")
        if _machine_from_argv(argv) != profile.qemu_machine:
            raise ContractError("QEMU machine does not match profile")
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
            qemu_argv=argv,
            accelerator=accelerator,
        )
