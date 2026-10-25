#!/usr/bin/env python3
"""Verify stock DS124 kernel SATA discovery with a private blank scratch disk."""
from pathlib import Path
import re
import sys


REQUIRED = (
    "rtk_ahci b100000.sata: AHCI 0001.0000",
    "ata1: SATA link up 1.5 Gbps",
    "ata1.00: ATA-7: QEMU HARDDISK",
    "scsi 0:0:0:0: Direct-Access",
    "DOCKDSM_DS124_SATA_PROBE_INIT",
    "DOCKDSM_DS124_SATA_PROBE_PASS sectors=4194304",
    "reboot: Power down",
)
FORBIDDEN = re.compile(
    r"kernel panic|Oops:|\bBUG:|undefined instruction|synchronous external abort|"
    r"SError Interrupt|soft lockup|DOCKDSM_DS124_SATA_PROBE_(?:FAIL|ERROR)_",
    re.IGNORECASE,
)
PARTITION = re.compile(r"^\s*8\s+0\s+2097152\s+sata1\s*$", re.MULTILINE)


def verify(text: str) -> None:
    missing = [marker for marker in REQUIRED if marker not in text]
    if missing:
        raise ValueError("missing DS124 SATA probe evidence: " + ", ".join(missing))
    if not PARTITION.search(text):
        raise ValueError("the 2 GiB /dev/sata1 block geometry was not printed")
    match = FORBIDDEN.search(text)
    if match:
        raise ValueError("forbidden DS124 SATA probe failure signature: " + match.group(0))
    if "DOCKDSM_DS124_SATA_PROBE_ERROR_POWEROFF_RETURNED" in text:
        raise ValueError("guest poweroff unexpectedly returned")


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(f"Usage: {argv[0]} SERIAL_LOG", file=sys.stderr)
        return 2
    try:
        verify(Path(argv[1]).read_text(encoding="utf-8", errors="replace"))
    except (OSError, ValueError) as error:
        print(f"DS124 SATA probe verification failed: {error}", file=sys.stderr)
        return 1
    print("Stock DS124 kernel discovered the isolated 2 GiB QEMU SATA disk and powered off cleanly.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
