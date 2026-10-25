#!/usr/bin/env python3
"""Validate legacy provider mappings against platform defaults and fixtures."""
import os
import json
import signal
import subprocess
import sys
from pathlib import Path
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src/platform"))

from boot_provider import ContractError, HostCapabilities, VMConfig  # noqa: E402
from legacy_provider import (  # noqa: E402
    LegacyPlatformFacts,
    bind_legacy_environment,
    bind_legacy_platform,
    build_legacy_launch_plan,
    _probe_kvm,
)
from profile_registry import (  # noqa: E402
    legacy_profile,
    legacy_profile_ids,
    research_profile,
)


def rejects(action):
    try:
        action()
    except ContractError:
        return
    raise AssertionError("unsupported legacy platform facts were accepted")


def check_shell_environment():
    binding = bind_legacy_environment(os.environ)
    assert binding.profile.id == os.environ["DSM_PLATFORM"]
    print(f"Legacy provider mapping passed for {binding.profile.id}.")


def check_launch_plan(argv):
    binding = bind_legacy_environment(os.environ)
    required = ("PLAN_HOST_ARCH", "PLAN_CONTAINER_ARCH", "PLAN_ACCELERATOR",
                "PLAN_KVM_ACCESS", "PLAN_KVM_PROBE")
    missing = [name for name in required if name not in os.environ]
    if missing:
        raise SystemExit("missing synthetic LaunchPlan facts: " + ", ".join(missing))
    booleans = {}
    for name in ("PLAN_KVM_ACCESS", "PLAN_KVM_PROBE"):
        value = os.environ[name]
        if value not in ("true", "false", "unknown"):
            raise SystemExit(f"invalid synthetic capability value: {name}")
        booleans[name] = None if value == "unknown" else value == "true"
    host = HostCapabilities(
        os.environ["PLAN_HOST_ARCH"], os.environ["PLAN_CONTAINER_ARCH"],
        (binding.qemu_binary,), booleans["PLAN_KVM_ACCESS"], booleans["PLAN_KVM_PROBE"])
    config = VMConfig(binding.profile.id, "docker", "/isolated/legacy-test-disk", 2, 2048)
    plan = binding.provider.build_plan(
        binding.profile, config, host, (binding.qemu_binary, *argv),
        os.environ["PLAN_ACCELERATOR"])
    assert plan.qemu_argv[1:] == tuple(argv)
    print(f"Synthetic legacy LaunchPlan contract verified for {binding.profile.id}: {plan.plan_hash}")


assert legacy_profile_ids() == ("virtualdsm", "rtd1619b")
assert legacy_profile("virtualdsm").boot_provider == "virtualdsm-legacy"
assert research_profile("research-arm64-linux-kexec").dsm_platform == "open-linux"
assert research_profile("research-x86_64-grub-linux").dsm_platform == "open-linux"
rejects(lambda: legacy_profile("research-arm64-linux-kexec"))
rejects(lambda: legacy_profile("full-arm64"))
rejects(lambda: research_profile("rtd1619b"))

if sys.argv[1:] == ["--check-env"]:
    check_shell_environment()
    raise SystemExit(0)
if sys.argv[1:2] == ["--plan-argv"]:
    check_launch_plan(sys.argv[2:])
    raise SystemExit(0)

x86 = bind_legacy_platform(LegacyPlatformFacts(
    "virtualdsm", "amd64", "x64", "qemu-system-x86_64", "q35", "legacy"))
arm = bind_legacy_platform(LegacyPlatformFacts(
    "rtd1619b", "arm64", "arm64", "qemu-system-aarch64", "virt", "direct"))
assert (x86.profile.boot_provider, x86.profile.guest_arch, x86.profile.bootloader_arch) == (
    "virtualdsm-legacy", "amd64", None)
assert (arm.profile.boot_provider, arm.profile.guest_arch, arm.profile.bootloader_arch) == (
    "rtd1619b-direct", "arm64", None)

legacy_x86_environment = {
    "DSM_PLATFORM": "virtualdsm", "GUEST_ARCH": "amd64", "PLATFORM": "x64",
    "QEMU_BIN": "qemu-system-x86_64", "MACHINE": "q35", "BOOT_MODE": "legacy",
    "CONTAINER_ARCH": "amd64", "STORAGE": "/isolated",
}
for invalid_argv in ([], [None], [1], ["bad\x00arg"], "-machine q35"):
    try:
        build_legacy_launch_plan(legacy_x86_environment, invalid_argv)
    except ContractError:
        pass
    else:
        raise AssertionError(f"legacy provider accepted malformed QEMU argv: {invalid_argv!r}")

