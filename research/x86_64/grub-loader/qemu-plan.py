#!/usr/bin/env python3
"""Emit NUL-delimited QEMU arguments from the internal x86_64 provider plan."""
import argparse
from pathlib import Path
import platform
import sys


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src/platform"))

from boot_provider import ContractError, HostCapabilities, VMConfig  # noqa: E402
from x86_grub_provider import GrubIsoProvider  # noqa: E402
from profile_registry import research_profile  # noqa: E402
from qemu_runtime import QemuRuntimeError, exec_launch_plan  # noqa: E402


def architecture() -> str:
    machine = platform.machine().lower()
    if machine in ("x86_64", "amd64"):
        return "amd64"
    if machine in ("aarch64", "arm64"):
        return "arm64"
    raise ContractError(f"unsupported QEMU process architecture: {machine}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--qemu", default="qemu-system-x86_64")
    parser.add_argument("--iso", required=True)
    parser.add_argument("--uefi", action="store_true",
                        help="boot with explicit OVMF code and variable-store images")
    parser.add_argument("--firmware-code")
    parser.add_argument("--firmware-vars",
                        help="writable disposable OVMF variable-store copy (QEMU modifies it; do not pass the shared template)")
    parser.add_argument("--execute", action="store_true",
                        help="exec QEMU through the qemu-process runtime adapter")
    args = parser.parse_args()
    if Path(args.qemu).name != "qemu-system-x86_64":
        parser.error("--qemu must name qemu-system-x86_64")
    if not args.uefi and (args.firmware_code is not None or args.firmware_vars is not None):
        parser.error("--firmware-code/--firmware-vars require --uefi")

    profile = research_profile("research-x86_64-grub-linux")
    config = VMConfig(profile.id, "qemu-process", "none", 2, 1024)
    process_arch = architecture()
    host = HostCapabilities(process_arch, process_arch,
                            (Path(args.qemu).name,), False, False)
    try:
        plan = GrubIsoProvider().build_plan(
            profile, config, host, args.iso, qemu_binary=args.qemu,
            firmware_code=args.firmware_code if args.uefi else None,
            firmware_vars=args.firmware_vars if args.uefi else None)
    except ContractError as error:
        print(f"x86_64 QEMU plan rejected: {error}", file=sys.stderr)
        return 2

    sys.stderr.write(f"x86_64 LaunchPlan SHA256: {plan.plan_hash}\n")
    if args.execute:
        sys.stderr.flush()
        try:
            exec_launch_plan(plan)
        except (ContractError, QemuRuntimeError) as error:
            print(f"x86_64 QEMU runtime rejected LaunchPlan: {error}", file=sys.stderr)
            return 3
    sys.stdout.buffer.write(b"".join(arg.encode("utf-8") + b"\0"
                                          for arg in plan.qemu_argv[1:]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
