#!/usr/bin/env python3
"""Read-only Surveillance Station readiness checks over existing SSH access."""
import argparse
import ipaddress
import json
from pathlib import Path
import re
import shlex
import subprocess
import time

COLLECTOR = Path(__file__).resolve().parents[1] / "src/guest/surveillance-diagnostics.sh"
PACKAGES = ("StorageManager", "SurveillanceVideoExtension", "SurveillanceStation")
STATES = {"PASS", "FAIL", "BLOCKED", "NOT TESTED"}
STATUS_INSTALLED = {"running", "run", "active", "stop", "stopped", "inactive"}


def parse(text):
    if len(text) > 65536:
        raise ValueError("Diagnostic report is oversized")
    result = {}
    for line in text.splitlines():
        key, separator, value = line.partition("\t")
        if not separator or not re.fullmatch(r"[A-Za-z0-9_.]+", key) or key in result:
            raise ValueError("Invalid or duplicate diagnostic field")
        if len(value) > 512 or any(ord(char) < 32 for char in value):
            raise ValueError("Invalid diagnostic value")
        result[key] = value
    if result.get("format") != "1":
        raise ValueError("Expected guest diagnostic format 1")
    return result


def flag(value):
    if value == "yes":
        return True
    if value == "no":
        return False
    return None


def check(status, **details):
    if status not in STATES:
        raise ValueError("Invalid check status")
    return {"status": status, **details}


def platform_info(data):
    unique = data.get("unique", "").lower()
    guest_arch = data.get("guest_arch", "")
    if "kvmx64" in unique:
        name, platform, package_arch, expected_arch = "virtualdsm", "kvmx64", "x86_64", "x86_64"
    elif unique == "synology_rtd1619b_ds124":
        name, platform, package_arch, expected_arch = "rtd1619b", "rtd1619b", "armv8", "aarch64"
    else:
        name, platform, package_arch, expected_arch = "unknown", "unknown", "unknown", ""
    arch_ok = guest_arch == expected_arch or (expected_arch == "aarch64" and guest_arch == "arm64")
    status = "FAIL" if name == "unknown" or not arch_ok else "PASS"
    dsm_version, dsm_build = data.get("dsm_version", ""), data.get("dsm_build", "")
    if name == "rtd1619b" and (dsm_version, dsm_build) != ("7.2.2", "72806"):
        status = "FAIL"
    return {
        "name": name,
        "platform_id": platform,
        "guest_arch": guest_arch or None,
        "package_arch": package_arch,
        "dsm_version": dsm_version or None,
        "dsm_build": dsm_build or None,
        "status": status,
    }


def parse_dsm_release(value, build="0"):
    match = re.fullmatch(r"(\d+)\.(\d+)(?:\.(\d+))?(?:-(\d+))?", value or "")
    if not match:
        return None
    parts = tuple(int(part or 0) for part in match.groups()[:3])
    release_build = int(match.group(4) or build or 0)
    return (*parts, release_build)


