"""Exercise safe SPK inspection and target validation without a DSM guest."""
import argparse
from contextlib import redirect_stdout
import importlib.util
import io
import json
from pathlib import Path
import shlex
from unittest import mock
import tarfile
import tempfile

repo = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("surveillance_install", repo / "scripts/surveillance-install.py")
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)
readiness = installer.readiness_module()


def make_spk(path, info):
    data = info.encode("utf-8")
    with tarfile.open(path, "w") as archive:
        header = tarfile.TarInfo("INFO")
        header.size = len(data)
        archive.addfile(header, io.BytesIO(data))
    return path


arm = {
    "name": "rtd1619b", "platform_id": "rtd1619b", "package_arch": "armv8",
    "dsm_version": "7.2.2", "dsm_build": "72806",
}
x86 = {
    "name": "virtualdsm", "platform_id": "kvmx64", "package_arch": "x86_64",
    "dsm_version": "7.2.2", "dsm_build": "72806",
}

with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    arm_spk = make_spk(root / "arm.spk", 'package="SurveillanceStation"\nversion="9.2.0"\narch="armv8"\nos_min_ver="7.0-40000"\n')
    x86_spk = make_spk(root / "x86.spk", 'package="SurveillanceStation"\nversion="9.2.0"\narch="x86_64"\nos_min_ver="7.0-40000"\n')
    _, arm_info = installer.read_spk_info(arm_spk)
    _, x86_info = installer.read_spk_info(x86_spk)
    assert installer.validate_spk(arm_info, arm, readiness)["package"] == "SurveillanceStation"
    assert installer.validate_spk(x86_info, x86, readiness)["package"] == "SurveillanceStation"

    for info, target in (
        (arm_info, x86),
        ({**arm_info, "os_min_ver": "7.3-90000"}, arm),
        ({**arm_info, "os_max_ver": "7.2-70000"}, arm),
        ({**arm_info, "os_min_ver": "not-a-version"}, arm),
        ({**arm_info, "package": "UnknownPackage"}, arm),
    ):
        try:
            installer.validate_spk(info, target, readiness)
        except installer.InstallError:
            pass
        else:
            raise AssertionError("Incompatible SPK metadata was accepted")

    malformed = root / "wrong.spk"
    make_spk(malformed, 'package="OtherPackage"\narch="armv8"\n')
    try:
        installer.read_spk_info(malformed)
    except installer.InstallError:
        pass
    else:
        raise AssertionError("Non-Surveillance SPK was accepted")

    report_data = {"format": "1", "package.SurveillanceStation.info_present": "no"}
    preflight = {
        "platform": {**arm, "status": "PASS"}, "guest_clock": {"status": "PASS"},
        "storage": {"volume1": {"status": "PASS"}},
    }
    args = argparse.Namespace(
        guest="admin@127.0.0.1", port=5022, sve_spk=None, spk=arm_spk, apply=False,
    )
    output = io.StringIO()
    with mock.patch.object(installer, "collect_report", return_value=report_data), \
            mock.patch.object(readiness, "analyze", return_value=preflight), \
            mock.patch.object(installer, "run", side_effect=AssertionError("dry-run attempted SSH")), \
            redirect_stdout(output):
        assert installer.install(args, readiness) == 0
    assert json.loads(output.getvalue())["mode"] == "dry_run"

assert shlex.split(installer.remote_install_command("/tmp/package with space.spk")) == [
    "sudo", "-n", "/usr/syno/bin/synopkg", "install", "/tmp/package with space.spk",
]
for status in ("FAIL", "BLOCKED", "NOT TESTED"):
    try:
        installer.validate_preflight({
            "platform": {"status": "PASS"},
            "guest_clock": {"status": "PASS"},
            "storage": {"volume1": {"status": status}},
        })
    except installer.InstallError:
        pass
    else:
        raise AssertionError("Incomplete DSM preflight was accepted")

print("Surveillance installer tests passed (safe SPK metadata, platform/DSM matching, preflight, shell quoting).")