# These facts are synthetic unit-test inputs; they do not assert host KVM support.
x86_plan = x86.provider.build_plan(
    x86.profile, VMConfig("virtualdsm", "docker", "/tmp/x86-test-disk", 2, 2048),
    HostCapabilities("amd64", "amd64", (x86.qemu_binary,), False, None),
    (x86.qemu_binary, "-machine", "type=q35,accel=tcg"), "tcg")
arm_plan = arm.provider.build_plan(
    arm.profile, VMConfig("rtd1619b", "docker", "/tmp/arm-test-disk", 2, 2048),
    HostCapabilities("arm64", "arm64", (arm.qemu_binary,), False, None),
    (arm.qemu_binary, "-machine", "virt,gic-version=3"), "tcg")
assert x86_plan.guest_arch == "amd64" and arm_plan.guest_arch == "arm64"

for altered in (
    LegacyPlatformFacts("full-x86_64", "amd64", "x64", "qemu-system-x86_64", "q35", "legacy"),
    LegacyPlatformFacts("full-arm64", "arm64", "arm64", "qemu-system-aarch64", "virt", "direct"),
    LegacyPlatformFacts("virtualdsm", "arm64", "x64", "qemu-system-x86_64", "q35", "legacy"),
    LegacyPlatformFacts("rtd1619b", "arm64", "arm64", "qemu-system-aarch64", "q35", "direct"),
):
    rejects(lambda facts=altered: bind_legacy_platform(facts))

# The qemu-process adapter must preserve the planned argv and QEMU exit code.
with tempfile.TemporaryDirectory(prefix="legacy-qemu-runtime-") as tmp:
    root = Path(tmp)
    bindir = root / "bin"
    bindir.mkdir()
    capture = root / "argv.json"
    fake_qemu = bindir / "qemu-system-x86_64"
    fake_qemu.write_text(
        f"#!{sys.executable}\n"
        "import json, os, sys\n"
        "from pathlib import Path\n"
        "Path(os.environ['LEGACY_ARGV_CAPTURE']).write_text(json.dumps(sys.argv[1:]))\n"
        "raise SystemExit(37)\n"
    )
    fake_qemu.chmod(0o755)
    qemu_args = ["-machine", "type=q35,accel=tcg", "-smp", "2,sockets=1",
                 "-m", "2G", "-drive", "file=/isolated/test.img"]
    environment = dict(os.environ)
    environment.update({
        "PATH": str(bindir) + os.pathsep + environment.get("PATH", "/usr/bin:/bin"),
        "LEGACY_ARGV_CAPTURE": str(capture),
        "DSM_PLATFORM": "virtualdsm",
        "GUEST_ARCH": "amd64",
        "PLATFORM": "x64",
        "QEMU_BIN": "qemu-system-x86_64",
        "MACHINE": "q35",
        "BOOT_MODE": "legacy",
        "CONTAINER_ARCH": "arm64",
        "STORAGE": "/isolated",
        "DOCKDSM_ARM_KVM_PROBED": "false",
    })
    process = subprocess.run(
        [sys.executable, str(ROOT / "src/platform/legacy_provider.py"),
         "--exec-plan", *qemu_args], env=environment, check=False,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=15,
    )
    assert process.returncode == 37, (process.returncode, process.stderr)
    assert json.loads(capture.read_text()) == qemu_args
    assert "Legacy LaunchPlan SHA256:" in process.stderr

# Exercise the KVM probe construction with a fake QEMU and synthetic device
# node. This does not claim host KVM support.
with tempfile.TemporaryDirectory(prefix="legacy-kvm-probe-") as tmp:
    root = Path(tmp)
    fake_qemu = root / "qemu-system-x86_64"
    capture = root / "probe.json"
    fake_qemu.write_text(
        f"#!{sys.executable}\n"
        "import json, os, sys\n"
        "from pathlib import Path\n"
        "Path(os.environ['LEGACY_PROBE_CAPTURE']).write_text(json.dumps(sys.argv[1:]))\n"
        "raise SystemExit(0 if '-accel' in sys.argv and 'kvm' in sys.argv else 19)\n"
    )
    fake_qemu.chmod(0o755)
    fake_device = root / "kvm"
    fake_device.write_bytes(b"synthetic")
    fake_device.chmod(0o600)
    os.environ["LEGACY_PROBE_CAPTURE"] = str(capture)
    assert _probe_kvm(str(fake_qemu), "type=q35,smm=off,accel=kvm", str(fake_device)) == (True, True)
    probe_argv = json.loads(capture.read_text())
    assert probe_argv[:6] == ["-machine", "type=q35,smm=off", "-accel", "kvm", "-cpu", "host"], probe_argv
    del os.environ["LEGACY_PROBE_CAPTURE"]