def package_info(data, name, platform, required=False):
    prefix = "package." + name + "."
    status_text = data.get(prefix + "synopkg_status", "unavailable").lower()
    command_rc = data.get(prefix + "synopkg_rc", "")
    info_present = flag(data.get(prefix + "info_present", ""))
    official_status = command_rc == "0" and status_text in STATUS_INSTALLED
    installed = official_status or info_present is True
    if official_status:
        installation = check("PASS", source="synopkg status", state=status_text)
    elif info_present is True:
        installation = check("NOT TESTED", source="package INFO", state="present; synopkg status unavailable")
    elif command_rc not in ("0", "1", "2"):
        installation = check("NOT TESTED", source="synopkg status", state="unavailable")
    elif not required:
        installation = check(
            "NOT TESTED",
            source="synopkg status",
            state="not installed",
            note="Whether this package is required depends on the official Surveillance Station package and DSM version.",
        )
    else:
        installation = check("BLOCKED", source="synopkg status", state="not installed or status unavailable")

    service_state = data.get(prefix + "service", "unknown").lower()
    if service_state == "active":
        service = check("PASS", state=service_state)
    elif installed:
        service = check("FAIL", state=service_state or "unknown")
    else:
        service = check("BLOCKED", state=service_state or "unknown", reason="package not confirmed installed")

    architecture = check("NOT TESTED", supported_architectures=None)
    arch_value = data.get(prefix + "arch", "")
    if arch_value:
        supported = set(arch_value.lower().split())
        allowed = {platform["package_arch"], platform["platform_id"], "noarch"} - {"unknown"}
        matches = bool(supported & allowed)
        architecture = check(
            "PASS" if matches else "FAIL",
            supported_architectures=sorted(supported),
            running_package_arch=platform["package_arch"],
        )

    dsm_compatibility = check("NOT TESTED", minimum=None, maximum=None)
    current = parse_dsm_release(platform.get("dsm_version") or "", platform.get("dsm_build") or "0")
    minimum_text = data.get(prefix + "os_min_ver", "")
    maximum_text = data.get(prefix + "os_max_ver", "")
    minimum = parse_dsm_release(minimum_text)
    maximum = parse_dsm_release(maximum_text)
    if current and (minimum_text or maximum_text):
        compatible = (minimum is None or current >= minimum) and (maximum is None or current <= maximum)
        dsm_compatibility = check(
            "PASS" if compatible else "FAIL",
            minimum=minimum_text or None,
            maximum=maximum_text or None,
        )

    return {
        "installation": installation,
        "service": service,
        "architecture": architecture,
        "dsm_version": dsm_compatibility,
        "version": data.get(prefix + "version") or None,
        "installed": installed,
    }


def transport_check(data, endpoint):
    prefix = "network." + endpoint + "."
    rc = data.get(prefix + "curl")
    response = data.get(prefix + "http", "")
    if rc is None:
        return check("NOT TESTED", reason="run with --network")
    if rc == "0" and re.fullmatch(r"[1-5]\d\d", response):
        return check("PASS", transport="reachable", http_status=int(response))
    cause = {
        "6": "dns",
        "7": "connection",
        "28": "timeout",
        "35": "tls_handshake",
        "60": "certificate",
        "77": "ca_file",
    }.get(rc, "curl_" + rc)
    return check("FAIL", transport="unavailable", cause=cause)


def camera_check(data):
    rc = data.get("camera_rtsp.curl")
    response = data.get("camera_rtsp.response", "")
    if rc is None:
        return check("NOT TESTED", reason="supply --camera-ip to test one manual target")
    if rc == "0" and re.fullmatch(r"[1-5]\d\d", response):
        return check(
            "PASS",
            transport="rtsp_server_responded",
            response_code=int(response),
            note="A response proves the DSM-initiated RTSP path only; it does not prove credentials or video decode.",
        )
    if rc == "unavailable":
        return check("NOT TESTED", reason="curl is unavailable in the guest")
    cause = {
        "6": "dns",
        "7": "connection",
        "28": "timeout",
        "35": "tls_handshake",
        "60": "certificate",
    }.get(rc, "rtsp_probe_" + (rc or "unknown"))
    return check("FAIL", transport="no_rtsp_response", cause=cause)


