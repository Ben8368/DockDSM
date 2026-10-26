"""Adapters for the two existing platform policies; no experimental selectors."""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path

from boot_provider import (
    ContractError,
    HostCapabilities,
    Profile,
    QemuArgvProvider,
    VMConfig,
    _accelerator_from_argv,
)
from profile_registry import legacy_profile


@dataclass(frozen=True)
class LegacyPlatformFacts:
    dsm_platform: str
    guest_arch: str
    qemux_platform: str
    qemu_binary: str
    qemu_machine: str
    boot_mode: str


@dataclass(frozen=True)
class LegacyProviderBinding:
    profile: Profile
    provider: QemuArgvProvider
    qemu_binary: str


_LEGACY_COMPATIBILITY = {
    "virtualdsm": ("x64", "legacy"),
    "rtd1619b": ("arm64", "direct"),
}


def bind_legacy_platform(facts: LegacyPlatformFacts) -> LegacyProviderBinding:
    """Bind only exact facts emitted by the current whitelisted platform scripts."""
    try:
        profile = legacy_profile(facts.dsm_platform)
    except ContractError:
        raise ContractError("platform has no implemented legacy Boot Provider")
    compatibility = _LEGACY_COMPATIBILITY.get(facts.dsm_platform)
    if compatibility is None:
        raise ContractError("legacy platform has no compatibility facts")
    guest_arch, qemux_platform, boot_mode = profile.guest_arch, *compatibility
    qemu_binary = ("qemu-system-x86_64" if guest_arch == "amd64"
                   else "qemu-system-aarch64")
    expected = LegacyPlatformFacts(
        profile.dsm_platform, guest_arch, qemux_platform,
        qemu_binary, profile.qemu_machine, boot_mode)
    if facts != expected:
        raise ContractError("legacy platform facts differ from the implemented profile")
    return LegacyProviderBinding(
        profile, QemuArgvProvider(profile.boot_provider), facts.qemu_binary)


def bind_legacy_environment(environment: dict[str, str]) -> LegacyProviderBinding:
    """Read the established platform globals without evaluating shell text."""
    names = ("DSM_PLATFORM", "GUEST_ARCH", "PLATFORM", "QEMU_BIN", "MACHINE", "BOOT_MODE")
    missing = [name for name in names if not environment.get(name)]
    if missing:
        raise ContractError("legacy platform environment is incomplete: " + ", ".join(missing))
    return bind_legacy_platform(LegacyPlatformFacts(
        dsm_platform=environment["DSM_PLATFORM"],
        guest_arch=environment["GUEST_ARCH"],
        qemux_platform=environment["PLATFORM"],
        qemu_binary=environment["QEMU_BIN"],
        qemu_machine=environment["MACHINE"],
        boot_mode=environment["BOOT_MODE"],
    ))


def _single_option(argv: tuple[str, ...], option: str) -> str:
    values = []
    index = 0
    while index < len(argv):
        item = argv[index]
        if item == option:
            if index + 1 >= len(argv):
                raise ContractError(f"QEMU {option} option has no value")
            values.append(argv[index + 1])
            index += 2
            continue
        if item.startswith(option + "="):
            values.append(item.partition("=")[2])
        index += 1
    if len(values) != 1:
        raise ContractError(f"QEMU argv must select exactly one {option}")
    return values[0]


def _positive_integer(value: str, name: str) -> int:
    match = re.match(r"^([1-9][0-9]*)(?:,|$)", value)
    if match:
        return int(match.group(1))
    for part in value.split(","):
        key, separator, item = part.partition("=")
        if separator and key == "cpus" and item.isdecimal() and int(item) > 0:
            return int(item)
    raise ContractError(f"QEMU {name} must declare a positive CPU count")


def _memory_mib(value: str) -> int:
    size = value.split(",", 1)[0]
    match = re.fullmatch(r"([0-9]+(?:\.[0-9]+)?)([KMGTP]?)(?:i?B)?", size, re.IGNORECASE)
    if not match:
        raise ContractError("QEMU memory size cannot be represented in MiB")
    try:
        amount = Decimal(match.group(1))
    except InvalidOperation as error:
        raise ContractError("QEMU memory size is invalid") from error
    unit = (match.group(2) or "M").upper()
    powers = {"K": -1, "M": 0, "G": 1, "T": 2, "P": 3}
    mib = amount * (Decimal(1024) ** powers[unit])
    if mib <= 0 or mib != mib.to_integral_value():
        raise ContractError("QEMU memory size must resolve to a positive whole MiB")
    return int(mib)


def _machine_spec(argv: tuple[str, ...]) -> str:
    index = 0
    values = []
    while index < len(argv):
        item = argv[index]
        if item in ("-machine", "-M"):
            if index + 1 >= len(argv):
                raise ContractError("QEMU machine option has no value")
            values.append(argv[index + 1])
            index += 2
            continue
        if item.startswith("-machine="):
            values.append(item.partition("=")[2])
        index += 1
    if len(values) != 1:
        raise ContractError("QEMU argv must select exactly one machine")
    return ",".join(part for part in values[0].split(",")
                    if not part.startswith("accel="))


