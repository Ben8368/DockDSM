#!/usr/bin/env python3
"""Emit NUL-delimited QEMU arguments for the ARM64 GRUB-to-kexec research chain."""
import argparse
from pathlib import Path
import platform
import sys


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src/platform"))

from arm64_grub_provider import Arm64GrubProvider  # noqa: E402
from boot_provider import ContractError, HostCapabilities, VMConfig  # noqa: E402
from profile_registry import research_profile  # noqa: E402
from qemu_runtime import QemuRuntimeError, exec_launch_plan  # noqa: E402


def architecture() -> str:
    machine = platform.machine().lower()
    if machine in ("aarch64", "arm64"):
        return "arm64"
    if machine in ("x86_64", "amd64"):
        return "amd64"
    raise ContractError(f"unsupported QEMU process architecture: {machine}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--qemu", default="qemu-system-aarch64")
    parser.add_argument("--disk", required=True, help="isolated GPT/EFI boot disk image")
    parser.add_argument("--firmware", required=True, help="AArch64 UEFI firmware image")
    parser.add_argument("--vcpus", type=int, choices=(1, 2, 4), default=1)
    parser.add_argument("--memory-mib", type=int, choices=(512, 1024, 2048), default=512)
    parser.add_argument("--execute", action="store_true",
                        help="exec QEMU through the qemu-process runtime adapter")
    args = parser.parse_args()
    if Path(args.qemu).name != "qemu-system-aarch64":
        parser.error("--qemu must name qemu-system-aarch64")

    profile = research_profile("research-arm64-grub-linux")
    config = VMConfig(profile.id, "qemu-process", "none", args.vcpus, args.memory_mib)
    process_arch = architecture()
    host = HostCapabilities(process_arch, process_arch,
                            (Path(args.qemu).name,), False, False)
    try:
        plan = Arm64GrubProvider().build_plan(
            profile, config, host, args.disk, args.firmware, qemu_binary=args.qemu)
    except ContractError as error:
        print(f"ARM64 GRUB QEMU plan rejected: {error}", file=sys.stderr)
        return 2

    sys.stderr.write(f"ARM64 GRUB LaunchPlan SHA256: {plan.plan_hash}\n")
    if args.execute:
        sys.stderr.flush()
        try:
            exec_launch_plan(plan)
        except (ContractError, QemuRuntimeError) as error:
            print(f"ARM64 GRUB runtime rejected LaunchPlan: {error}", file=sys.stderr)
            return 3
    sys.stdout.buffer.write(b"".join(arg.encode("utf-8") + b"\0"
                                           for arg in plan.qemu_argv[1:]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