def analyze(data, host_epoch):
    try:
        guest_epoch = int(data["epoch"])
    except (KeyError, ValueError):
        clock = check("NOT TESTED", reason="guest UTC epoch unavailable")
    else:
        skew = guest_epoch - int(host_epoch)
        clock = check("PASS" if abs(skew) <= 300 else "FAIL", skew_seconds=skew)

    platform = platform_info(data)
    volume = data.get("volume1", "")
    if not volume:
        volume_check = check("BLOCKED", reason="no mounted /volume1")
    else:
        filesystem, _, options = volume.partition(":")
        mount_options = set(options.split(","))
        if "ro" in mount_options:
            volume_check = check("FAIL", mounted=True, filesystem=filesystem, writable_mount=False)
        elif "rw" not in mount_options:
            volume_check = check("NOT TESTED", mounted=True, filesystem=filesystem, writable_mount=None)
        else:
            volume_check = check("PASS", mounted=True, filesystem=filesystem, writable_mount=True)
    collector_access = flag(data.get("volume1.collector_write_access", ""))
    if volume_check["status"] == "PASS" and collector_access is False:
        volume_check = check(
            "PASS",
            mounted=True,
            filesystem=volume.partition(":")[0],
            writable_mount=True,
            collector_write_access=False,
            note="Collector account access differs from the mounted filesystem mode; package-user ACL is not inspected.",
        )
    try:
        free_bytes = int(data["volume1.free_bytes"])
    except (KeyError, ValueError):
        free_bytes = None
    if free_bytes == 0 and volume_check["status"] == "PASS":
        volume_check = check("FAIL", mounted=True, writable_mount=True, free_bytes=0)
    elif volume_check["status"] == "PASS":
        volume_check["free_bytes"] = free_bytes

    packages = {
        name: package_info(data, name, platform, required=(name == "SurveillanceStation"))
        for name in PACKAGES
    }
    pgsql_state = data.get("service.postgresql", "unknown").lower()
    if pgsql_state == "active":
        postgresql = check("PASS", state=pgsql_state)
    else:
        postgresql = check(
            "NOT TESTED",
            state=pgsql_state or "unknown",
            reason="The required database service varies by DSM and official package version; verify Package Center dependencies and service logs.",
        )

    share_present = flag(data.get("recording_share.present", ""))
    share_access = flag(data.get("recording_share.collector_write_access", ""))
    if share_present is True:
        recording_share = check(
            "PASS",
            present=True,
            collector_write_access=share_access,
            note="Package service-user permission and actual recording writes require the end-to-end procedure.",
        )
    elif packages["SurveillanceStation"]["installed"]:
        recording_share = check("FAIL", present=False, reason="default recording share is absent")
    elif volume_check["status"] == "BLOCKED":
        recording_share = check("BLOCKED", present=False, reason="package and writable data volume are prerequisites")
    else:
        recording_share = check("BLOCKED", present=False, reason="Surveillance Station has not created its recording share")

    sve = packages["SurveillanceVideoExtension"]["installation"]
    if sve["status"] == "BLOCKED":
        sve = check("BLOCKED", state=sve["state"], reason="install through Package Center when required by the official package")

    network = {
        "synology_package_catalog": transport_check(data, "pkgupdate"),
        "synology_download": transport_check(data, "download"),
        "camera_rtsp": camera_check(data),
    }

    history_categories = (
        "authorization", "dependency", "architecture", "network", "tls",
        "filesystem", "service_start", "install_failure",
    )
    history = []
    for filename in ("synopkg.log", "synopkgmgr.log", "SurveillanceStation.log"):
        for category in history_categories:
            if data.get("history." + filename + "." + category) == "yes":
                history.append({"category": category, "source": filename, "status": "NOT TESTED"})
    log_access = {
        filename: ("PASS" if data.get("logs." + filename) == "readable" else "NOT TESTED")
        for filename in ("synopkg.log", "synopkgmgr.log", "SurveillanceStation.log")
    }

    blockers = []
    for name, item in (("platform", platform), ("guest_clock", clock), ("volume1", volume_check),
                       ("postgresql", postgresql)):
        if item["status"] in ("FAIL", "BLOCKED"):
            blockers.append(name + ":" + item["status"].lower())
    for name, item in packages.items():
        if item["installation"]["status"] in ("FAIL", "BLOCKED"):
            blockers.append("package_" + name + ":" + item["installation"]["status"].lower())
        for dimension in ("architecture", "dsm_version"):
            if item[dimension]["status"] == "FAIL":
                blockers.append("package_" + name + "_" + dimension + ":fail")
    if packages["SurveillanceStation"]["installation"]["status"] == "PASS":
        if packages["SurveillanceStation"]["service"]["status"] in ("FAIL", "BLOCKED"):
            blockers.append("surveillance_service:" + packages["SurveillanceStation"]["service"]["status"].lower())
    if recording_share["status"] == "FAIL":
        blockers.append("recording_share:fail")
    if any(item["status"] == "FAIL" for item in network.values()):
        blockers.append("network_probe:fail")

    prerequisite_status = "PASS"
    if any(value.endswith(":fail") for value in blockers):
        prerequisite_status = "FAIL"
    elif blockers:
        prerequisite_status = "BLOCKED"
    elif any(item["status"] == "NOT TESTED" for item in network.values()):
        prerequisite_status = "NOT TESTED"

    return {
        "schema_version": 1,
        "platform": platform,
        "guest_clock": clock,
        "storage": {
            "volume1": volume_check,
            "recording_share": recording_share,
        },
        "services": {"postgresql": postgresql},
        "dependencies": {
            "status": "NOT TESTED",
            "observed_packages": {
                name: item["installation"]["status"]
                for name, item in packages.items()
            },
            "note": "Package requirements are version-specific; confirm them through DSM Package Center and the official package's dependency result.",
        },
        "packages": packages,
        "network": network,
        "logs": {"readability": log_access, "recent_categories": history},
        "authorization": {
            "status": "NOT TESTED",
            "license_material_read": False,
            "note": "Use Surveillance Station's official License page; this tool never reads license keys or tries to validate or alter licenses.",
        },
        "end_to_end": {
            "status": "NOT TESTED",
            "checks": {
                "camera_preview": "NOT TESTED",
                "recording_and_playback": "NOT TESTED",
                "motion_events": "NOT TESTED",
                "restart_persistence": "NOT TESTED",
                "licensed_recording": "NOT TESTED",
            },
            "note": "A readiness report is not evidence of live video, recording, playback, motion events, license validity, or persistence.",
        },
        "prerequisites_status": prerequisite_status,
        "blockers": blockers,
    }


