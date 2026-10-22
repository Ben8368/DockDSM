#!/usr/bin/env python3
"""Install user-provided Synology Surveillance Station SPKs through synopkg."""
import argparse
import importlib.util
import json
from pathlib import Path
import re
import secrets
import shlex
import subprocess
import sys
import tarfile
import time

ROOT = Path(__file__).resolve().parents[1]
READINESS_PATH = ROOT / "scripts/surveillance-readiness.py"
MAX_INFO_BYTES = 65536
MAX_SPK_BYTES = 2 * 1024 * 1024 * 1024
PACKAGE_IDS = {"SurveillanceVideoExtension", "SurveillanceStation"}


class InstallError(RuntimeError):
    """A safe-to-report install or preflight error."""


def readiness_module():
    spec = importlib.util.spec_from_file_location("surveillance_readiness", READINESS_PATH)
    if spec is None or spec.loader is None:
        raise InstallError("Surveillance readiness module is unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def read_spk_info(path):
    path = Path(path).resolve(strict=True)
    if not path.is_file() or not 1 <= path.stat().st_size <= MAX_SPK_BYTES:
        raise InstallError("SPK must be a regular file no larger than 2 GiB")
    try:
        with tarfile.open(path, mode="r:*") as package:
            matches = [member for member in package if member.name.removeprefix("./") == "INFO"]
            if len(matches) != 1 or not matches[0].isfile() or matches[0].size > MAX_INFO_BYTES:
                raise InstallError("SPK must contain exactly one small top-level INFO file")
            stream = package.extractfile(matches[0])
            if stream is None:
                raise InstallError("SPK INFO cannot be read")
            text = stream.read(MAX_INFO_BYTES + 1).decode("utf-8")
    except (tarfile.TarError, OSError, UnicodeError) as exc:
        raise InstallError("SPK archive or INFO is invalid (" + type(exc).__name__ + ")") from None
    if len(text.encode("utf-8")) > MAX_INFO_BYTES:
        raise InstallError("SPK INFO is oversized")

    info = {}
    for line in text.splitlines():
        key, separator, value = line.partition("=")
        if not separator:
            continue
        key, value = key.strip(), value.strip()
        if not re.fullmatch(r"[A-Za-z0-9_]+", key) or key in info:
            raise InstallError("SPK INFO contains an invalid or duplicate field")
        if value.startswith('"') and value.endswith('"') and len(value) >= 2:
            value = value[1:-1]
        info[key] = value
    if info.get("package") not in PACKAGE_IDS:
        raise InstallError("SPK package must be SurveillanceStation or SurveillanceVideoExtension")
    return path, info


def validate_spk(info, platform, readiness):
    if info.get("package") not in PACKAGE_IDS:
        raise InstallError("SPK package must be SurveillanceStation or SurveillanceVideoExtension")
    architectures = set(re.split(r"[\s,]+", info.get("arch", "").lower())) - {""}
    allowed = {platform["package_arch"], platform["platform_id"], "noarch"} - {"unknown"}
    if not architectures or not architectures.intersection(allowed):
        raise InstallError("SPK architecture does not match the DSM guest")

    current = readiness.parse_dsm_release(platform.get("dsm_version") or "",
                                          platform.get("dsm_build") or "0")
    minimum_text, maximum_text = info.get("os_min_ver", ""), info.get("os_max_ver", "")
    minimum = readiness.parse_dsm_release(minimum_text) if minimum_text else None
    maximum = readiness.parse_dsm_release(maximum_text) if maximum_text else None
    if not current:
        raise InstallError("DSM version/build could not be identified")
    if (minimum_text and minimum is None) or (maximum_text and maximum is None):
        raise InstallError("SPK DSM version bounds are invalid")
    if minimum is not None and current < minimum:
        raise InstallError("SPK requires a newer DSM version")
    if maximum is not None and current > maximum:
        raise InstallError("SPK does not support this DSM version")
    return {
        "package": info["package"],
        "version": info.get("version") or None,
        "architectures": sorted(architectures),
        "dsm_minimum": info.get("os_min_ver") or None,
        "dsm_maximum": info.get("os_max_ver") or None,
    }


def validate_preflight(report):
    checks = {
        "platform": report["platform"]["status"],
        "guest_clock": report["guest_clock"]["status"],
        "volume1": report["storage"]["volume1"]["status"],
    }
    blocked = [name for name, status in checks.items() if status != "PASS"]
    if blocked:
        raise InstallError("DSM installation preflight did not pass: " + ", ".join(blocked))


def remote_install_command(path):
    return "sudo -n /usr/syno/bin/synopkg install " + shlex.quote(path)


def run(command, input_text=None, timeout=120):
    try:
        result = subprocess.run(command, input=input_text, text=True, capture_output=True,
                                timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise InstallError("SSH operation unavailable (" + type(exc).__name__ + ")") from None
    if result.returncode:
        raise InstallError("SSH operation failed (exit " + str(result.returncode) + ")")
    return result.stdout


def ssh_prefix(args):
    return ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", "-p", str(args.port)]


def scp_prefix(args):
    return ["scp", "-B", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", "-P", str(args.port)]


def collect_report(args, readiness):
    ns = argparse.Namespace(
        guest=args.guest, port=args.port, sudo=True, network=False,
        camera_ip=None, rtsp_port=554,
    )
    try:
        raw = readiness.collect(ns)
    except RuntimeError as exc:
        raise InstallError(str(exc)) from None
    return readiness.parse(raw)


def install(args, readiness):
    report_data = collect_report(args, readiness)
    report = readiness.analyze(report_data, int(time.time()))
    validate_preflight(report)

    packages = []
    for path in (args.sve_spk, args.spk):
        if path is None:
            continue
        resolved, info = read_spk_info(path)
        details = validate_spk(info, report["platform"], readiness)
        if report_data.get("package." + details["package"] + ".info_present") == "yes":
            raise InstallError(details["package"] + " is already installed; use DSM Package Center for updates")
        packages.append((resolved, details))
    if not packages or packages[-1][1]["package"] != "SurveillanceStation":
        raise InstallError("A SurveillanceStation SPK is required and must be installed last")
    if args.sve_spk and packages[0][1]["package"] != "SurveillanceVideoExtension":
        raise InstallError("--sve-spk must identify a SurveillanceVideoExtension package")

    summaries = [{**details, "file": path.name} for path, details in packages]
    if not args.apply:
        print(json.dumps({
            "mode": "dry_run",
            "platform": report["platform"],
            "preflight": {"platform": "PASS", "guest_clock": "PASS", "volume1": "PASS"},
            "packages": summaries,
            "authorization": "not read or modified; verify in DSM's official License page",
            "next_step": "review the package metadata, then rerun with --apply",
        }, indent=2, sort_keys=True))
        return 0

    uploaded = []
    token = secrets.token_hex(8)
    try:
        for index, (path, _) in enumerate(packages):
            remote_path = "/tmp/vdsm-surveillance-" + token + "-" + str(index) + ".spk"
            destination = args.guest + ":" + remote_path
            uploaded.append(remote_path)
            run([*scp_prefix(args), "--", str(path), destination], timeout=1800)
            run([*ssh_prefix(args), args.guest, remote_install_command(remote_path)], timeout=1800)
    finally:
        if uploaded:
            cleanup = "rm -f -- " + " ".join(shlex.quote(path) for path in uploaded)
            try:
                subprocess.run([*ssh_prefix(args), args.guest, cleanup], capture_output=True,
                               text=True, timeout=30, check=False)
            except (OSError, subprocess.TimeoutExpired):
                pass

    post_report = None
    try:
        post_data = collect_report(args, readiness)
        post_report = readiness.analyze(post_data, int(time.time()))
    except (OSError, RuntimeError, ValueError, InstallError):
        print("Package install command completed; post-install diagnostics were unavailable.", file=sys.stderr)
    print(json.dumps({
        "mode": "installed",
        "packages": summaries,
        "package_manager": "DSM synopkg; vendor package checks remain enabled",
        "authorization": "not read or modified; verify in DSM's official License page",
        "readiness": post_report,
    }, indent=2, sort_keys=True))
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--guest", required=True, help="Existing SSH target user@host")
    parser.add_argument("--port", type=int, default=22, help="Existing SSH port")
    parser.add_argument("--spk", type=Path, required=True, help="Official SurveillanceStation SPK")
    parser.add_argument("--sve-spk", type=Path, help="Optional official Surveillance Video Extension SPK")
    parser.add_argument("--apply", action="store_true", help="Upload and install using noninteractive sudo")
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.-]*@[A-Za-z0-9][A-Za-z0-9.:-]*", args.guest):
        parser.error("--guest must be an SSH target user@host")
    if not 1 <= args.port <= 65535:
        parser.error("--port must be 1-65535")
    try:
        return install(args, readiness_module())
    except (OSError, ValueError, InstallError) as exc:
        parser.exit(2, str(exc) + "\n")


if __name__ == "__main__":
    raise SystemExit(main())
