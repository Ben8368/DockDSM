#!/usr/bin/env python3
"""Tests for the side-effect-free Boot Provider contracts."""
import sys
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src/platform"))

from boot_provider import (  # noqa: E402
    ContractError,
    HostCapabilities,
    Profile,
    QemuArgvProvider,
    VMConfig,
)


def rejects(action):
    try:
        action()
    except ContractError:
        return
    raise AssertionError("invalid boot contract was accepted")


profile = Profile("legacy-x86", "virtualdsm", "amd64", "virtualdsm-legacy", "q35")
host = HostCapabilities("arm64", "arm64", ("qemu-system-x86_64",), False, None)
config = VMConfig(profile.id, "docker", "/isolated/test-disk", 2, 2048)
provider = QemuArgvProvider("virtualdsm-legacy")
plan = provider.build_plan(
    profile, config, host,
    ("qemu-system-x86_64", "-machine", "type=q35,accel=tcg", "-drive", "file=/isolated/test-disk"),
    "tcg",
)

assert plan.host_arch == "arm64"
assert plan.container_arch == "arm64"
assert plan.guest_arch == "amd64"
assert plan.bootloader_arch is None
assert plan.qemu_argv[4] == "file=/isolated/test-disk"
assert len(plan.plan_hash) == 64
assert plan.plan_hash == provider.build_plan(
    profile, config, host,
    ("qemu-system-x86_64", "-machine", "type=q35,accel=tcg", "-drive", "file=/isolated/test-disk"),
    "tcg",
).plan_hash
assert type(plan).from_dict(plan.to_dict()) == plan
schema = json.loads((ROOT / "src/platform/boot-provider.schema.json").read_text())
assert schema["$defs"]["LaunchPlan"]["additionalProperties"] is False
assert schema["$defs"]["HostCapabilities"]["properties"]["host_arch"]["anyOf"][-1] == {"type": "null"}
assert schema["$defs"]["LaunchPlan"]["properties"]["host_arch"]["anyOf"][-1] == {"type": "null"}
text_pattern = re.compile(schema["$defs"]["nonemptyText"]["pattern"])
argv_pattern = re.compile(schema["$defs"]["LaunchPlan"]["properties"]["qemu_argv"]["items"]["pattern"])
assert text_pattern.fullmatch("qemu-system-x86_64")
assert not text_pattern.fullmatch("bad\x00binary")
assert argv_pattern.fullmatch("") and not argv_pattern.fullmatch("bad\x00arg")

# The existing ARM64 direct-kernel profile keeps guest and bootloader identity
# separate; this plan is synthetic and does not claim a DSM boot was executed.
arm_profile = Profile("ds124-direct", "rtd1619b", "arm64", "rtd1619b-direct", "virt")
arm_host = HostCapabilities("arm64", "arm64",
                            ("qemu-system-aarch64", "qemu-system-x86_64"), None, None)
arm_config = VMConfig(arm_profile.id, "docker", "/isolated/arm-test-disk", 2, 2048)
arm_plan = QemuArgvProvider("rtd1619b-direct").build_plan(
    arm_profile, arm_config, arm_host,
    ("qemu-system-aarch64", "-machine", "virt,gic-version=3"), "tcg",
)
assert arm_plan.host_arch == arm_plan.container_arch == arm_plan.guest_arch == "arm64"
assert arm_plan.bootloader_arch is None
assert arm_plan.plan_hash != plan.plan_hash
arm_kvm_host = HostCapabilities("arm64", "arm64", ("qemu-system-aarch64",), True, True)
arm_kvm_plan = QemuArgvProvider("rtd1619b-direct").build_plan(
    arm_profile, arm_config, arm_kvm_host,
    ("qemu-system-aarch64", "-M", "virt", "-accel", "kvm"), "kvm",
)
assert arm_kvm_plan.accelerator == "kvm"  # Synthetic capability input; no host probe ran.

# A container cannot reliably observe its outer host architecture. Unknown is
# represented as null; KVM still requires accessible /dev/kvm and a successful
# QEMU probe, while the container and guest architectures must match.
unknown_host = HostCapabilities(None, "arm64", ("qemu-system-aarch64",), True, True)
unknown_host_plan = QemuArgvProvider("rtd1619b-direct").build_plan(
    arm_profile, arm_config, unknown_host,
    ("qemu-system-aarch64", "-M", "virt", "-accel", "kvm"), "kvm",
)
assert unknown_host_plan.host_arch is None
assert type(unknown_host_plan).from_dict(unknown_host_plan.to_dict()) == unknown_host_plan
assert HostCapabilities.from_dict(unknown_host.to_dict()) == unknown_host
rejects(lambda: QemuArgvProvider("rtd1619b-direct").build_plan(
    arm_profile, arm_config,
    HostCapabilities(None, "arm64", ("qemu-system-aarch64",), True, None),
    ("qemu-system-aarch64", "-M", "virt", "-accel", "kvm"), "kvm"))

