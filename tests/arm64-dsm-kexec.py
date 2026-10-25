#!/usr/bin/env python3
"""Synthetic contracts for the private, diskless DS124 kexec research harness."""
import gzip
import importlib.util
import lzma
from pathlib import Path
import os
import stat
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src/platform"))
sys.path.insert(0, str(ROOT / "research/arm64/loader"))

from boot_provider import ContractError, HostCapabilities, VMConfig  # noqa: E402
from linux_kexec_provider import DSM_PROVIDER_ID, LinuxKexecProvider  # noqa: E402
from profile_registry import legacy_profile_ids, research_profile  # noqa: E402
from scratch_disk import create_scratch_sata1, verify_scratch_sata1  # noqa: E402


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


prepare = load_module("prepare_dsm_kexec", ROOT / "research/arm64/loader/prepare-dsm-kexec.py")
verifier = load_module("verify_dsm_handoff", ROOT / "research/arm64/loader/verify-dsm-handoff.py")
initrd_sata_verifier = load_module(
    "verify_dsm_initrd_sata", ROOT / "research/arm64/loader/verify-dsm-initrd-sata.py")
dsm_loader_init = (ROOT / "research/arm64/loader/board/arm64-kexec/dsm-loader-init").read_text()
assert "kexec -c -d -l /boot/DSM_DS124_72806.Image --mem-min=0x42000000" in dsm_loader_init


def newc(files):
    payload = bytearray()
    entries = list(files.items()) + [("TRAILER!!!", b"")]
    for ino, (name, data) in enumerate(entries, start=1):
        encoded_name = name.encode() + b"\0"
        values = (ino, stat.S_IFREG | 0o644, 0, 0, 1, 0, len(data), 0, 0,
                  0, 0, len(encoded_name), 0)
        header = b"070701" + b"".join(f"{value:08x}".encode() for value in values)
        payload.extend(header)
        payload.extend(encoded_name)
        payload.extend(bytes((-len(payload)) % 4))
        payload.extend(data)
        payload.extend(bytes((-len(payload)) % 4))
    return bytes(payload)


def read_newc(payload):
    entries = {}
    offset = 0
    while True:
        assert payload[offset:offset + 6] == b"070701"
        fields = [int(payload[offset + 6 + i * 8:offset + 14 + i * 8], 16)
                  for i in range(13)]
        mode, size, namesize = fields[1], fields[6], fields[11]
        offset += 110
        name = payload[offset:offset + namesize - 1].decode()
        offset = (offset + namesize + 3) & ~3
        data = payload[offset:offset + size]
        offset = (offset + size + 3) & ~3
        if name == "TRAILER!!!":
            break
        entries[name] = (mode, data)
    assert offset == len(payload)
    return entries


def cli(*args, **kwargs):
    return subprocess.run([sys.executable, *map(str, args)], capture_output=True,
                          text=True, **kwargs)


