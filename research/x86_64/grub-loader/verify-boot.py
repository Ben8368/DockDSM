#!/usr/bin/env python3
"""Validate an x86_64 GRUB-to-Linux serial transcript."""
import re
from pathlib import Path
import sys


MARKER = "DOCKDSM_X86_GRUB_LINUX_BOOTED"
FAILURES = (
    re.compile(r"kernel panic", re.IGNORECASE),
    re.compile(r"\bBUG:", re.IGNORECASE),
    re.compile(r"\bOops:", re.IGNORECASE),
    re.compile(r"internal error", re.IGNORECASE),
    re.compile(r"not syncing", re.IGNORECASE),
    re.compile(r"call trace:", re.IGNORECASE),
    re.compile(r"general protection fault", re.IGNORECASE),
    re.compile(r"double fault", re.IGNORECASE),
)


def verify(transcript: str) -> None:
    normalized = transcript.replace("\r", "")
    if sum(line == MARKER for line in normalized.splitlines()) != 1:
        raise ValueError("expected exactly one standalone x86_64 Linux boot marker")
    if not any(line in ("reboot: Power down", "reboot: Power Off")
               for line in normalized.splitlines()):
        raise ValueError("Linux boot marker was not followed by a guest poweroff")
    if any(pattern.search(normalized) for pattern in FAILURES):
        raise ValueError("kernel failure signature found in QEMU serial output")


def main() -> int:
    if len(sys.argv) != 2:
        print(f"Usage: {Path(sys.argv[0]).name} QEMU_LOG", file=sys.stderr)
        return 2
    try:
        transcript = Path(sys.argv[1]).read_text(encoding="utf-8", errors="replace")
        verify(transcript)
    except (OSError, ValueError) as error:
        print(f"x86_64 GRUB boot verification failed: {error}", file=sys.stderr)
        return 1
    print("GRUB-to-open-Linux serial marker verified (DSM and kexec handoff not tested).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
