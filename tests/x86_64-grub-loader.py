#!/usr/bin/env python3
"""Contract and source checks for the isolated x86_64 GRUB ISO experiment."""
from pathlib import Path
import importlib.util
import json
import os
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src/platform"))

from boot_provider import ContractError, HostCapabilities, Profile, VMConfig  # noqa: E402
from x86_grub_provider import GrubIsoProvider  # noqa: E402

verifier_spec = importlib.util.spec_from_file_location(
    "x86_grub_boot_verifier", ROOT / "research/x86_64/grub-loader/verify-boot.py")
verifier = importlib.util.module_from_spec(verifier_spec)
verifier_spec.loader.exec_module(verifier)


base = ROOT / "research/x86_64/grub-loader"
config = (base / "configs/dockdsm_x86_64_grub_defconfig").read_text()
source_lock = json.loads((ROOT / "research/buildroot/source-lock.json").read_text())
build = (base / "build.sh").read_text()
runner = (base / "test.sh").read_text()
assert "BR2_x86_64=y" in config
assert "BR2_TARGET_GRUB2_I386_PC=y" in config
assert "BR2_TARGET_GRUB2_X86_64_EFI=y" in config
assert 'BR2_TARGET_GRUB2_BUILTIN_MODULES_EFI="boot configfile ' in config
assert "BR2_TARGET_GRUB2_BUILTIN_CONFIG_EFI=" in config
assert "BR2_TARGET_ROOTFS_ISO9660=y" in config
assert "BR2_TARGET_ROOTFS_ISO9660_INITRD=y" in config
assert "BR2_TARGET_ROOTFS_INITRAMFS=y" not in config
assert "BR2_ROOTFS_OVERLAY=" in config
assert "BR2_REPRODUCIBLE=y" in config
assert f'BR2_LINUX_KERNEL_CUSTOM_VERSION_VALUE="{source_lock["kernel"]["version"]}"' in config
assert "research/buildroot/check_inputs.py" in build
assert build.index("--check-output") < build.index("mkdir -p -- \"$output\"")
assert build.index("olddefconfig") < build.index('--config "$output/.config"')
assert build.index('--config "$output/.config"') < build.index(' dependencies')
assert "CONFIG_SERIAL_8250_CONSOLE=y" in build
assert "efi-part/EFI/BOOT/bootx64.efi" in build
assert "grub_config_fingerprint" in build and "grub2-reconfigure" in build
assert "requires an external initrd" in build
assert {"CONFIG_BLK_DEV_INITRD=y", "CONFIG_RD_GZIP=y"} <= set(
    (base / "board/x86_64-grub/linux.fragment").read_text().splitlines())
assert {"CONFIG_EFI=y", "CONFIG_EFI_STUB=y"} <= set(
    (base / "board/x86_64-grub/linux.fragment").read_text().splitlines())
assert "OUTPUT_DIR must be outside the repository" in build
assert 'downloads=${DOWNLOADS_DIR:-}' in build
assert 'DOWNLOADS_DIR must be separate from OUTPUT_DIR.' in build
assert 'output=$(python3 "$repo_root/research/buildroot/check_inputs.py"' in build
assert build.index('output=$(python3 "$repo_root/research/buildroot/check_inputs.py"') < build.index('case "$output/" in')
assert 'buildroot_epoch=$(sed -n' in build
assert 'SOURCE_DATE_EPOCH="$buildroot_epoch" make' in build
assert 'find "$iso_stage" -depth -exec touch -h -d "@$buildroot_epoch"' in build
assert '--modification-date="$iso_date" --set_all_file_dates "$iso_date"' in build
assert build.index('find "$iso_stage" -depth') < build.index('xorriso" -as mkisofs')
assert "qemu-plan.py" in runner and "--execute" in runner
assert "--uefi" in runner and "grub-boot${mode}.log" in runner
assert "read -r -d '' argument" not in runner
runtime = (ROOT / "src/platform/qemu_runtime.py").read_text()
assert "os.execvpe" in runtime and "shell=True" not in runtime
assert "qemu_runtime" in (base / "qemu-plan.py").read_text()
assert "eval " not in runner and "verify-boot.py" in runner
grub_config = (base / "board/x86_64-grub/grub.cfg").read_text()
assert "console=ttyS0,115200n8" in grub_config
assert "__KERNEL_PATH__" in grub_config and "__INITRD_PATH__" in grub_config
assert (base / "board/x86_64-grub/rootfs-overlay/init").stat().st_mode & 0o111
efi_config = (base / "board/x86_64-grub/grub-efi.cfg").read_text()
assert "set root=(cd0)" in efi_config and "configfile /boot/grub/grub.cfg" in efi_config

profile = Profile("research-x86_64-grub-linux", "open-linux", "amd64",
                  "x86_64-grub-iso", "q35", "amd64")
