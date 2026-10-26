#!/usr/bin/env python3
"""Synthetic contracts for the isolated DS124 kernel SATA discovery probe."""
import contextlib
import importlib.util
import io
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
from linux_kexec_provider import (  # noqa: E402
    DSM_PROVIDER_ID,
    DSM_SCRATCH_DISK,
    DSM_SCRATCH_DISK_BYTES,
    LinuxKexecProvider,
)
from profile_registry import research_profile  # noqa: E402
from scratch_disk import create_scratch_sata1  # noqa: E402


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


verifier = load("verify_dsm_sata_probe", ROOT / "research/arm64/loader/verify-dsm-sata-probe.py")
pack_probe = load("make_dsm_sata_probe_initrd", ROOT / "research/arm64/loader/make-dsm-sata-probe-initrd.py")


def cli(*args, env=None):
    return subprocess.run([str(item) for item in args], capture_output=True, text=True, env=env)


valid_log = "\n".join((
    "Linux version 5.10.55+ DSM #72806",
    "rtk_ahci b100000.sata: AHCI 0001.0000 32 slots 1 ports 1.5 Gbps 0x1 impl platform mode",
    "ata1: SATA link up 1.5 Gbps (SStatus 113 SControl 300)",
    "ata1.00: ATA-7: QEMU HARDDISK, 2.5+, max UDMA/100",
    "scsi 0:0:0:0: Direct-Access     QEMU     HARDDISK                 2.5+ PQ: 0 ANSI: 5",
    "DOCKDSM_DS124_SATA_PROBE_INIT",
    "major minor  #blocks  name",
    "   8        0    2097152 sata1",
    "DOCKDSM_DS124_SATA_PROBE_PASS sectors=4194304",
    "reboot: Power down",
))
verifier.verify(valid_log)
verifier.verify(valid_log + "\nprintk: debug: harmless diagnostic\n")
for failure_marker in (
    "DOCKDSM_DS124_SATA_PROBE_FAIL_NO_BLOCK_DEVICE",
    "DOCKDSM_DS124_SATA_PROBE_FAIL_SIZE sectors=1024",
):
    try:
        verifier.verify(valid_log.replace(
            "DOCKDSM_DS124_SATA_PROBE_PASS sectors=4194304", failure_marker))
    except ValueError as error:
        assert "DOCKDSM_DS124_SATA_PROBE_FAIL_" in str(error)
    else:
        raise AssertionError("SATA probe verifier accepted a failure marker")
for bad in (
    valid_log.replace("ata1: SATA link up 1.5 Gbps", "ata1: SATA link down"),
    valid_log.replace("   8        0    2097152 sata1", "   8        0       1024 sata1"),
    valid_log + "\nKernel panic - not syncing: synthetic\n",
    valid_log + "\nDOCKDSM_DS124_SATA_PROBE_ERROR_POWEROFF_RETURNED\n",
):
    try:
        verifier.verify(bad)
    except ValueError:
        pass
    else:
        raise AssertionError("SATA probe verifier accepted incomplete or failed evidence")

profile = research_profile("research-arm64-dsm-kexec")
host = HostCapabilities("arm64", "arm64", ("qemu-system-aarch64",), False, False)
diskless_config = VMConfig(profile.id, "qemu-process", "none", 2, 2048)
kernel = Path(__file__).resolve()
initrd = Path(ROOT / "research/arm64/loader/board/arm64-kexec/sata-probe-init")
init_text = initrd.read_text(encoding="utf-8")
for branch, marker in (
    ("if [ ! -b /dev/sata1 ] || [ ! -r /sys/block/sata1/size ]; then",
     "DOCKDSM_DS124_SATA_PROBE_FAIL_NO_BLOCK_DEVICE"),
    ('if [ "$sectors" != 4194304 ]; then',
     'DOCKDSM_DS124_SATA_PROBE_FAIL_SIZE sectors=$sectors'),
):
    start = init_text.index(branch)
    end = init_text.index("\nfi", start)
    failure_path = init_text[start:end]
    assert marker in failure_path
    assert failure_path.index(marker) < failure_path.index("sync")
    assert failure_path.index("sync") < failure_path.index("poweroff -f")
    assert failure_path.index("poweroff -f") < failure_path.index("exec sh")
    assert "exit 1" not in failure_path
