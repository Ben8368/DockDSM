#!/usr/bin/env python3
"""Host-only tests for deterministic newc initramfs and handoff evidence."""
import gzip
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import stat
import tempfile


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src/platform"))

from boot_provider import HostCapabilities, Profile, VMConfig  # noqa: E402
from linux_kexec_provider import LinuxKexecProvider  # noqa: E402


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


packer = load_module("arm64_loader_initramfs", ROOT / "research/arm64/loader/board/arm64-kexec/make-initramfs.py")
verifier = load_module("arm64_loader_handoff", ROOT / "research/arm64/loader/verify-handoff.py")
kernel_fragment = (ROOT / "research/arm64/loader/board/arm64-kexec/linux-kexec.fragment").read_text()
build_script = (ROOT / "research/arm64/loader/build.sh").read_text()
fetch_script = (ROOT / "research/arm64/loader/fetch-buildroot.sh").read_text()
qemu_test_script = (ROOT / "research/arm64/loader/test.sh").read_text()
loader_init = (ROOT / "research/arm64/loader/board/arm64-kexec/rootfs-overlay/init").read_text()
required_kernel_options = {
    "CONFIG_KEXEC=y",
    "CONFIG_KEXEC_FILE=y",
    "CONFIG_PROC_KCORE=y",
    "CONFIG_RANDOMIZE_BASE=y",
    "CONFIG_ARM64_VA_BITS_48=y",
    "CONFIG_BLK_DEV_INITRD=y",
    "CONFIG_RD_GZIP=y",
    "CONFIG_DEVTMPFS=y",
    "CONFIG_DEVTMPFS_MOUNT=y",
    "CONFIG_SERIAL_AMBA_PL011=y",
    "CONFIG_SERIAL_AMBA_PL011_CONSOLE=y",
}
assert required_kernel_options <= set(kernel_fragment.splitlines())
assert all(option in build_script for option in required_kernel_options)
source_lock = json.loads((ROOT / "research/buildroot/source-lock.json").read_text())
defconfig = (ROOT / "research/arm64/loader/configs/dockdsm_arm64_kexec_defconfig").read_text()
assert f'BR2_LINUX_KERNEL_CUSTOM_VERSION_VALUE="{source_lock["kernel"]["version"]}"' in defconfig
assert len(source_lock["kernel"]["sha256"]) == 64
assert all(char in "0123456789abcdef" for char in source_lock["kernel"]["sha256"])
assert source_lock["version"] in source_lock["kernel"]["sha256_source"]
assert "source-lock.json" in fetch_script
assert "../../buildroot/source-lock.json" in fetch_script
assert "research/buildroot/check_inputs.py" in build_script
assert 'downloads=${DOWNLOADS_DIR:-}' in build_script
assert 'if [[ -n "$downloads" ]]; then' in build_script
assert '--check-output "$downloads" --repo-root "$repo_root"' in build_script
assert 'DOWNLOADS_DIR must be separate from OUTPUT_DIR.' in build_script
assert build_script.index('--check-output "$downloads"') < build_script.index('mkdir -p -- "$output"')
assert 'downloads="$output/downloads"' in build_script
assert build_script.index("make-initramfs.py") > build_script.index('make -C "$buildroot" O="$output" BR2_EXTERNAL="$external" BR2_DL_DIR="$downloads" -j"$jobs"')
assert build_script.index("--check-output") < build_script.index("mkdir -p -- \"$output\"")
assert build_script.index("olddefconfig") < build_script.index('--config "$output/.config"')
assert build_script.index('--config "$output/.config"') < build_script.index(' dependencies')
assert "expected_version=2025.02.19" not in fetch_script
assert "qemu-plan.py" in qemu_test_script and "--execute" in qemu_test_script
assert "read -r -d '' argument" not in qemu_test_script
runtime = (ROOT / "src/platform/qemu_runtime.py").read_text()
assert "os.execvpe" in runtime and "shell=True" not in runtime
assert "qemu_runtime" in (ROOT / "research/arm64/loader/qemu-plan.py").read_text()
assert "mapfile" not in qemu_test_script
assert "virt,accel=tcg" not in qemu_test_script
argument_reader = (
    'args=(); while IFS= read -r -d "" argument; do '
    'args+=("$argument"); done; printf "%s\\n" "${args[@]}"'
)
parsed_arguments = subprocess.run(
    ["/bin/bash", "-c", argument_reader],
    input=b"--machine\0virt,accel=tcg\0-append\0console=ttyAMA0\0",
    check=True, capture_output=True).stdout.decode().splitlines()
