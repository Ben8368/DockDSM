#!/usr/bin/env python3
"""Verify GRUB boot and the established ARM64 kexec handoff markers."""
from pathlib import Path
import importlib.util
import sys

ROOT = Path(__file__).resolve().parents[3]
VERIFY_SCRIPT = ROOT / "research/arm64/loader/verify-handoff.py"
SPEC = importlib.util.spec_from_file_location("arm64_kexec_verify", VERIFY_SCRIPT)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("could not load ARM64 kexec handoff verifier")
VERIFY_MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VERIFY_MODULE)
MARKERS = VERIFY_MODULE.MARKERS
verify = VERIFY_MODULE.verify

GRUB_MARKER = "DOCKDSM_ARM64_GRUB_ENTRY"


def verify_grub(text: str) -> None:
    verify(text)
    lines = [line.rstrip("\r") for line in text.splitlines()]
    if lines.count(GRUB_MARKER) != 1:
        raise ValueError(f"expected exactly one GRUB marker: {GRUB_MARKER}")
    if lines.index(GRUB_MARKER) > lines.index(MARKERS[0]):
        raise ValueError("GRUB marker must precede the ARM64 loader marker")
    if "reboot: Power down" not in text:
        raise ValueError("target Linux did not report a guest poweroff")


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: verify-grub.py SERIAL_LOG")
    try:
        verify_grub(Path(sys.argv[1]).read_text(errors="replace"))
    except (OSError, ValueError) as error:
        print(f"ARM64 GRUB handoff failed: {error}", file=sys.stderr)
        return 1
    print("ARM64 UEFI -> GRUB -> Linux loader -> kexec handoff markers verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