with tempfile.TemporaryDirectory(prefix="dockdsm-dsm-kexec-") as temporary:
    tmp = Path(temporary)
    target = tmp / "buildroot-target"
    target.mkdir()
    (target / "init").write_text("#!/bin/sh\n")
    (target / "bin").mkdir()
    (target / "bin/busybox").write_bytes(b"busybox")

    kernel = bytearray(b"K" * 96)
    kernel[0x38:0x3c] = b"ARM\x64"
    kernel_path = tmp / "DSM.Image"
    kernel_path.write_bytes(kernel)
    initrd = newc({"init": b"diskless-dsm-init"})
    initrd_path = tmp / "DSM.initrd.cpio"
    initrd_path.write_bytes(initrd)

    output = tmp / "prepared.cpio.gz"
    result = cli(ROOT / "research/arm64/loader/prepare-dsm-kexec.py",
                 target, kernel_path, initrd_path, output)
    assert result.returncode == 0, result.stderr
    entries = read_newc(gzip.decompress(output.read_bytes()))
    assert entries["boot/DSM_DS124_72806.Image"][1] == bytes(kernel)
    assert entries["boot/DSM_DS124_72806.initrd.cpio"][1] == initrd
    assert b"nr_cpus=2" in entries["init"][1]
    assert b"irqchip.gicv3_nolpi=1" not in entries["init"][1]
    assert b"libata.force=noncq" in entries["init"][1]
    assert entries["init"][0] & 0o777 == 0o755

    compressed_kernel = tmp / "DSM.zImage"
    compressed_kernel.write_bytes(lzma.compress(bytes(kernel), format=lzma.FORMAT_ALONE))
    compressed_initrd = tmp / "DSM.rd.bin"
    compressed_initrd.write_bytes(lzma.compress(initrd, format=lzma.FORMAT_ALONE))
    compressed_output = tmp / "prepared-compressed-inputs.cpio.gz"
    compressed_result = cli(ROOT / "research/arm64/loader/prepare-dsm-kexec.py",
                            target, compressed_kernel, compressed_initrd, compressed_output)
    assert compressed_result.returncode == 0, compressed_result.stderr
    compressed_entries = read_newc(gzip.decompress(compressed_output.read_bytes()))
    assert compressed_entries["boot/DSM_DS124_72806.Image"][1] == bytes(kernel)
    assert compressed_entries["boot/DSM_DS124_72806.initrd.cpio"][1] == initrd

    assert cli(ROOT / "research/arm64/loader/prepare-dsm-kexec.py",
               target, kernel_path, initrd_path, output).returncode != 0
    invalid_kernel = tmp / "invalid.Image"
    invalid_kernel.write_bytes(b"not-an-arm64-image")
    invalid = cli(ROOT / "research/arm64/loader/prepare-dsm-kexec.py",
                  target, invalid_kernel, initrd_path, tmp / "invalid-out.cpio.gz")
    assert invalid.returncode != 0 and "neither in the expected raw format nor LZMA-alone" in invalid.stderr
    bad_cpio = tmp / "bad.cpio"
    bad_cpio.write_bytes(b"not-cpio")
    invalid = cli(ROOT / "research/arm64/loader/prepare-dsm-kexec.py",
                  target, kernel_path, bad_cpio, tmp / "invalid-cpio-out.cpio.gz")
    assert invalid.returncode != 0
    repo_output = ROOT / "research/arm64/work/should-not-be-created.cpio.gz"
    invalid = cli(ROOT / "research/arm64/loader/prepare-dsm-kexec.py",
                  target, kernel_path, initrd_path, repo_output)
    assert invalid.returncode != 0 and "outside the repository" in invalid.stderr
    symlink_kernel = tmp / "kernel-link"
    symlink_kernel.symlink_to(kernel_path)
    invalid = cli(ROOT / "research/arm64/loader/prepare-dsm-kexec.py",
                  target, symlink_kernel, initrd_path, tmp / "symlink-out.cpio.gz")
    assert invalid.returncode != 0 and "not a symlink" in invalid.stderr

    profile = research_profile("research-arm64-dsm-kexec")
    config = VMConfig(profile.id, "qemu-process", "none", 2, 2048)
    host = HostCapabilities("arm64", "arm64", ("qemu-system-aarch64",), False, False)
    plan = LinuxKexecProvider(DSM_PROVIDER_ID).build_plan(
        profile, config, host, str(kernel_path), str(initrd_path),
        cpu="max,lpa2=off", gic_version=3, its=True, loader_disable_lpi=True,
        serial_route="dsm-mmio16550")
    assert plan.profile_id == "research-arm64-dsm-kexec"
    assert plan.boot_provider == DSM_PROVIDER_ID
    assert plan.storage_ref == "none" and plan.accelerator == "tcg"
    assert plan.qemu_argv[plan.qemu_argv.index("-machine") + 1] == (
        "virt,accel=tcg,gic-version=3,dtb-kaslr-seed=off,its=on")
    assert plan.qemu_argv[plan.qemu_argv.index("-smp") + 1] == "2"
    assert plan.qemu_argv[plan.qemu_argv.index("-m") + 1] == "2048"
    assert "irqchip.gicv3_nolpi=1" in plan.qemu_argv[plan.qemu_argv.index("-append") + 1]
    assert plan.qemu_argv[-5:] == ("-serial", "null", "-serial", "stdio", "-no-reboot")
    assert "-nic" in plan.qemu_argv and "none" in plan.qemu_argv
    assert "-drive" not in plan.qemu_argv and "-cdrom" not in plan.qemu_argv
    assert "research-arm64-dsm-kexec" not in legacy_profile_ids()

    snapshot_dir = tmp / "snapshot-scratch"
    snapshot_dir.mkdir(mode=0o700)
    snapshot_disk = create_scratch_sata1(snapshot_dir, ROOT)
    assert verify_scratch_sata1(snapshot_dir, ROOT) == snapshot_disk
    snapshot_config = VMConfig(profile.id, "qemu-process", "scratch-sata1-snapshot", 2, 2048)
    snapshot_plan = LinuxKexecProvider(DSM_PROVIDER_ID).build_plan(
        profile, snapshot_config, host, str(kernel_path), str(initrd_path),
        cpu="max,lpa2=off", gic_version=3, its=True, loader_disable_lpi=True,
        serial_route="dsm-mmio16550", scratch_sata1=str(snapshot_disk),
        scratch_sata1_snapshot=True)
    assert snapshot_plan.storage_ref == "scratch-sata1-snapshot"
    assert snapshot_plan.qemu_argv[snapshot_plan.qemu_argv.index("-drive") + 1].endswith(
        ",format=raw,if=ide,index=0,snapshot=on")
    with snapshot_disk.open("r+b") as stream:
        stream.write(b"nonblank")
    try:
        verify_scratch_sata1(snapshot_dir, ROOT)
    except ValueError:
        pass
    else:
        raise AssertionError("scratch disk verifier accepted allocated, modified backing image")
    try:
        LinuxKexecProvider(DSM_PROVIDER_ID).build_plan(
            profile, config, host, str(kernel_path), str(initrd_path),
            cpu="max,lpa2=off", gic_version=3, its=True, loader_disable_lpi=True,
            serial_route="dsm-mmio16550", scratch_sata1_snapshot=True)
    except ContractError:
        pass
    else:
        raise AssertionError("DS124 provider accepted snapshot mode without a scratch image")
    for kwargs in (
        {"its": False},
        {"loader_disable_lpi": False},
        {"cpu": "cortex-a55"},
        {"serial_route": "pl011"},
    ):
        try:
            LinuxKexecProvider(DSM_PROVIDER_ID).build_plan(
                profile, config, host, str(kernel_path), str(initrd_path),
                cpu=kwargs.get("cpu", "max,lpa2=off"), gic_version=3,
                its=kwargs.get("its", True),
                loader_disable_lpi=kwargs.get("loader_disable_lpi", True),
                serial_route=kwargs.get("serial_route", "dsm-mmio16550"))
        except ContractError:
            pass
        else:
            raise AssertionError(f"DS124 provider accepted unsupported settings: {kwargs}")

    valid_log = "\n".join((
        "Linux version 5.10.55+ (fixture)",
        "Trying to unpack rootfs image as initramfs...",
        "Freeing initrd memory: 14964K",
        "Exit on error [1] DISK NOT INSTALLED...",
        ":: Starting /etc/rc",
        "SynologyNAS login:",
    ))
    verifier.verify(valid_log)
    verifier.verify(valid_log + "\nprintk: debug: harmless debug output")
    for invalid_log in ("Linux version 5.10.55+", valid_log + "\nKernel panic: fixture"):
        try:
            verifier.verify(invalid_log)
        except ValueError:
            pass
        else:
            raise AssertionError("DSM kexec verifier accepted incomplete or failed evidence")

    stock_initrd_sata_log = "\n".join(initrd_sata_verifier.REQUIRED)
    initrd_sata_verifier.verify(stock_initrd_sata_log)
    for invalid_log in (
        stock_initrd_sata_log.replace("QEMU HARDDISK", "missing disk"),
        stock_initrd_sata_log + "\nKernel panic: fixture",
    ):
        try:
            initrd_sata_verifier.verify(invalid_log)
        except ValueError:
            pass
        else:
            raise AssertionError("DSM initrd SATA verifier accepted missing disk or panic evidence")

    buildroot_output = tmp / "buildroot-output"
    (buildroot_output / "target").mkdir(parents=True)
    (buildroot_output / "target/init").write_text("#!/bin/sh\n")
    (buildroot_output / "images").mkdir()
    (buildroot_output / "images/Image").write_bytes(b"loader-kernel")
    fake_bin = tmp / "fake-bin"
    fake_bin.mkdir()
    fake_qemu = fake_bin / "qemu-system-aarch64"
    fake_qemu.write_text(
        "#!/usr/bin/env python3\n"
        "import os, sys\n"
        "args = sys.argv[1:]\n"
        "assert args[args.index('-machine') + 1] == 'virt,accel=tcg,gic-version=3,dtb-kaslr-seed=off,its=on'\n"
        "assert args[args.index('-smp') + 1] == '2' and args[args.index('-m') + 1] == '2048'\n"
        "assert args[args.index('-cpu') + 1] == 'max,lpa2=off'\n"
        "assert '-nic' in args and args[args.index('-nic') + 1] == 'none'\n"
        "assert '-serial' in args and args[args.index('-serial') + 1] == 'null'\n"
        "assert '-cdrom' not in args\n"
        "if os.environ.get('EXPECT_SCRATCH'):\n"
        "    from pathlib import Path\n"
        "    drive = args[args.index('-drive') + 1]\n"
        "    scratch = Path(drive.split('file=', 1)[1].split(',', 1)[0])\n"
        "    expected_suffix = ',format=raw,if=ide,index=0'\n"
        "    if os.environ.get('EXPECT_SNAPSHOT'):\n"
        "        expected_suffix += ',snapshot=on'\n"
        "    assert drive.endswith(expected_suffix)\n"
        "    assert scratch.stat().st_size == 2 * 1024 * 1024 * 1024\n"
        "    assert scratch.stat().st_blocks == 0 and scratch.stat().st_mode & 0o777 == 0o600\n"
        "else:\n"
        "    assert '-drive' not in args\n"
        "from pathlib import Path\n"
        "print(Path(os.environ['DSM_FIXTURE_LOG']).read_text())\n"
        "if os.environ.get('FAKE_DSM_PANIC'):\n"
        "    print('Kernel panic: synthetic failure')\n",
        encoding="utf-8")
    fake_timeout = fake_bin / "timeout-wrapper"
    fake_timeout.write_text(
        "#!/usr/bin/env python3\n"
        "import subprocess, sys\n"
        "if sys.argv[1:4] != ['--signal=TERM', '--kill-after=5s', '180s']:\n"
        "    raise SystemExit(90)\n"
        "result = subprocess.run(sys.argv[4:])\n"
        "raise SystemExit(124 if result.returncode == 0 else result.returncode)\n",
        encoding="utf-8")
    fake_qemu.chmod(0o755)
    fake_timeout.chmod(0o755)
    fake_log = tmp / "valid-dsm.log"
    fake_log.write_text(valid_log)

    def run_fake(output_dir, *, panic=False, scratch=False, runner=None, fixture=None):
        env = os.environ.copy()
        env.update({"QEMU": str(fake_qemu), "TIMEOUT": str(fake_timeout),
                    "DSM_FIXTURE_LOG": str(fixture or fake_log)})
        if panic:
            env["FAKE_DSM_PANIC"] = "1"
        if scratch:
            env["EXPECT_SCRATCH"] = "1"
            if runner == ROOT / "research/arm64/loader/test-dsm-initrd-sata.sh":
                env["EXPECT_SNAPSHOT"] = "1"
        script = runner or (ROOT / "research/arm64/loader/test-dsm-kexec.sh")
        return subprocess.run(
            ["bash", str(script),
             str(buildroot_output), str(kernel_path), str(initrd_path), str(output_dir)],
            env=env, capture_output=True, text=True)

    success = run_fake(tmp / "runner-output")
    assert success.returncode == 0, success.stdout + success.stderr
    assert "diskless login prompt" in success.stdout
    failure = run_fake(tmp / "runner-panic-output", panic=True)
    assert failure.returncode != 0 and "Kernel panic" in failure.stderr

    initrd_sata_fixture = tmp / "valid-dsm-initrd-sata.log"
    initrd_sata_fixture.write_text("\n".join(initrd_sata_verifier.REQUIRED))
    initrd_sata_runner = ROOT / "research/arm64/loader/test-dsm-initrd-sata.sh"
    initrd_sata_output = tmp / "runner-initrd-sata-output"
    initrd_sata_success = run_fake(initrd_sata_output, scratch=True,
                                   runner=initrd_sata_runner, fixture=initrd_sata_fixture)
    assert initrd_sata_success.returncode == 0, (
        initrd_sata_success.stdout + initrd_sata_success.stderr)
    assert "backing image remains sparse and blank" in initrd_sata_success.stdout
    assert (initrd_sata_output / "dockdsm-ds124-scratch-sata1.img").exists()
    assert (initrd_sata_output / "dsm-stock-initrd-sata.log").is_file()

    missing_disk_fixture = tmp / "missing-dsm-sata-disk.log"
    missing_disk_fixture.write_text("\n".join(initrd_sata_verifier.REQUIRED).replace(
        "QEMU HARDDISK", "missing disk"))
    initrd_sata_failure = run_fake(
        tmp / "runner-initrd-sata-failure", scratch=True,
        runner=initrd_sata_runner, fixture=missing_disk_fixture)
    assert initrd_sata_failure.returncode != 0
    assert "missing DSM initrd SATA evidence" in initrd_sata_failure.stderr

print("ARM64 DSM kexec research harness tests passed (synthetic inputs only; no PAT or QEMU boot used).")
