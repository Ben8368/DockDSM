#!/usr/bin/env python3
"""Synthetic contract checks for the ARM64 UEFI GRUB research provider."""
from pathlib import Path
import importlib.util
import os
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src/platform"))
from arm64_grub_provider import Arm64GrubProvider  # noqa: E402
from boot_provider import ContractError, HostCapabilities, Profile, VMConfig  # noqa: E402
from profile_registry import research_profile  # noqa: E402


VERIFY_PATH = ROOT / "research/arm64/grub-loader/verify-grub.py"
VERIFY_SPEC = importlib.util.spec_from_file_location("arm64_grub_verify", VERIFY_PATH)
assert VERIFY_SPEC and VERIFY_SPEC.loader
verify_module = importlib.util.module_from_spec(VERIFY_SPEC)
VERIFY_SPEC.loader.exec_module(verify_module)

profile = research_profile("research-arm64-grub-linux")
host = HostCapabilities("arm64", "arm64", ("qemu-system-aarch64",), False, False)
provider = Arm64GrubProvider()


def rejects(callback, expected=None):
    try:
        callback()
    except ContractError as error:
        if expected is not None:
            assert expected in str(error), str(error)
    else:
        raise AssertionError("expected ContractError")


with tempfile.TemporaryDirectory(prefix="dockdsm-arm64-grub-") as temp:
    root = Path(temp)
    disk = root / "dockdsm-arm64-grub.img"
    firmware = root / "QEMU_EFI.fd"
    disk.write_bytes(b"synthetic-gpt-efi-image")
    firmware.write_bytes(b"synthetic-aarch64-uefi-firmware")
    config = VMConfig(profile.id, "qemu-process", "none", 1, 512)
    plan = provider.build_plan(profile, config, host, str(disk), str(firmware))
    assert plan.accelerator == "tcg"
    assert plan.host_arch == plan.container_arch == "arm64"
    assert plan.guest_arch == plan.bootloader_arch == "arm64"
    assert plan.storage_ref == "none"
    assert plan.qemu_argv[0] == "qemu-system-aarch64"
    assert plan.qemu_argv[plan.qemu_argv.index("-machine") + 1] == "virt,accel=tcg"
    assert plan.qemu_argv[plan.qemu_argv.index("-bios") + 1] == str(firmware.resolve())
    drive = plan.qemu_argv[plan.qemu_argv.index("-drive") + 1]
    assert drive == f"file={disk.resolve()},format=raw,if=none,id=boot,readonly=on"
    assert "virtio-blk-device,drive=boot" in plan.qemu_argv
    assert "-nic" in plan.qemu_argv and plan.qemu_argv[plan.qemu_argv.index("-nic") + 1] == "none"
    assert all(option not in plan.qemu_argv for option in ("-kernel", "-initrd", "-append"))

    wrong_profile = Profile("wrong", "rtd1619b", "arm64", "arm64-grub-efi", "virt", "arm64")
    rejects(lambda: provider.build_plan(wrong_profile, config, host, str(disk), str(firmware)),
            "profile/provider mismatch")
    rejects(lambda: provider.build_plan(profile, VMConfig(profile.id, "docker", "none", 1, 512),
                                        host, str(disk), str(firmware)), "qemu-process")
    rejects(lambda: provider.build_plan(profile, VMConfig(profile.id, "qemu-process", "data", 1, 512),
                                        host, str(disk), str(firmware)), "read-only boot media")
    rejects(lambda: provider.build_plan(profile, config,
                                        HostCapabilities("arm64", "arm64", (), False, False),
                                        str(disk), str(firmware)), "not available")
    rejects(lambda: provider.build_plan(profile, config, host, str(disk), str(root / "missing.fd")),
            "cannot be read")
    comma_disk = root / "disk,unsafe.img"
    comma_disk.write_bytes(b"disk")
    rejects(lambda: provider.build_plan(profile, config, host, str(comma_disk), str(firmware)),
            "drive-option separators")

    cli = ROOT / "research/arm64/grub-loader/qemu-plan.py"
    cli_result = subprocess.run(
        [sys.executable, str(cli), "--disk", str(disk), "--firmware", str(firmware)],
        check=True, capture_output=True)
    cli_args = tuple(value.decode() for value in cli_result.stdout.split(b"\0")[:-1])
    assert cli_args == plan.qemu_argv[1:]
    assert b"ARM64 GRUB LaunchPlan SHA256:" in cli_result.stderr

    fake_bin = root / "bin"
    fake_bin.mkdir()
    fake_qemu = fake_bin / "qemu-system-aarch64"
    fake_qemu.write_text(
        "#!/usr/bin/env python3\n"
        "import os, sys\n"
        "args = sys.argv[1:]\n"
        "assert args[args.index('-bios') + 1] == os.environ['EXPECTED_FIRMWARE'], args\n"
        "drive = args[args.index('-drive') + 1]\n"
        "assert drive == 'file=' + os.environ['EXPECTED_DISK'] + ',format=raw,if=none,id=boot,readonly=on', args\n"
        "assert args[args.index('-device') + 1] == 'virtio-blk-device,drive=boot', args\n"
        "print('DOCKDSM_ARM64_GRUB_ENTRY')\n"
        "print('DOCKDSM_KEXEC_LOADER_READY')\n"
        "print('DOCKDSM_KEXEC_IMAGE_LOADED')\n"
        "print('DOCKDSM_KEXEC_TARGET_BOOTED')\n"
        "print('reboot: Power down')\n",
        encoding="utf-8")
    fake_timeout = fake_bin / "timeout-wrapper"
    fake_timeout.write_text(
        "#!/usr/bin/env python3\n"
        "import os, sys\n"
        "assert sys.argv[1:4] == ['--signal=TERM', '--kill-after=5s', '180s'], sys.argv\n"
        "os.execvp(sys.argv[4], sys.argv[4:])\n",
        encoding="utf-8")
    fake_qemu.chmod(0o755)
    fake_timeout.chmod(0o755)
    build_output = root / "build"
    images = build_output / "images"
    images.mkdir(parents=True)
    runner_disk = images / "dockdsm-arm64-grub.img"
    runner_disk.write_bytes(b"synthetic-gpt-efi-image")
    runner_firmware = root / "runner-QEMU_EFI.fd"
    runner_firmware.write_bytes(b"synthetic-aarch64-uefi-firmware")
    runner = subprocess.run(
        ["bash", str(ROOT / "research/arm64/grub-loader/test.sh"),
         str(build_output), str(runner_firmware), "--qemu", str(fake_qemu)],
        env={**os.environ, "TIMEOUT": str(fake_timeout),
             "EXPECTED_FIRMWARE": str(runner_firmware.resolve()),
             "EXPECTED_DISK": str(runner_disk.resolve())},
        capture_output=True, text=True)
    assert runner.returncode == 0, runner.stdout + runner.stderr
    assert "UEFI -> GRUB -> Linux loader -> kexec handoff markers verified" in runner.stdout

    transcript = ("DOCKDSM_ARM64_GRUB_ENTRY\n" +
                  "DOCKDSM_KEXEC_LOADER_READY\nDOCKDSM_KEXEC_IMAGE_LOADED\n" +
                  "DOCKDSM_KEXEC_TARGET_BOOTED\nreboot: Power down\n")
    verify_module.verify_grub(transcript)
    try:
        verify_module.verify_grub("DOCKDSM_KEXEC_LOADER_READY\n" + transcript)
    except ValueError:
        pass
    else:
        raise AssertionError("verifier accepted a GRUB marker after the loader marker")

