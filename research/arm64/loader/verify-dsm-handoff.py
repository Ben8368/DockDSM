#!/usr/bin/env python3
"""Verify the bounded, diskless DS124 kernel/initrd kexec experiment."""
from pathlib import Path
import re
import sys


MARKERS = (
    "Linux version 5.10.55+",
    "Trying to unpack rootfs image as initramfs...",
    "Freeing initrd memory:",
    "Exit on error [1] DISK NOT INSTALLED",
    ":: Starting /etc/rc",
    "SynologyNAS login:",
)
FAILURES = re.compile(
    r"\b(?:Kernel panic\b|Oops:|BUG:|undefined instruction\b|Synchronous Abort\b|"
    r"SError Interrupt\b|soft lockup\b)",
    re.IGNORECASE,
)


def verify(log: str) -> None:
    missing = [marker for marker in MARKERS if marker not in log]
    if missing:
        raise ValueError("missing DSM kexec handoff evidence: " + ", ".join(missing))
    failure = FAILURES.search(log)
    if failure:
        raise ValueError(f"failure signature in DSM kexec serial log: {failure.group(0)}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: verify-dsm-handoff.py SERIAL_LOG")
    try:
        verify(Path(sys.argv[1]).read_text(errors="replace"))
    except (OSError, ValueError) as error:
        print(f"DS124 kexec handoff failed: {error}", file=sys.stderr)
        raise SystemExit(1)
    print("DS124 kernel/initrd kexec reached the diskless login prompt; no disk or DSM lifecycle tested.")