x86_kvm_host = HostCapabilities("amd64", "amd64", ("qemu-system-x86_64",), True, True)
x86_kvm_plan = provider.build_plan(
    profile, config, x86_kvm_host,
    ("qemu-system-x86_64", "-machine", "type=q35,accel=kvm", "-enable-kvm"), "kvm",
)
assert x86_kvm_plan.accelerator == "kvm"

round_trip_profile = Profile.from_dict(profile.to_dict())
assert round_trip_profile == profile
round_trip_host = HostCapabilities.from_dict(host.to_dict())
assert round_trip_host == host
round_trip_config = VMConfig.from_dict(config.to_dict())
assert round_trip_config == config

rejects(lambda: Profile.from_dict({**profile.to_dict(), "new_field": True}))
rejects(lambda: Profile.from_dict({**profile.to_dict(), "schema_version": True}))
rejects(lambda: Profile("legacy-x86", "virtualdsm", "amd64", "legacy", "q35", schema_version=True))
rejects(lambda: HostCapabilities.from_dict({**host.to_dict(), "kvm_access": 1}))
rejects(lambda: HostCapabilities.from_dict({**host.to_dict(), "kvm_probe": 1}))
rejects(lambda: HostCapabilities("arm64", "arm64", ("bad\x00qemu",), False, None))
rejects(lambda: type(plan).from_dict({**plan.to_dict(), "runtime_shell": "sh -c"}))
rejects(lambda: type(plan).from_dict({**plan.to_dict(), "qemu_machine": "virt"}))
rejects(lambda: type(plan).from_dict({**plan.to_dict(), "accelerator": "kvm"}))
rejects(lambda: HostCapabilities("arm64", "arm64", (), False, None, schema_version=True))
rejects(lambda: VMConfig.from_dict({**config.to_dict(), "schema_version": 99}))
rejects(lambda: VMConfig.from_dict({**config.to_dict(), "vcpus": True}))
rejects(lambda: VMConfig("x", "docker", "disk", 1, 1, schema_version=True))
rejects(lambda: type(plan)(plan.profile_id, plan.boot_provider, plan.host_arch,
                           plan.container_arch, plan.guest_arch, plan.bootloader_arch,
                           plan.qemu_machine,
                           plan.runtime_adapter, plan.storage_ref, plan.qemu_argv,
                           plan.accelerator, schema_version=True))
rejects(lambda: provider.build_plan(profile, VMConfig("other", "docker", "disk", 1, 1024),
                                    host, ("qemu-system-x86_64",), "tcg"))
rejects(lambda: provider.build_plan(profile, config, host,
                                    ("qemu-system-aarch64",), "tcg"))
rejects(lambda: provider.build_plan(profile, config, host,
                                    ("qemu-system-x86_64", "-machine", "virt"), "tcg"))
rejects(lambda: provider.build_plan(
    profile, config, host,
    ("qemu-system-x86_64", "-machine", "type=q35,accel=kvm", "-enable-kvm"), "tcg"))
rejects(lambda: provider.build_plan(
    profile, config, host,
    ("qemu-system-x86_64", "-machine", "type=q35,accel=tcg", "-accel", "kvm"), "tcg"))
rejects(lambda: provider.build_plan(
    profile, config, host,
    ("qemu-system-x86_64", "-machine", "type=q35,accel=kvm", "-enable-kvm"), "tcg"))
rejects(lambda: provider.build_plan(
    profile, config, host,
    ("qemu-system-x86_64", "-machine", "type=q35", "-accel", "hvf"), "tcg"))
rejects(lambda: provider.build_plan(
    profile, config, host,
    ("qemu-system-x86_64", "-machine", "type=q35,accel=tcg,accel=kvm"), "tcg"))
rejects(lambda: provider.build_plan(profile, config, host,
                                    ("qemu-system-x86_64",), "kvm"))
rejects(lambda: QemuArgvProvider("another-provider").build_plan(
    profile, config, host, ("qemu-system-x86_64",), "tcg"))
rejects(lambda: provider.build_plan(profile, config, host,
                                    ("qemu-system-x86_64", "bad\x00arg"), "tcg"))

print("Boot Provider contract tests passed (versioned models, architecture separation, argv, KVM gate, deterministic plan hash).")