def _probe_kvm(qemu_path: str, machine: str, device: str = "/dev/kvm") -> tuple[bool, bool | None]:
    accessible = Path(device).exists() and os.access(device, os.R_OK | os.W_OK)
    if not accessible:
        return False, False
    machine = ",".join(part for part in machine.split(",")
                        if not part.startswith("accel="))
    command = [qemu_path, "-machine", machine, "-accel", "kvm", "-cpu", "host",
               "-smp", "1", "-m", "128", "-nodefaults", "-display", "none",
               "-serial", "none", "-monitor", "stdio", "-S"]
    try:
        result = subprocess.run(command, input="quit\n", text=True,
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                timeout=10, check=False)
    except subprocess.TimeoutExpired:
        return True, None
    except OSError:
        return True, False
    return True, result.returncode == 0


def build_legacy_launch_plan(environment: dict[str, str], qemu_arguments: list[str],
                            *, kvm_device: str = "/dev/kvm"):
    """Plan the current argv, probing KVM only when the argv requests it."""
    binding = bind_legacy_environment(environment)
    if (not isinstance(qemu_arguments, list) or not qemu_arguments
            or any(not isinstance(item, str) or "\x00" in item for item in qemu_arguments)):
        raise ContractError("QEMU argv must be nonempty and contain no NUL")
    argv = (binding.qemu_binary, *qemu_arguments)
    accelerator = _accelerator_from_argv(argv)
    container_arch = environment.get("CONTAINER_ARCH", "")
    if container_arch in ("x86_64", "x86_64h"):
        container_arch = "amd64"
    elif container_arch in ("aarch64", "arm64"):
        container_arch = "arm64"
    if container_arch not in ("amd64", "arm64"):
        raise ContractError("CONTAINER_ARCH must be detected before planning QEMU")

    host_arch = environment.get("DOCKDSM_HOST_ARCH") or None
    if host_arch in ("x86_64", "x86_64h"):
        host_arch = "amd64"
    elif host_arch == "aarch64":
        host_arch = "arm64"
    kvm_access: bool | None = None
    kvm_probe: bool | None = None
    if accelerator == "kvm":
        qemu_path = shutil.which(binding.qemu_binary, path=environment.get("PATH"))
        if not qemu_path:
            raise ContractError("selected QEMU binary is not executable from PATH")
        already_probed = (environment.get("DOCKDSM_ARM_KVM_PROBED") == "true"
                          and binding.profile.id == "rtd1619b")
        if already_probed:
            kvm_access, kvm_probe = _probe_kvm_device_only(kvm_device)
            kvm_probe = bool(kvm_access)
        else:
            kvm_access, kvm_probe = _probe_kvm(
                qemu_path, _machine_spec(argv), kvm_device)

    host = HostCapabilities(host_arch, container_arch, (binding.qemu_binary,),
                            kvm_access, kvm_probe)
    config = VMConfig(
        binding.profile.id, "qemu-process",
        environment.get("STORAGE") or "/storage",
        _positive_integer(_single_option(tuple(qemu_arguments), "-smp"), "-smp"),
        _memory_mib(_single_option(tuple(qemu_arguments), "-m")),
    )
    return binding.provider.build_plan(
        binding.profile, config, host, argv, accelerator)


def _probe_kvm_device_only(device: str = "/dev/kvm") -> tuple[bool, bool]:
    accessible = Path(device).exists() and os.access(device, os.R_OK | os.W_OK)
    return accessible, accessible


def main() -> int:
    if sys.argv[1:2] == ["--exec-plan"]:
        try:
            plan = build_legacy_launch_plan(os.environ, sys.argv[2:])
        except ContractError as error:
            print(f"Legacy Boot Provider rejected LaunchPlan: {error}", file=sys.stderr)
            return 64
        from qemu_runtime import QemuRuntimeError, exec_launch_plan
        print(f"Legacy LaunchPlan SHA256: {plan.plan_hash}", file=sys.stderr, flush=True)
        try:
            exec_launch_plan(plan)
        except (ContractError, QemuRuntimeError) as error:
            print(f"Legacy QEMU runtime rejected LaunchPlan: {error}", file=sys.stderr)
            return 69
        return 0
    if sys.argv[1:] not in ([], ["--check-env"]):
        print(f"Usage: {sys.argv[0]} [--check-env | --exec-plan QEMU_ARG ...]", file=sys.stderr)
        return 2
    try:
        bind_legacy_environment(os.environ)
    except ContractError as error:
        print(f"Legacy Boot Provider rejected platform facts: {error}", file=sys.stderr)
        return 64
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
