#!/usr/bin/env python3
"""Verify bounded stock DS124 initrd startup with an isolated blank SATA disk."""
from pathlib import Path
import re
import sys


REQUIRED = (
    "Linux version 5.10.55+",
    "#72806 SMP",
    "Trying to unpack rootfs image as initramfs...",
    "Freeing initrd memory:",
    "rtk_ahci b100000.sata: AHCI 0001.0000",
    "ata1: SATA link up 1.5 Gbps",
    "ata1.00: ATA-7: QEMU HARDDISK",
    "scsi 0:0:0:0: Direct-Access",
    "SynologyNAS login:",
)
FAILURES = re.compile(
    r"\b(?:Kernel panic\b|Oops:|BUG:|undefined instruction\b|Synchronous Abort\b|"
    r"SError Interrupt\b|soft lockup\b)",
    re.IGNORECASE,
)


def verify(text: str) -> None:
    missing = [marker for marker in REQUIRED if marker not in text]
    if missing:
        raise ValueError("missing DSM initrd SATA evidence: " + ", ".join(missing))
    failure = FAILURES.search(text)
    if failure:
        raise ValueError("failure signature in DSM initrd SATA log: " + failure.group(0))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: verify-dsm-initrd-sata.py SERIAL_LOG")
    try:
        verify(Path(sys.argv[1]).read_text(encoding="utf-8", errors="replace"))
    except (OSError, ValueError) as error:
        print(f"DS124 initrd SATA verification failed: {error}", file=sys.stderr)
        raise SystemExit(1)
    print("Stock DS124 initrd reached login after detecting the isolated blank SATA disk.")
