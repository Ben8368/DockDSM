#!/usr/bin/env python3
"""Validate a Buildroot tree and defconfig against the shared source lock."""
import argparse
import json
from pathlib import Path

from source_tree import verify_source_tree


LOCK = Path(__file__).with_name("source-lock.json")


def _config_assignments(lines: list[str], symbol: str) -> list[str]:
    unset = f"# {symbol} is not set"
    return [line for line in lines if line.startswith(f"{symbol}=") or line == unset]


def resolve_output_path(repo_root: Path, output: Path) -> Path:
    root = repo_root.resolve(strict=True)
    try:
        candidate = output.expanduser().resolve(strict=False)
    except (OSError, RuntimeError) as error:
        raise ValueError("OUTPUT_DIR cannot be resolved safely") from error
    if candidate == Path(candidate.anchor):
        raise ValueError("OUTPUT_DIR cannot be a filesystem root")
    try:
        candidate.relative_to(root)
    except ValueError:
        return candidate
    raise ValueError("OUTPUT_DIR must be outside the repository")


def validate(buildroot: Path, defconfig: Path, lock_path: Path = LOCK,
             resolved_config: Path | None = None) -> tuple[str, str]:
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    root = buildroot.resolve(strict=True)
    makefile = (root / "Makefile").read_text(encoding="utf-8").splitlines()
    expected_buildroot = f"export BR2_VERSION := {lock['version']}"
    if expected_buildroot not in makefile:
        raise ValueError("Buildroot source tree does not match the locked release")

    kernel = lock["kernel"]
    expected_entry = f"sha256  {kernel['sha256']}  linux-{kernel['version']}.tar.xz"
    for relative in ("linux/linux.hash", "package/linux-headers/linux-headers.hash"):
        entries = (root / relative).read_text(encoding="utf-8").splitlines()
        if expected_entry not in entries:
            raise ValueError(f"locked Linux hash entry is missing from {relative}")
    verify_source_tree(root, lock_path)

    config_lines = defconfig.read_text(encoding="utf-8").splitlines()
    expected_kernel = f"BR2_LINUX_KERNEL_CUSTOM_VERSION_VALUE=\"{kernel['version']}\""
    if _config_assignments(config_lines, "BR2_LINUX_KERNEL_CUSTOM_VERSION_VALUE") != [expected_kernel]:
        raise ValueError(
            "defconfig must select exactly one Linux kernel version matching the shared source lock")
    if resolved_config is not None:
        resolved_lines = resolved_config.read_text(encoding="utf-8").splitlines()
        required = (
            "BR2_LINUX_KERNEL=y",
            "BR2_LINUX_KERNEL_CUSTOM_VERSION=y",
            expected_kernel,
        )
        mismatches = [line for line in required
                      if _config_assignments(resolved_lines, line.partition("=")[0]) != [line]]
        if mismatches:
            raise ValueError(
                "resolved Buildroot .config has missing, duplicate, or mismatched locked settings: "
                + ", ".join(mismatches))
    return lock["version"], kernel["version"]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--buildroot", type=Path)
    parser.add_argument("--defconfig", type=Path)
    parser.add_argument("--config", type=Path,
                        help="resolved Buildroot .config to check against the Linux source lock")
    parser.add_argument("--check-output", type=Path)
    parser.add_argument("--repo-root", type=Path)
    args = parser.parse_args()
    if args.check_output is not None:
        if (args.repo_root is None or args.buildroot is not None or args.defconfig is not None
                or args.config is not None):
            parser.error("--check-output requires --repo-root and cannot be combined with build inputs")
        try:
            output = resolve_output_path(args.repo_root, args.check_output)
        except (OSError, ValueError) as error:
            parser.error(str(error))
        print(output)
        return 0
    if args.buildroot is None or args.defconfig is None or args.repo_root is not None:
        parser.error("--buildroot and --defconfig are required for input validation")
    try:
        buildroot_version, kernel_version = validate(
            args.buildroot, args.defconfig, resolved_config=args.config)
    except (OSError, KeyError, json.JSONDecodeError, ValueError) as error:
        parser.error(str(error))
    print(f"Validated Buildroot {buildroot_version} and Linux {kernel_version} inputs.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