# A failed KVM initialization must reject the plan before the runtime launches
# the QEMU command. The synthetic device and emulator never touch host KVM.
with tempfile.TemporaryDirectory(prefix="legacy-kvm-reject-") as tmp:
    root = Path(tmp)
    bindir = root / "bin"
    bindir.mkdir()
    probe_marker = root / "probe-ran"
    fake_qemu = bindir / "qemu-system-x86_64"
    fake_qemu.write_text(
        f"#!{sys.executable}\n"
        "import sys\n"
        "from pathlib import Path\n"
        f"Path({str(probe_marker)!r}).write_text('called')\n"
        "raise SystemExit(19)\n"
    )
    fake_qemu.chmod(0o755)
    fake_device = root / "kvm"
    fake_device.write_bytes(b"synthetic")
    fake_device.chmod(0o600)
    kvm_environment = {
        "DSM_PLATFORM": "virtualdsm", "GUEST_ARCH": "amd64", "PLATFORM": "x64",
        "QEMU_BIN": "qemu-system-x86_64", "MACHINE": "q35", "BOOT_MODE": "legacy",
        "CONTAINER_ARCH": "amd64", "STORAGE": "/isolated",
        "PATH": str(bindir),
    }
    try:
        build_legacy_launch_plan(
            kvm_environment,
            ["-machine", "type=q35,accel=kvm", "-enable-kvm", "-smp", "1", "-m", "128"],
            kvm_device=str(fake_device),
        )
    except ContractError:
        pass
    else:
        raise AssertionError("failed synthetic KVM probe was accepted")
    assert probe_marker.read_text() == "called"

# execvpe must retain the process ID and forward a termination signal to QEMU.
with tempfile.TemporaryDirectory(prefix="legacy-qemu-signal-") as tmp:
    root = Path(tmp)
    bindir = root / "bin"
    bindir.mkdir()
    pid_file = root / "qemu.pid"
    fake_qemu = bindir / "qemu-system-x86_64"
    fake_qemu.write_text(
        f"#!{sys.executable}\n"
        "import os, signal, sys, time\n"
        "from pathlib import Path\n"
        "Path(os.environ['LEGACY_PID_FILE']).write_text(str(os.getpid()))\n"
        "signal.signal(signal.SIGTERM, lambda *_: sys.exit(143))\n"
        "while True: time.sleep(0.05)\n"
    )
    fake_qemu.chmod(0o755)
    environment = dict(os.environ)
    environment.update({
        "PATH": str(bindir) + os.pathsep + environment.get("PATH", "/usr/bin:/bin"),
        "LEGACY_PID_FILE": str(pid_file),
        "DSM_PLATFORM": "virtualdsm", "GUEST_ARCH": "amd64", "PLATFORM": "x64",
        "QEMU_BIN": "qemu-system-x86_64", "MACHINE": "q35", "BOOT_MODE": "legacy",
        "CONTAINER_ARCH": "arm64", "STORAGE": "/isolated",
        "DOCKDSM_ARM_KVM_PROBED": "false",
    })
    process = subprocess.Popen(
        [sys.executable, str(ROOT / "src/platform/legacy_provider.py"), "--exec-plan",
         "-machine", "type=q35,accel=tcg", "-smp", "1", "-m", "128"],
        env=environment, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        deadline = time.monotonic() + 5
        while not pid_file.exists() and time.monotonic() < deadline:
            if process.poll() is not None:
                raise AssertionError(f"QEMU runtime exited before exec: {process.returncode}")
            time.sleep(0.01)
        assert pid_file.is_file(), "fake QEMU did not start"
        assert int(pid_file.read_text()) == process.pid, "execvpe changed the QEMU PID"
        process.send_signal(signal.SIGTERM)
        assert process.wait(timeout=5) == 143
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)

print("Legacy Boot Provider tests passed (profile binding, argv passthrough, KVM probe policy).")
