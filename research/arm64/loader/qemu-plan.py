#!/usr/bin/env python3
"""Emit NUL-delimited QEMU arguments from the internal ARM64 provider plan."""
import argparse
from pathlib import Path
import platform
import sys


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src/platform"))

from boot_provider import ContractError, HostCapabilities, VMConfig  # noqa: E402
from linux_kexec_provider import (  # noqa: E402
    DSM_PROVIDER_ID,
    LinuxKexecProvider,
)
from profile_registry import research_profile  # noqa: E402
from qemu_runtime import QemuRuntimeError, exec_launch_plan  # noqa: E402
from scratch_disk import create_scratch_sata1  # noqa: E402


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
    parser.add_argument("--profile", choices=("research-arm64-linux-kexec",
                                                "research-arm64-dsm-kexec"),
                        default="research-arm64-linux-kexec")
    parser.add_argument("--kernel", required=True)
    parser.add_argument("--initrd", required=True)
    parser.add_argument("--cpu", choices=("cortex-a57", "cortex-a55", "max,lpa2=off"),
                        default="cortex-a57")
    parser.add_argument("--gic-version", type=int, choices=(2, 3), default=2)
    parser.add_argument("--memory-mib", type=int, choices=(512, 1024, 2048), default=512)
    parser.add_argument("--vcpus", type=int, choices=(1, 2, 4), default=1)
    parser.add_argument("--serial-route", choices=("pl011", "dsm-mmio16550"),
                        default="pl011")
    parser.add_argument("--its", choices=("on", "off"),
                        help="set the QEMU GICv3 ITS state; omit for QEMU default")
    parser.add_argument("--loader-disable-lpi", action="store_true",
                        help="keep GICv3 LPI initialization for the target kernel")
    parser.add_argument("--scratch-sata1-dir",
                        help="create a new private 2 GiB sparse disk for DSM SATA probing")
    parser.add_argument("--scratch-sata1-snapshot", action="store_true",
                        help="use a disposable QEMU copy-on-write overlay for the new DSM SATA scratch disk")
    parser.add_argument("--execute", action="store_true",
                        help="exec QEMU through the qemu-process runtime adapter")
    args = parser.parse_args()
    if Path(args.qemu).name != "qemu-system-aarch64":
        parser.error("--qemu must name qemu-system-aarch64")

    profile = research_profile(args.profile)
    if args.scratch_sata1_dir and (args.profile != "research-arm64-dsm-kexec"
                                   or not args.execute):
        parser.error("--scratch-sata1-dir requires the DS124 research profile and --execute")
    if args.scratch_sata1_snapshot and not args.scratch_sata1_dir:
        parser.error("--scratch-sata1-snapshot requires --scratch-sata1-dir")
    scratch_sata1 = None
    if args.scratch_sata1_dir:
        try:
            scratch_sata1 = str(create_scratch_sata1(args.scratch_sata1_dir, ROOT))
        except (OSError, ValueError) as error:
            parser.error(str(error))
    # Matches the known-good upstream Buildroot kexec runtime-test baseline.
    storage_ref = ("scratch-sata1-snapshot" if args.scratch_sata1_snapshot
                   else "scratch-sata1") if scratch_sata1 else "none"
    config = VMConfig(profile.id, "qemu-process", storage_ref, args.vcpus, args.memory_mib)
    process_arch = architecture()
    host = HostCapabilities(process_arch, process_arch, (Path(args.qemu).name,), False, False)
    try:
        provider_id = DSM_PROVIDER_ID if args.profile == "research-arm64-dsm-kexec" else None
        provider = LinuxKexecProvider() if provider_id is None else LinuxKexecProvider(provider_id)
        plan = provider.build_plan(
            profile, config, host, args.kernel, args.initrd, qemu_binary=args.qemu,
            cpu=args.cpu, gic_version=args.gic_version,
            its=None if args.its is None else args.its == "on",
            loader_disable_lpi=args.loader_disable_lpi, serial_route=args.serial_route,
            scratch_sata1=scratch_sata1,
            scratch_sata1_snapshot=args.scratch_sata1_snapshot)
    except ContractError as error:
        print(f"ARM64 QEMU plan rejected: {error}", file=sys.stderr)
        return 2

    sys.stderr.write(f"ARM64 LaunchPlan SHA256: {plan.plan_hash}\n")
    if args.execute:
        sys.stderr.flush()
        try:
            exec_launch_plan(plan)
        except (ContractError, QemuRuntimeError) as error:
            print(f"ARM64 QEMU runtime rejected LaunchPlan: {error}", file=sys.stderr)
            return 3
    sys.stdout.buffer.write(b"".join(arg.encode("utf-8") + b"\0" for arg in plan.qemu_argv[1:]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