assert parsed_arguments == ["--machine", "virt,accel=tcg", "-append", "console=ttyAMA0"]
assert loader_init.index("if ! kexec -c -d -l") < loader_init.index("DOCKDSM_KEXEC_LOADER_ERROR_LOAD_FAILED")
assert "kexec -c -d -l /boot/Image --mem-min=0x42000000" in loader_init
assert "rdinit=/init loglevel=7 nokaslr reset_devices nr_cpus=1" in loader_init
assert loader_init.index("DOCKDSM_KEXEC_LOADER_ERROR_LOAD_FAILED") < loader_init.index("DOCKDSM_KEXEC_IMAGE_LOADED")


def read_newc(payload):
    entries = {}
    offset = 0
    while True:
        if payload[offset:offset + 6] != b"070701":
            raise AssertionError("invalid newc magic")
        fields = [int(payload[offset + 6 + index * 8:offset + 14 + index * 8], 16)
                  for index in range(13)]
        mode, size, rdevmajor, rdevminor, namesize = fields[1], fields[6], fields[9], fields[10], fields[11]
        offset += 110
        name = payload[offset:offset + namesize - 1].decode()
        offset = (offset + namesize + 3) & ~3
        data = payload[offset:offset + size]
        offset = (offset + size + 3) & ~3
        if name == "TRAILER!!!":
            break
        entries[name] = (mode, data, rdevmajor, rdevminor)
    if offset != len(payload):
        raise AssertionError("trailing bytes after newc trailer")
    return entries