provider = LinuxKexecProvider(DSM_PROVIDER_ID)

with tempfile.TemporaryDirectory(prefix="dockdsm-dsm-sata-probe-") as temporary:
    tmp = Path(temporary)
    private = tmp / "private-output"
    private.mkdir(mode=0o700)
    os.chmod(private, 0o700)
    disk = create_scratch_sata1(private, ROOT)
    assert disk.name == DSM_SCRATCH_DISK
    assert disk.stat().st_size == DSM_SCRATCH_DISK_BYTES
    assert stat.S_IMODE(disk.stat().st_mode) == 0o600
    assert disk.stat().st_nlink == 1
    with disk.open("rb") as stream:
        assert stream.read(4096) == bytes(4096)
        stream.seek(-4096, os.SEEK_END)
        assert stream.read() == bytes(4096)
    try:
        create_scratch_sata1(private, ROOT)
    except ValueError as error:
        assert "refusing to reuse or overwrite" in str(error)
    else:
        raise AssertionError("scratch disk helper reused an existing image")

    config = VMConfig(profile.id, "qemu-process", "scratch-sata1", 2, 2048)
    plan = provider.build_plan(
        profile, config, host, str(kernel), str(initrd), cpu="max,lpa2=off",
        gic_version=3, its=True, loader_disable_lpi=True,
        serial_route="dsm-mmio16550", scratch_sata1=str(disk))
    drive = plan.qemu_argv[plan.qemu_argv.index("-drive") + 1]
    assert drive == f"file={disk},format=raw,if=ide,index=0"
    assert "-nic" in plan.qemu_argv and plan.qemu_argv[plan.qemu_argv.index("-nic") + 1] == "none"
    assert "-drive" not in provider.build_plan(
        profile, diskless_config, host, str(kernel), str(initrd), cpu="max,lpa2=off",
        gic_version=3, its=True, loader_disable_lpi=True,
        serial_route="dsm-mmio16550").qemu_argv

    bad_disk = tmp / DSM_SCRATCH_DISK
    bad_disk.write_bytes(b"not-a-2-GiB-scratch-image")
    try:
        provider.build_plan(profile, config, host, str(kernel), str(initrd),
                            cpu="max,lpa2=off", gic_version=3, its=True,
                            loader_disable_lpi=True, serial_route="dsm-mmio16550",
                            scratch_sata1=str(bad_disk))
    except ContractError:
        pass
    else:
        raise AssertionError("provider accepted an incorrectly sized scratch disk")

    allocated_dir = tmp / "allocated-private"
    allocated_dir.mkdir(mode=0o700)
    os.chmod(allocated_dir, 0o700)
    allocated_disk = allocated_dir / DSM_SCRATCH_DISK
    with allocated_disk.open("wb") as stream:
        stream.truncate(DSM_SCRATCH_DISK_BYTES)
        stream.write(b"x")
    try:
        provider.build_plan(profile, config, host, str(kernel), str(initrd),
                            cpu="max,lpa2=off", gic_version=3, its=True,
                            loader_disable_lpi=True, serial_route="dsm-mmio16550",
                            scratch_sata1=str(allocated_disk))
    except ContractError:
        pass
    else:
        raise AssertionError("provider accepted an allocated nonblank scratch image")

    link_dir = tmp / "link-output"
    link_dir.mkdir(mode=0o700)
    os.chmod(link_dir, 0o700)
    (link_dir / DSM_SCRATCH_DISK).symlink_to(disk)
    try:
        provider.build_plan(profile, config, host, str(kernel), str(initrd),
                            cpu="max,lpa2=off", gic_version=3, its=True,
                            loader_disable_lpi=True, serial_route="dsm-mmio16550",
                            scratch_sata1=str(link_dir / DSM_SCRATCH_DISK))
    except ContractError:
        pass
    else:
        raise AssertionError("provider accepted a symlink scratch disk")

    public = tmp / "public-output"
    public.mkdir(mode=0o755)
    try:
        create_scratch_sata1(public, ROOT)
    except ValueError as error:
        assert "mode 0700" in str(error)
    else:
        raise AssertionError("scratch disk helper accepted a public output directory")

    buildroot_target = tmp / "buildroot-target"
    (buildroot_target / "bin").mkdir(parents=True)
    (buildroot_target / "bin/busybox").write_bytes(b"busybox-fixture")
    (buildroot_target / "init").write_text("#!/bin/sh\nexit 0\n")
    probe_initrd = tmp / "probe-initrd.cpio.gz"
    packed = pack_probe.main(["make-dsm-sata-probe-initrd.py", str(buildroot_target),
                              str(probe_initrd)])
    assert packed == 0
    probe_archive = probe_initrd.read_bytes()
    assert probe_archive.startswith(b"070701")
    assert b"DOCKDSM_DS124_SATA_PROBE_PASS sectors=" in probe_archive
    with contextlib.redirect_stderr(io.StringIO()):
        assert pack_probe.main(["make-dsm-sata-probe-initrd.py", str(buildroot_target),
                                str(probe_initrd)]) == 2

    buildroot_output = tmp / "buildroot-output"
    (buildroot_output / "target/bin").mkdir(parents=True)
    (buildroot_output / "target/bin/busybox").write_bytes(b"busybox-fixture")
    (buildroot_output / "target/init").write_text("#!/bin/sh\nexit 0\n")
    (buildroot_output / "images").mkdir()
    (buildroot_output / "images/Image").write_bytes(b"loader-kernel-fixture")
    dsm_kernel = tmp / "DSM.Image"
    image = bytearray(b"K" * 96)
    image[0x38:0x3c] = b"ARM\x64"
    dsm_kernel.write_bytes(image)

    fake_bin = tmp / "fake-bin"
    fake_bin.mkdir()
    fake_qemu = fake_bin / "qemu-system-aarch64"
    fake_qemu.write_text(
        "#!/usr/bin/env python3\n"
        "import os, sys\n"
        "from pathlib import Path\n"
        "args = sys.argv[1:]\n"
        "assert args[args.index('-machine') + 1] == 'virt,accel=tcg,gic-version=3,dtb-kaslr-seed=off,its=on'\n"
        "assert args[args.index('-cpu') + 1] == 'max,lpa2=off'\n"
        "assert args[args.index('-nic') + 1] == 'none'\n"
        "drive = args[args.index('-drive') + 1]\n"
        "assert drive.endswith(',format=raw,if=ide,index=0'), drive\n"
        "disk = Path(drive.split('file=', 1)[1].split(',format=', 1)[0])\n"
        "assert disk.name == 'dockdsm-ds124-scratch-sata1.img' and disk.stat().st_size == 2 * 1024**3\n"
        "assert disk.stat().st_mode & 0o077 == 0\n"
        "print(Path(os.environ['DSM_FIXTURE_LOG']).read_text())\n",
        encoding="utf-8")
    fake_timeout = fake_bin / "timeout-wrapper"
    fake_timeout.write_text(
        "#!/usr/bin/env python3\n"
        "import os, sys\n"
        "if sys.argv[1:4] != ['--signal=TERM', '--kill-after=5s', '180s']:\n"
        "    raise SystemExit(90)\n"
        "os.execvp(sys.argv[4], sys.argv[4:])\n",
        encoding="utf-8")
    fake_qemu.chmod(0o755)
    fake_timeout.chmod(0o755)
    fixture_log = tmp / "sata.log"
    fixture_log.write_text(valid_log)
    output = tmp / "runner-output"
    environment = os.environ.copy()
    environment.update({"QEMU": str(fake_qemu), "TIMEOUT": str(fake_timeout),
                        "DSM_FIXTURE_LOG": str(fixture_log)})
    result = subprocess.run(
        ["bash", str(ROOT / "research/arm64/loader/test-dsm-sata-probe.sh"),
         str(buildroot_output), str(dsm_kernel), str(output)],
        capture_output=True, text=True, env=environment)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "powered off cleanly" in result.stdout
    assert (output / DSM_SCRATCH_DISK).stat().st_size == DSM_SCRATCH_DISK_BYTES
    assert cli("bash", ROOT / "research/arm64/loader/test-dsm-sata-probe.sh",
               buildroot_output, dsm_kernel, output).returncode != 0

print("ARM64 DS124 SATA probe contracts passed (synthetic fixtures only; no QEMU boot or DSM disk used).")