vm = VMConfig(profile.id, "qemu-process", "none", 2, 1024)
host = HostCapabilities("arm64", "arm64", ("qemu-system-x86_64",), False, False)
with tempfile.TemporaryDirectory(prefix="dockdsm-x86-grub-") as tmp:
    iso = Path(tmp) / "rootfs.iso9660"
    iso.write_bytes(b"synthetic-iso")
    firmware_code = Path(tmp) / "OVMF_CODE.fd"
    firmware_vars = Path(tmp) / "OVMF_VARS.fd"
    firmware_code.write_bytes(b"firmware-code")
    firmware_vars.write_bytes(b"firmware-vars-template")
    runner_output = Path(tmp) / "runner-output"
    runner_images = runner_output / "images"
    runner_images.mkdir(parents=True)
    runner_iso = runner_images / "rootfs.iso9660"
    runner_iso.write_bytes(b"synthetic-iso-for-runner")
    plan = GrubIsoProvider().build_plan(profile, vm, host, str(iso))
    assert plan.accelerator == "tcg"
    assert plan.host_arch == plan.container_arch == "arm64"
    assert plan.guest_arch == plan.bootloader_arch == "amd64"
    assert plan.storage_ref == "none"
    assert "-cdrom" in plan.qemu_argv and str(iso.resolve()) in plan.qemu_argv
    assert plan.qemu_argv[plan.qemu_argv.index("-boot") + 1] == "order=d"
    assert "-drive" not in plan.qemu_argv and "-append" not in plan.qemu_argv
    uefi_plan = GrubIsoProvider().build_plan(
        profile, vm, host, str(iso), firmware_code=str(firmware_code),
        firmware_vars=str(firmware_vars))
    drives = [uefi_plan.qemu_argv[i + 1] for i, arg in enumerate(uefi_plan.qemu_argv[:-1])
              if arg == "-drive"]
    assert len(drives) == 2
    assert drives[0] == f"if=pflash,format=raw,readonly=on,file={firmware_code.resolve()}"
    assert drives[1] == f"if=pflash,format=raw,file={firmware_vars.resolve()}"
    try:
        GrubIsoProvider().build_plan(profile, vm, host, str(iso),
                                     firmware_code=str(firmware_code))
    except ContractError:
        pass
    else:
        raise AssertionError("UEFI plan accepted a missing variables image")
    comma_firmware = Path(tmp) / "OVMF,inject.fd"
    comma_firmware.write_bytes(b"firmware")
    try:
        GrubIsoProvider().build_plan(profile, vm, host, str(iso),
                                     firmware_code=str(comma_firmware),
                                     firmware_vars=str(firmware_vars))
    except ContractError:
        pass
    else:
        raise AssertionError("UEFI plan accepted a QEMU drive-option separator in a path")

    cli = base / "qemu-plan.py"
    result = subprocess.run([sys.executable, str(cli), "--iso", str(iso)],
                            check=True, capture_output=True)
    assert tuple(item.decode() for item in result.stdout.split(b"\0")[:-1]) == plan.qemu_argv[1:]
    assert b"LaunchPlan SHA256:" in result.stderr
    efi_cli = subprocess.run(
        [sys.executable, str(cli), "--iso", str(iso), "--uefi", "--firmware-code",
         str(firmware_code), "--firmware-vars", str(firmware_vars)],
        check=True, capture_output=True)
    efi_args = tuple(item.decode() for item in efi_cli.stdout.split(b"\0")[:-1])
    assert efi_args[efi_args.index("-drive") + 1] == (
        f"if=pflash,format=raw,readonly=on,file={firmware_code.resolve()}")
    help_result = subprocess.run([sys.executable, str(cli), "--help"],
                                 check=True, capture_output=True, text=True)
    assert "writable disposable OVMF variable-store copy" in help_result.stdout
    assert "--firmware-code/--firmware-vars require --uefi" in subprocess.run(
        [sys.executable, str(cli), "--iso", str(iso), "--firmware-code", str(firmware_code)],
        capture_output=True, text=True).stderr
    unavailable_qemu = Path(tmp) / "missing" / "qemu-system-x86_64"
    unavailable = subprocess.run(
        [sys.executable, str(cli), "--execute", "--qemu", str(unavailable_qemu),
         "--iso", str(iso)], capture_output=True, text=True)
    assert unavailable.returncode == 3
    assert "cannot execute QEMU from LaunchPlan" in unavailable.stderr

    bad_profile = Profile("bad", "open-linux", "amd64", "x86_64-grub-iso", "virt", "amd64")
    bad_config = VMConfig("bad", "qemu-process", "none", 2, 1024)
    try:
        GrubIsoProvider().build_plan(bad_profile, bad_config, host, str(iso))
    except ContractError:
        pass
    else:
        raise AssertionError("provider accepted an architecture/machine mismatch")

    bad_platform = Profile("bad-platform", "virtualdsm", "amd64", "x86_64-grub-iso",
                           "q35", "amd64")
    bad_platform_config = VMConfig("bad-platform", "qemu-process", "none", 2, 1024)
    try:
        GrubIsoProvider().build_plan(bad_platform, bad_platform_config, host, str(iso))
    except ContractError:
        pass
    else:
        raise AssertionError("provider accepted a production DSM platform")

    disk_config = VMConfig(profile.id, "qemu-process", "production-data", 2, 1024)
    try:
        GrubIsoProvider().build_plan(profile, disk_config, host, str(iso))
    except ContractError:
        pass
    else:
        raise AssertionError("provider accepted a research plan with a data disk")

    fake_bin = Path(tmp) / "fake-bin"
    fake_bin.mkdir()
    fake_qemu = fake_bin / "qemu-system-x86_64"
    fake_qemu.write_text(
        "#!/usr/bin/env python3\n"
        "import os, sys\n"
        "args = sys.argv[1:]\n"
        "assert args.count('-machine') == 1\n"
        "assert os.path.realpath(args[args.index('-cdrom') + 1]) == os.path.realpath(os.environ['EXPECTED_ISO']), args\n"
        "assert args[args.index('-boot') + 1] == 'order=d'\n"
        "drives = [args[i + 1] for i, item in enumerate(args[:-1]) if item == '-drive']\n"
        "if os.environ.get('EXPECT_UEFI') and drives:\n"
        "    assert len(drives) == 2, args\n"
        "    assert drives[0] == 'if=pflash,format=raw,readonly=on,file=' + os.path.realpath(os.environ['EXPECTED_FIRMWARE_CODE']), args\n"
        "    assert drives[1].startswith('if=pflash,format=raw,file=') and os.path.isfile(drives[1].split('file=', 1)[1]), args\n"
        "else:\n"
        "    assert not drives, args\n"
        "assert '-append' not in args\n"
        "print('DOCKDSM_X86_GRUB_LINUX_BOOTED')\n"
        "print('reboot: Power down')\n"
        "if os.environ.get('FAKE_QEMU_DUPLICATE'):\n"
        "    print('DOCKDSM_X86_GRUB_LINUX_BOOTED')\n",
        encoding="utf-8")
    fake_timeout = fake_bin / "timeout-wrapper"
    fake_timeout.write_text(
        "#!/usr/bin/env python3\n"
        "import os, sys\n"
        "if sys.argv[1:4] != ['--signal=TERM', '--kill-after=5s', '120s']:\n"
        "    raise SystemExit(90)\n"
        "os.execvp(sys.argv[4], sys.argv[4:])\n",
        encoding="utf-8")
    fake_qemu.chmod(0o755)
    fake_timeout.chmod(0o755)
    runner_env = os.environ.copy()
    runner_env.update({"QEMU": str(fake_qemu), "TIMEOUT": str(fake_timeout),
                       "EXPECTED_ISO": str(runner_iso)})
    success = subprocess.run(["bash", str(base / "test.sh"), str(runner_output)],
                            env=runner_env, capture_output=True, text=True)
    assert success.returncode == 0, success.stdout + success.stderr
    assert "serial marker verified" in success.stdout
    runner_env.update({"EXPECTED_FIRMWARE_CODE": str(firmware_code.resolve())})
    uefi_success = subprocess.run(
        ["bash", str(base / "test.sh"), str(runner_output), "--uefi",
         str(firmware_code), str(firmware_vars)],
        env={**runner_env, "EXPECT_UEFI": "1"}, capture_output=True, text=True)
    assert uefi_success.returncode == 0, uefi_success.stdout + uefi_success.stderr
    assert "serial marker verified" in uefi_success.stdout
    assert uefi_success.stdout.count("LaunchPlan SHA256:") == 2
    runner_env["FAKE_QEMU_DUPLICATE"] = "1"
    duplicate = subprocess.run(["bash", str(base / "test.sh"), str(runner_output)],
                               env=runner_env, capture_output=True, text=True)
    assert duplicate.returncode != 0
    assert "exactly one standalone" in duplicate.stderr

valid_transcript = "SeaBIOS\r\n" + verifier.MARKER + "\r\nreboot: Power down\r\n"
verifier.verify(valid_transcript)
for invalid_transcript in (
    "SeaBIOS\n",
    "SeaBIOS\n" + verifier.MARKER + "\n",
    "SeaBIOS\nreboot: Power down\n" + verifier.MARKER + "\n",
    valid_transcript + verifier.MARKER + "\n",
    valid_transcript.replace(verifier.MARKER, "prefix " + verifier.MARKER),
    valid_transcript + "Kernel panic - not syncing: fixture\n",
    valid_transcript + "BUG: unable to handle page fault\n",
    valid_transcript + "Internal error: fixture\n",
):
    try:
        verifier.verify(invalid_transcript)
    except ValueError:
        pass
    else:
        raise AssertionError("invalid x86_64 boot transcript was accepted")

print("x86_64 GRUB provider contract passed (no ISO build or QEMU boot performed).")
