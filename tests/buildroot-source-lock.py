#!/usr/bin/env python3
"""Regression tests for architecture-neutral Buildroot/Linux input locking."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "research/buildroot"))

from check_inputs import resolve_output_path, validate  # noqa: E402
from source_tree import PROVENANCE_NAME, seal_source_tree  # noqa: E402


lock_path = ROOT / "research/buildroot/source-lock.json"
lock = json.loads(lock_path.read_text(encoding="utf-8"))
kernel = lock["kernel"]
expected_entry = f"sha256  {kernel['sha256']}  linux-{kernel['version']}.tar.xz"
fetch_script = (ROOT / "research/arm64/loader/fetch-buildroot.sh").read_text()
assert "source_tree.py" in fetch_script and "seal" in fetch_script
fetch_usage = subprocess.run(
    ["bash", str(ROOT / "research/arm64/loader/fetch-buildroot.sh")],
    capture_output=True, text=True)
assert fetch_usage.returncode == 2
assert f"buildroot-{lock['version']}" in fetch_usage.stderr

with tempfile.TemporaryDirectory(prefix="dockdsm-buildroot-lock-") as tmp:
    repository = Path(tmp) / "repo"
    repository.mkdir()
    outside = Path(tmp) / "outside"
    resolved_output = resolve_output_path(repository, outside / "build")
    assert resolved_output == (outside / "build").resolve()
    inside_output = repository / "not-created" / "build"
    try:
        resolve_output_path(repository, inside_output)
    except ValueError as error:
        assert "outside the repository" in str(error)
    else:
        raise AssertionError("repository-local output path was accepted")
    assert not inside_output.exists(), "preflight must not create rejected output paths"

    repository_alias = Path(tmp) / "repo-alias"
    repository_alias.symlink_to(repository, target_is_directory=True)
    alias_output = repository_alias / "symlink-output"
    try:
        resolve_output_path(repository, alias_output)
    except ValueError as error:
        assert "outside the repository" in str(error)
    else:
        raise AssertionError("symlinked repository-local output path was accepted")
    assert not (repository / "symlink-output").exists()

    try:
        resolve_output_path(repository, Path("/"))
    except ValueError as error:
        assert "filesystem root" in str(error)
    else:
        raise AssertionError("filesystem root was accepted as output")

    root = Path(tmp) / "buildroot"
    (root / "linux").mkdir(parents=True)
    (root / "package/linux-headers").mkdir(parents=True)
    (root / "Makefile").write_text(
        f"export BR2_VERSION := {lock['version']}\n", encoding="utf-8")
    for relative in ("linux/linux.hash", "package/linux-headers/linux-headers.hash"):
        (root / relative).write_text(expected_entry + "\n", encoding="utf-8")
    defconfig = Path(tmp) / "defconfig"
    defconfig.write_text(
        f'BR2_LINUX_KERNEL_CUSTOM_VERSION_VALUE="{kernel["version"]}"\n',
        encoding="utf-8")
    source_file = root / "README"
    source_file.write_text("locked source fixture\n", encoding="utf-8")
    try:
        seal_source_tree(root, lock["version"], "0" * 64, lock_path)
    except ValueError as error:
        assert "does not match the source lock" in str(error)
    else:
        raise AssertionError("unlocked Buildroot archive metadata was sealed")
    seal_source_tree(root, lock["version"], lock["sha256"], lock_path)

    assert validate(root, defconfig, lock_path) == (lock["version"], kernel["version"])
    source_file.write_text("modified source fixture\n", encoding="utf-8")
    try:
        validate(root, defconfig, lock_path)
    except ValueError as error:
        assert "source tree changed" in str(error)
    else:
        raise AssertionError("modified Buildroot source tree was accepted")
    source_file.write_text("locked source fixture\n", encoding="utf-8")
    (root / PROVENANCE_NAME).unlink()
    try:
        validate(root, defconfig, lock_path)
    except ValueError as error:
        assert "provenance marker" in str(error)
    else:
        raise AssertionError("unsealed Buildroot source tree was accepted")
    seal_source_tree(root, lock["version"], lock["sha256"], lock_path)

    resolved_config = Path(tmp) / ".config"
    resolved_config.write_text(
        "BR2_LINUX_KERNEL=y\n"
        "BR2_LINUX_KERNEL_CUSTOM_VERSION=y\n"
        f'BR2_LINUX_KERNEL_CUSTOM_VERSION_VALUE="{kernel["version"]}"\n',
        encoding="utf-8")
    assert validate(root, defconfig, lock_path, resolved_config) == (
        lock["version"], kernel["version"])
    resolved_config.write_text(
        "BR2_LINUX_KERNEL=y\n"
        "BR2_LINUX_KERNEL_CUSTOM_VERSION=y\n"
        f'BR2_LINUX_KERNEL_CUSTOM_VERSION_VALUE="{kernel["version"]}"\n'
        'BR2_LINUX_KERNEL_CUSTOM_VERSION_VALUE="0.0"\n',
        encoding="utf-8")
    try:
        validate(root, defconfig, lock_path, resolved_config)
    except ValueError as error:
        assert "duplicate" in str(error)
    else:
        raise AssertionError("duplicate resolved kernel versions were accepted")
    resolved_config.write_text(
        "BR2_LINUX_KERNEL=y\n"
        "BR2_LINUX_KERNEL_CUSTOM_VERSION=y\n"
        'BR2_LINUX_KERNEL_CUSTOM_VERSION_VALUE="0.0"\n',
        encoding="utf-8")
    try:
        validate(root, defconfig, lock_path, resolved_config)
    except ValueError as error:
        assert "resolved Buildroot .config" in str(error)
    else:
        raise AssertionError("resolved kernel version drift was accepted")

    bad_defconfig = Path(tmp) / "bad-defconfig"
    bad_defconfig.write_text('BR2_LINUX_KERNEL_CUSTOM_VERSION_VALUE="0.0"\n',
                             encoding="utf-8")
    try:
        validate(root, bad_defconfig, lock_path)
    except ValueError as error:
        assert "defconfig must select exactly one" in str(error)
    else:
        raise AssertionError("mismatched kernel version was accepted")

    duplicate_defconfig = Path(tmp) / "duplicate-defconfig"
    duplicate_defconfig.write_text(
        f'BR2_LINUX_KERNEL_CUSTOM_VERSION_VALUE="{kernel["version"]}"\n'
        'BR2_LINUX_KERNEL_CUSTOM_VERSION_VALUE="0.0"\n',
        encoding="utf-8")
    try:
        validate(root, duplicate_defconfig, lock_path)
    except ValueError as error:
        assert "exactly one" in str(error)
    else:
        raise AssertionError("duplicate defconfig kernel versions were accepted")

    (root / "linux/linux.hash").write_text("sha256  0  linux-wrong.tar.xz\n",
                                            encoding="utf-8")
    try:
        validate(root, defconfig, lock_path)
    except ValueError as error:
        assert "linux/linux.hash" in str(error)
    else:
        raise AssertionError("missing locked kernel hash was accepted")

    (root / "linux/linux.hash").write_text(expected_entry + "\n", encoding="utf-8")
    (root / "Makefile").write_text("export BR2_VERSION := 0.0\n", encoding="utf-8")
    try:
        validate(root, defconfig, lock_path)
    except ValueError as error:
        assert "Buildroot source tree" in str(error)
    else:
        raise AssertionError("mismatched Buildroot release was accepted")

print("Shared Buildroot source lock tests passed.")