with tempfile.TemporaryDirectory(prefix="dockdsm-arm64-loader-") as tmp:
    root = Path(tmp) / "root"
    (root / "bin").mkdir(parents=True)
    (root / "bin/busybox").write_bytes(b"busybox-fixture")
    (root / "init").write_text("old-init\n")
    (root / "sh").symlink_to("bin/busybox")
    kernel = Path(tmp) / "Image"
    kernel.write_bytes(b"open-linux-kernel-fixture")
    replacement = Path(tmp) / "target-init"
    replacement.write_text("#!/bin/sh\necho DOCKDSM_KEXEC_TARGET_BOOTED\n")
    extra = Path(tmp) / "target.cpio.gz"
    extra.write_bytes(b"target-initramfs-fixture")
    loader_profile = Profile(
        "research-arm64-linux-kexec", "open-linux", "arm64",
        "arm64-linux-kexec", "virt", "arm64")
    loader_config = VMConfig(loader_profile.id, "qemu-process", "none", 1, 512)
    # Synthetic host capabilities exercise the plan; they do not claim QEMU is installed.
    loader_host = HostCapabilities("arm64", "arm64", ("qemu-system-aarch64",), False, False)
    plan = LinuxKexecProvider().build_plan(
        loader_profile, loader_config, loader_host, str(kernel), str(extra))
    assert plan.accelerator == "tcg"
    assert plan.bootloader_arch == plan.guest_arch == "arm64"
    assert plan.qemu_argv[1:3] == ("-machine", "virt,accel=tcg,gic-version=2,dtb-kaslr-seed=off")
    assert plan.qemu_argv[3:5] == ("-cpu", "cortex-a57")
    assert plan.qemu_argv[11:15] == ("-kernel", str(kernel.resolve()), "-initrd", str(extra.resolve()))
    assert plan.qemu_argv[-3:] == ("-monitor", "none", "-no-reboot")
    path_qemu_plan = LinuxKexecProvider().build_plan(
        loader_profile, loader_config, loader_host, str(kernel), str(extra),
        qemu_binary="/usr/bin/qemu-system-aarch64")
    assert path_qemu_plan.qemu_argv[0] == "/usr/bin/qemu-system-aarch64"
    armv3_no_its_plan = LinuxKexecProvider().build_plan(
        loader_profile, loader_config, loader_host, str(kernel), str(extra),
        cpu="cortex-a55", gic_version=3, its=False)
    assert armv3_no_its_plan.qemu_argv[1:5] == (
        "-machine", "virt,accel=tcg,gic-version=3,dtb-kaslr-seed=off,its=off",
        "-cpu", "cortex-a55")
    armv3_default_its_plan = LinuxKexecProvider().build_plan(
        loader_profile, loader_config, loader_host, str(kernel), str(extra),
        cpu="cortex-a55", gic_version=3)
    assert armv3_default_its_plan.qemu_argv[2] == "virt,accel=tcg,gic-version=3,dtb-kaslr-seed=off"
    lpi_suppressed_plan = LinuxKexecProvider().build_plan(
        loader_profile, VMConfig(loader_profile.id, "qemu-process", "none", 1, 1024),
        loader_host, str(kernel), str(extra), cpu="cortex-a55", gic_version=3,
        its=True, loader_disable_lpi=True)
    assert lpi_suppressed_plan.qemu_argv[7:9] == ("-m", "1024")
    assert lpi_suppressed_plan.qemu_argv[lpi_suppressed_plan.qemu_argv.index("-append") + 1] == (
        "console=ttyAMA0,115200 earlycon=pl011,0x09000000 rdinit=/init loglevel=7 nokaslr "
        "irqchip.gicv3_nolpi=1")
    for options in (("gic_version", 4), ("gic_version", 2, "its", False),
                    ("cpu", "host"), ("its", "off"), ("its", 0),
                    ("gic_version", 2, "loader_disable_lpi", True),
                    ("gic_version", 3, "its", False, "loader_disable_lpi", True)):
        kwargs = dict(zip(options[::2], options[1::2]))
        try:
            LinuxKexecProvider().build_plan(
                loader_profile, loader_config, loader_host, str(kernel), str(extra), **kwargs)
        except Exception as error:
            assert error.__class__.__name__ == "ContractError", error
        else:
            raise AssertionError(f"invalid QEMU research option was accepted: {kwargs}")

    cli = ROOT / "research/arm64/loader/qemu-plan.py"
    result = subprocess.run(
        [sys.executable, str(cli), "--kernel", str(kernel), "--initrd", str(extra)],
        check=True, capture_output=True)
    cli_args = tuple(part.decode() for part in result.stdout.split(b"\0")[:-1])
    assert cli_args == plan.qemu_argv[1:]
    assert b"LaunchPlan SHA256:" in result.stderr
    variant_cli = subprocess.run(
        [sys.executable, str(cli), "--kernel", str(kernel), "--initrd", str(extra),
         "--cpu", "cortex-a55", "--gic-version", "3", "--its", "off"],
        check=True, capture_output=True)
    variant_cli_args = tuple(part.decode() for part in variant_cli.stdout.split(b"\0")[:-1])
    assert variant_cli_args == armv3_no_its_plan.qemu_argv[1:]
    lpi_cli = subprocess.run(
        [sys.executable, str(cli), "--kernel", str(kernel), "--initrd", str(extra),
         "--cpu", "cortex-a55", "--gic-version", "3", "--its", "on",
         "--memory-mib", "1024", "--loader-disable-lpi"],
        check=True, capture_output=True)
    lpi_cli_args = tuple(part.decode() for part in lpi_cli.stdout.split(b"\0")[:-1])
    assert lpi_cli_args == lpi_suppressed_plan.qemu_argv[1:]
    invalid_cli = subprocess.run(
        [sys.executable, str(cli), "--kernel", str(kernel), "--initrd", str(extra),
         "--gic-version", "2", "--its", "off"], capture_output=True, text=True)
    assert invalid_cli.returncode == 2 and "valid only with GICv3" in invalid_cli.stderr
    invalid_lpi_cli = subprocess.run(
        [sys.executable, str(cli), "--kernel", str(kernel), "--initrd", str(extra),
         "--gic-version", "2", "--loader-disable-lpi"], capture_output=True, text=True)
    assert invalid_lpi_cli.returncode == 2 and "requires GICv3" in invalid_lpi_cli.stderr
    path_cli = subprocess.run(
        [sys.executable, str(cli), "--qemu", "/usr/bin/qemu-system-aarch64",
         "--kernel", str(kernel), "--initrd", str(extra)],
        check=True, capture_output=True)
    path_cli_args = tuple(part.decode() for part in path_cli.stdout.split(b"\0")[:-1])
    assert path_cli_args == path_qemu_plan.qemu_argv[1:]
    unavailable_qemu = Path(tmp) / "missing" / "qemu-system-aarch64"
    unavailable = subprocess.run(
        [sys.executable, str(cli), "--execute", "--qemu", str(unavailable_qemu),
         "--kernel", str(kernel), "--initrd", str(extra)],
        capture_output=True, text=True)
    assert unavailable.returncode == 3
    assert "cannot execute QEMU from LaunchPlan" in unavailable.stderr

    # Exercise the runner boundary with a fake QEMU process. This verifies argv
    # transport and transcript gating without claiming a Linux boot occurred.
    runner_output = Path(tmp) / "runner-output"
    runner_images = runner_output / "images"
    runner_images.mkdir(parents=True)
    for artifact in ("Image", "dockdsm-loader.cpio.gz", "dockdsm-target.cpio.gz"):
        (runner_images / artifact).write_bytes((artifact + " fixture").encode())
    fake_bin = Path(tmp) / "fake-bin"
    fake_bin.mkdir()
    fake_qemu = fake_bin / "qemu-system-aarch64"
    fake_qemu.write_text(
        "#!/usr/bin/env python3\n"
        "import os, sys\n"
        "args = sys.argv[1:]\n"
        "assert args.count('-machine') == 1, args\n"
        "assert args[args.index('-machine') + 1] == os.environ['EXPECTED_MACHINE'], args\n"
        "assert args[args.index('-cpu') + 1] == os.environ['EXPECTED_CPU'], args\n"
        "assert os.path.realpath(args[args.index('-kernel') + 1]) == os.path.realpath(os.environ['EXPECTED_KERNEL']), args\n"
        "assert os.path.realpath(args[args.index('-initrd') + 1]) == os.path.realpath(os.environ['EXPECTED_INITRD']), args\n"
        "assert args[args.index('-append') + 1] == os.environ['EXPECTED_APPEND'], args\n"
        "assert '-nic' in args and args[args.index('-nic') + 1] == 'none', args\n"
        "assert '-no-reboot' in args and '-monitor' in args and args[args.index('-monitor') + 1] == 'none', args\n"
        "from pathlib import Path\n"
        "markers = Path(os.environ['EXPECTED_MARKERS']).read_text().splitlines()\n"
        "print('\\n'.join(markers))\n"
        "if os.environ.get('FAKE_QEMU_BAD_TRANSCRIPT'):\n"
        "    print('DOCKDSM_KEXEC_LOADER_ERROR_LOAD_FAILED')\n"
        "if os.environ.get('FAKE_QEMU_EXIT'):\n"
        "    raise SystemExit(int(os.environ['FAKE_QEMU_EXIT']))\n",
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
    expected_markers = Path(tmp) / "expected-markers.txt"
    expected_markers.write_text("\n".join(verifier.MARKERS) + "\n")
    runner_env = os.environ.copy()
    runner_env.update({
        "QEMU": str(fake_qemu),
        "TIMEOUT": str(fake_timeout),
        "EXPECTED_KERNEL": str(runner_images / "Image"),
        "EXPECTED_INITRD": str(runner_images / "dockdsm-loader.cpio.gz"),
        "EXPECTED_MARKERS": str(expected_markers),
        "EXPECTED_MACHINE": "virt,accel=tcg,gic-version=2,dtb-kaslr-seed=off",
        "EXPECTED_CPU": "cortex-a57",
        "EXPECTED_APPEND": "console=ttyAMA0,115200 earlycon=pl011,0x09000000 rdinit=/init loglevel=7 nokaslr",
    })
    success = subprocess.run(
        ["bash", str(ROOT / "research/arm64/loader/test.sh"), str(runner_output)],
        env=runner_env, capture_output=True, text=True)
    assert success.returncode == 0, success.stdout + success.stderr
    assert "Loader -> Linux kernel kexec handoff markers verified" in success.stdout
    runner_env["EXPECTED_MACHINE"] = "virt,accel=tcg,gic-version=3,dtb-kaslr-seed=off,its=off"
    runner_env["EXPECTED_CPU"] = "cortex-a55"
    variant_success = subprocess.run(
        ["bash", str(ROOT / "research/arm64/loader/test.sh"), str(runner_output),
         "--cpu", "cortex-a55", "--gic-version", "3", "--its", "off"],
        env=runner_env, capture_output=True, text=True)
    assert variant_success.returncode == 0, variant_success.stdout + variant_success.stderr
    assert "cortex-a55-gicv3-its-off-mem-512-loader-nolpi-0.log" in variant_success.stdout
    runner_env["EXPECTED_MACHINE"] = "virt,accel=tcg,gic-version=3,dtb-kaslr-seed=off,its=on"
    runner_env["EXPECTED_CPU"] = "cortex-a55"
    runner_env["EXPECTED_APPEND"] += " irqchip.gicv3_nolpi=1"
    lpi_success = subprocess.run(
        ["bash", str(ROOT / "research/arm64/loader/test.sh"), str(runner_output),
         "--cpu", "cortex-a55", "--gic-version", "3", "--memory-mib", "1024",
         "--its", "on", "--loader-disable-lpi"],
        env=runner_env, capture_output=True, text=True)
    assert lpi_success.returncode == 0, lpi_success.stdout + lpi_success.stderr
    assert "cortex-a55-gicv3-its-on-mem-1024-loader-nolpi-1.log" in lpi_success.stdout
    runner_env["EXPECTED_APPEND"] = "console=ttyAMA0,115200 earlycon=pl011,0x09000000 rdinit=/init loglevel=7 nokaslr"
    runner_env["EXPECTED_MACHINE"] = "virt,accel=tcg,gic-version=2,dtb-kaslr-seed=off"
    runner_env["EXPECTED_CPU"] = "cortex-a57"
    runner_env["FAKE_QEMU_BAD_TRANSCRIPT"] = "1"
    failure = subprocess.run(
        ["bash", str(ROOT / "research/arm64/loader/test.sh"), str(runner_output)],
        env=runner_env, capture_output=True, text=True)
    assert failure.returncode != 0
    assert "failure signature in serial log" in failure.stderr
    runner_env.pop("FAKE_QEMU_BAD_TRANSCRIPT")
    runner_env["FAKE_QEMU_EXIT"] = "7"
    qemu_failure = subprocess.run(
        ["bash", str(ROOT / "research/arm64/loader/test.sh"), str(runner_output)],
        env=runner_env, capture_output=True, text=True)
    assert qemu_failure.returncode == 7, qemu_failure.stdout + qemu_failure.stderr
    assert "QEMU exited with status 7" in qemu_failure.stderr

    archive = Path(tmp) / "initramfs.cpio.gz"
    packer.build(root, archive,
                 overrides=(("init", (replacement.read_bytes(), 0o755)),),
                 extras=(("boot/Image", kernel), ("boot/target.cpio.gz", extra)))
    first = archive.read_bytes()
    packer.build(root, archive,
                 overrides=(("init", (replacement.read_bytes(), 0o755)),),
                 extras=(("boot/Image", kernel), ("boot/target.cpio.gz", extra)))
    assert archive.read_bytes() == first, "initramfs archive must be byte reproducible"
    records = read_newc(gzip.decompress(first))
    assert records["init"][1] == replacement.read_bytes()
    assert stat.S_ISREG(records["init"][0]) and records["init"][0] & 0o111
    assert records["sh"][1] == b"bin/busybox" and stat.S_ISLNK(records["sh"][0])
    assert records["boot/Image"][1] == kernel.read_bytes()
    assert records["boot/target.cpio.gz"][1] == extra.read_bytes()
    assert stat.S_ISCHR(records["dev/console"][0])
    assert records["dev/console"][2:] == (5, 1)
    assert stat.S_ISCHR(records["dev/null"][0])
    assert records["dev/null"][2:] == (1, 3)

transcript = "\n".join(verifier.MARKERS)
verifier.verify(transcript)
for invalid in (
    "\n".join(reversed(verifier.MARKERS)),
    "\n".join(f"kernel: {marker}" for marker in verifier.MARKERS),
    transcript + "\n" + verifier.MARKERS[-1],
    transcript + "\nDOCKDSM_KEXEC_LOADER_ERROR_LOAD_FAILED",
    transcript + "\nDOCKDSM_KEXEC_EXEC_RETURNED",
    transcript + "\nKernel panic - not syncing:",
    transcript + "\nUnable to handle kernel paging request",
    transcript + "\nInternal error: synchronous external abort",
    transcript + "\nSError Interrupt on CPU0",
):
    try:
        verifier.verify(invalid)
    except ValueError:
        pass
    else:
        raise AssertionError("invalid handoff transcript was accepted")
for failure in verifier.FAILURES:
    try:
        verifier.verify(transcript + "\n" + failure)
    except ValueError:
        pass
    else:
        raise AssertionError(f"failure signature was accepted: {failure}")

print("ARM64 loader archive and handoff verifier tests passed (no QEMU boot performed).")