def target_command(args):
    command_args = []
    if args.network:
        command_args.append("--network")
    if args.camera_ip:
        command_args.extend(("--camera-ip", ipaddress.ip_address(args.camera_ip).compressed))
        command_args.extend(("--rtsp-port", str(args.rtsp_port)))
    remote = ("sudo -n " if args.sudo else "") + "/bin/sh -s --"
    if command_args:
        remote += " " + " ".join(shlex.quote(item) for item in command_args)
    return remote


def collect(args):
    if not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.-]*@[A-Za-z0-9][A-Za-z0-9.:-]*", args.guest):
        raise ValueError("Expected SSH target user@host")
    try:
        completed = subprocess.run(
            ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", "-p", str(args.port),
             args.guest, target_command(args)],
            input=COLLECTOR.read_text(encoding="utf-8"),
            text=True,
            capture_output=True,
            timeout=60,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError("SSH collector unavailable (" + type(exc).__name__ + "); no guest changes performed") from None
    if completed.returncode:
        raise RuntimeError("SSH collector failed; check existing SSH access and sudo permissions")
    return completed.stdout


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--guest", help="Existing SSH target user@host; no credentials are stored")
    source.add_argument("--from-report", type=Path, help="TSV output from surveillance-diagnostics.sh")
    parser.add_argument("--port", type=int, default=22)
    parser.add_argument("--sudo", action="store_true", help="Use cached/noninteractive sudo in DSM")
    parser.add_argument("--network", action="store_true", help="Probe Synology HTTPS transport from inside DSM")
    parser.add_argument("--camera-ip", help="One numeric camera IP to probe RTSP over TCP without credentials")
    parser.add_argument("--rtsp-port", type=int, default=554)
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("SSH port must be 1-65535")
    if not 1 <= args.rtsp_port <= 65535:
        parser.error("RTSP port must be 1-65535")
    if args.camera_ip:
        try:
            ipaddress.ip_address(args.camera_ip)
        except ValueError:
            parser.error("--camera-ip must be a numeric IPv4 or IPv6 address")
        if not args.guest:
            parser.error("--camera-ip requires --guest because it performs a live read-only probe")
    elif args.rtsp_port != 554:
        parser.error("--rtsp-port requires --camera-ip")
    try:
        if args.guest:
            raw = collect(args)
        else:
            if args.network or args.camera_ip:
                parser.error("live probes require --guest")
            raw = args.from_report.read_text(encoding="utf-8")
        report = analyze(parse(raw), int(time.time()))
    except (OSError, UnicodeError, ValueError, RuntimeError) as exc:
        parser.exit(2, str(exc) + "\n")
    print(json.dumps(report, indent=2, sort_keys=True))
    return {"PASS": 0, "FAIL": 2, "BLOCKED": 2, "NOT TESTED": 3}[report["prerequisites_status"]]


if __name__ == "__main__":
    raise SystemExit(main())
