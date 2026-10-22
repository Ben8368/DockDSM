#!/usr/bin/env python3
"""Exercise read-only Surveillance Station readiness classification."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile

repo = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("surveillance_readiness", repo / "scripts/surveillance-readiness.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def fixture(platform="arm", **overrides):
    if platform == "x86":
        base = {
            "format": "1", "epoch": "1792569600", "guest_arch": "x86_64",
            "unique": "synology_kvmx64_virtualdsm", "dsm_version": "7.2.2",
            "dsm_build": "72806", "volume1": "btrfs:rw,relatime",
        }
    else:
        base = {
            "format": "1", "epoch": "1792569600", "guest_arch": "aarch64",
            "unique": "synology_rtd1619b_ds124", "dsm_version": "7.2.2",
            "dsm_build": "72806", "volume1": "btrfs:rw,relatime",
        }
    base.update({
        "volume1.collector_write_access": "yes", "volume1.free_bytes": "10737418240",
        "recording_share.present": "yes", "recording_share.collector_write_access": "yes",
        "service.postgresql": "active", "network.pkgupdate.curl": "0",
        "network.pkgupdate.http": "404", "network.download.curl": "0",
        "network.download.http": "403",
    })
    for name, arch in (("StorageManager", "armv8"), ("SurveillanceVideoExtension", "armv8"),
                       ("SurveillanceStation", "armv8")):
        if platform == "x86":
            arch = "x86_64"
        prefix = "package." + name + "."
        base.update({
            prefix + "info_present": "yes", prefix + "version": "1.0.0",
            prefix + "arch": arch, prefix + "os_min_ver": "7.0-40000",
            prefix + "os_max_ver": "", prefix + "synopkg_rc": "0",
            prefix + "synopkg_status": "running", prefix + "service": "active",
        })
    base.update(overrides)
    return base


now = 1792569600
arm = module.analyze(fixture(), now)
assert arm["platform"]["name"] == "rtd1619b"
assert arm["platform"]["package_arch"] == "armv8"
assert arm["platform"]["status"] == "PASS"
assert arm["packages"]["SurveillanceStation"]["architecture"]["status"] == "PASS"
assert arm["network"]["synology_package_catalog"]["status"] == "PASS"
assert arm["network"]["synology_package_catalog"]["http_status"] == 404
assert arm["authorization"]["status"] == "NOT TESTED"
assert arm["authorization"]["license_material_read"] is False
assert arm["end_to_end"]["status"] == "NOT TESTED"

x86 = module.analyze(fixture("x86"), now)
assert x86["platform"]["name"] == "virtualdsm"
assert x86["platform"]["package_arch"] == "x86_64"
assert x86["packages"]["SurveillanceStation"]["architecture"]["status"] == "PASS"

assert module.analyze(fixture(guest_arch="x86_64"), now)["platform"]["status"] == "FAIL"
assert module.analyze(fixture(dsm_build="72807"), now)["platform"]["status"] == "FAIL"
assert module.analyze(fixture(unique="unknown_model"), now)["platform"]["status"] == "FAIL"

missing_volume = module.analyze(fixture(volume1=""), now)
assert missing_volume["storage"]["volume1"]["status"] == "BLOCKED"
assert missing_volume["services"]["postgresql"]["status"] == "PASS"
readonly = module.analyze(fixture(volume1="btrfs:ro,relatime"), now)
assert readonly["storage"]["volume1"]["status"] == "FAIL"
assert module.analyze(fixture(**{"volume1.free_bytes": "0"}), now)["storage"]["volume1"]["status"] == "FAIL"

wrong_arch = module.analyze(fixture(**{"package.SurveillanceStation.arch": "x86_64"}), now)
assert wrong_arch["packages"]["SurveillanceStation"]["architecture"]["status"] == "FAIL"
old_dsm = module.analyze(fixture(**{"package.SurveillanceStation.os_min_ver": "7.3-90000"}), now)
assert old_dsm["packages"]["SurveillanceStation"]["dsm_version"]["status"] == "FAIL"

missing_sve = module.analyze(fixture(**{
    "package.SurveillanceVideoExtension.info_present": "no",
    "package.SurveillanceVideoExtension.synopkg_rc": "1",
    "package.SurveillanceVideoExtension.synopkg_status": "unavailable",
    "package.SurveillanceVideoExtension.service": "inactive",
}), now)
assert missing_sve["packages"]["SurveillanceVideoExtension"]["installation"]["status"] == "NOT TESTED"
assert missing_sve["packages"]["SurveillanceVideoExtension"]["service"]["status"] == "BLOCKED"
assert missing_sve["dependencies"]["status"] == "NOT TESTED"
stopped = module.analyze(fixture(**{"package.SurveillanceStation.service": "inactive"}), now)
assert stopped["packages"]["SurveillanceStation"]["service"]["status"] == "FAIL"
wrong_arch = module.analyze(fixture(**{"package.SurveillanceStation.arch": "x86_64"}), now)
assert "package_SurveillanceStation_architecture:fail" in wrong_arch["blockers"]
assert wrong_arch["prerequisites_status"] == "FAIL"
old_dsm = module.analyze(fixture(**{"package.SurveillanceStation.os_min_ver": "7.3-90000"}), now)
assert "package_SurveillanceStation_dsm_version:fail" in old_dsm["blockers"]
assert old_dsm["prerequisites_status"] == "FAIL"
unavailable_status = module.analyze(fixture(**{
    "package.SurveillanceStation.synopkg_rc": "127",
    "package.SurveillanceStation.synopkg_status": "unavailable",
}), now)
assert unavailable_status["packages"]["SurveillanceStation"]["installation"]["status"] == "NOT TESTED"

for code, cause in (("6", "dns"), ("7", "connection"), ("28", "timeout"),
                    ("35", "tls_handshake"), ("60", "certificate"), ("77", "ca_file")):
    report = module.analyze(fixture(**{"network.pkgupdate.curl": code}), now)
    assert report["network"]["synology_package_catalog"]["status"] == "FAIL"
    assert report["network"]["synology_package_catalog"]["cause"] == cause

untested_camera = arm["network"]["camera_rtsp"]
assert untested_camera["status"] == "NOT TESTED"
camera = module.analyze(fixture(**{"camera_rtsp.curl": "0", "camera_rtsp.response": "401"}), now)
assert camera["network"]["camera_rtsp"]["status"] == "PASS"
assert camera["network"]["camera_rtsp"]["response_code"] == 401
camera_failed = module.analyze(fixture(**{"camera_rtsp.curl": "28", "camera_rtsp.response": ""}), now)
assert camera_failed["network"]["camera_rtsp"]["cause"] == "timeout"

history = module.analyze(fixture(**{"history.synopkg.log.authorization": "yes"}), now)
assert history["authorization"]["status"] == "NOT TESTED"
assert history["logs"]["recent_categories"] == [{
    "category": "authorization", "source": "synopkg.log", "status": "NOT TESTED",
}]
assert not any("authorization" in item for item in history["blockers"])

assert module.parse("format\t1\nepoch\t1792569600\n")["epoch"] == "1792569600"
for bad in (
    "format\t2\n",
    "format\t1\nformat\t1\n",
    "format\t1\ninvalid key\tvalue\n",
    "format\t1\nfield\tbad\x00value\n",
    "x" * 65537,
):
    try:
        module.parse(bad)
    except ValueError:
        pass
    else:
        raise AssertionError("Invalid diagnostic report accepted")

cli_fixture = fixture(**{"camera_rtsp.curl": "0", "camera_rtsp.response": "401"})
cli_fixture["epoch"] = str(int(module.time.time()))
with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".tsv") as report_file:
    report_file.write("\n".join(key + "\t" + value for key, value in cli_fixture.items()) + "\n")
    report_file.flush()
    completed = subprocess.run(
        [sys.executable, str(repo / "scripts/surveillance-readiness.py"), "--from-report", report_file.name],
        capture_output=True,
        text=True,
        check=False,
    )
assert completed.returncode == 0, completed.stderr + completed.stdout
cli_report = json.loads(completed.stdout)
assert cli_report["network"]["camera_rtsp"]["status"] == "PASS"
assert cli_report["authorization"]["status"] == "NOT TESTED"
assert cli_report["end_to_end"]["status"] == "NOT TESTED"
assert "192.0.2." not in completed.stdout

print("Surveillance readiness tests passed (x86/ARM64, package arch/version, dependencies, storage, services, DNS/TLS, RTSP, license separation).")