defconfig = (ROOT / "research/arm64/loader/configs/dockdsm_arm64_grub_defconfig").read_text()
for required in (
        "BR2_TARGET_GRUB2_ARM64_EFI=y",
        "BR2_TARGET_GRUB2_BUILTIN_MODULES_EFI=\"boot configfile echo fat linux normal part_gpt serial terminal\"",
        "BR2_PACKAGE_HOST_GENIMAGE=y",
        "BR2_PACKAGE_HOST_DOSFSTOOLS=y",
        "BR2_PACKAGE_HOST_MTOOLS=y",
        "BR2_LINUX_KERNEL_CUSTOM_VERSION_VALUE=\"6.12.112\"",
):
    assert required in defconfig, required
grub_cfg = (ROOT / "research/arm64/loader/board/arm64-kexec/grub.cfg").read_text()
assert "DOCKDSM_ARM64_GRUB_ENTRY" in grub_cfg
assert "serial --port=mmio,0x09000000.l --speed=115200" in grub_cfg
assert "terminal_output serial" in grub_cfg
assert "(hd0,gpt1)/Image" in grub_cfg
assert "(hd0,gpt1)/dockdsm-loader.cpio.gz" in grub_cfg

print("ARM64 UEFI GRUB provider, config, runner and transcript contracts passed.")
