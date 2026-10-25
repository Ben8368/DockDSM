#!/usr/bin/env python3
"""Require serial evidence for both sides of a real in-guest kexec handoff."""
from pathlib import Path
import sys


MARKERS = (
    "DOCKDSM_KEXEC_LOADER_READY",
    "DOCKDSM_KEXEC_IMAGE_LOADED",
    "DOCKDSM_KEXEC_TARGET_BOOTED",
)
FAILURES = (
    "DOCKDSM_KEXEC_LOADER_ERROR_",
    "DOCKDSM_KEXEC_EXEC_RETURNED",
    "DOCKDSM_KEXEC_TARGET_POWEROFF_RETURNED",
    "Kernel panic",
    "Oops:",
    "BUG:",
    "Unable to handle kernel",
    "Internal error:",
    "Synchronous Abort",
    "SError Interrupt",
)


def verify(log: str) -> None:
    lines = [line.rstrip("\r") for line in log.splitlines()]
    positions = []
    for marker in MARKERS:
        if lines.count(marker) != 1:
            raise ValueError(f"expected exactly one serial marker: {marker}")
        positions.append(lines.index(marker))
    if positions != sorted(positions):
        raise ValueError("loader/kernel handoff markers are out of order")
    for failure in FAILURES:
        if failure in log:
            raise ValueError(f"failure signature in serial log: {failure}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: verify-handoff.py SERIAL_LOG")
    try:
        verify(Path(sys.argv[1]).read_text(errors="replace"))
    except (OSError, ValueError) as error:
        print(f"ARM64 kexec handoff failed: {error}", file=sys.stderr)
        raise SystemExit(1)
    print("ARM64 Loader -> Linux kernel kexec handoff markers verified.")
