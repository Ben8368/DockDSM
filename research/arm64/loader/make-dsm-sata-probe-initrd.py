#!/usr/bin/env python3
"""Pack a minimal diagnostic initramfs for the official DS124 kernel."""
import importlib.util
import gzip
from pathlib import Path
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[3]
PACKER = Path(__file__).resolve().parent / "board/arm64-kexec/make-initramfs.py"
INIT = Path(__file__).resolve().parent / "board/arm64-kexec/sata-probe-init"
spec = importlib.util.spec_from_file_location("dockdsm_dsm_probe_packer", PACKER)
packer = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(packer)


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print(f"Usage: {argv[0]} BUILDROOT_TARGET NEW_INITRD.cpio.gz", file=sys.stderr)
        return 2
    target = Path(argv[1]).resolve(strict=True)
    output_arg = Path(argv[2])
    if output_arg.exists() or output_arg.is_symlink():
        print("ERROR: probe initramfs output already exists; refusing overwrite.", file=sys.stderr)
        return 2
    output_parent = output_arg.parent.resolve(strict=True)
    output = output_parent / output_arg.name
    if not target.is_dir() or not (target / "bin/busybox").exists():
        print("ERROR: BUILDROOT_TARGET must contain the built BusyBox runtime.", file=sys.stderr)
        return 2
    if output_parent == ROOT or ROOT in output_parent.parents:
        print("ERROR: probe initramfs must be written outside the repository.", file=sys.stderr)
        return 2
    if not INIT.is_file() or not INIT.stat().st_size:
        print("ERROR: the DS124 SATA probe init script is missing or empty.", file=sys.stderr)
        return 2
    with tempfile.TemporaryDirectory(prefix=".dockdsm-sata-probe-", dir=output_parent) as work:
        compressed = Path(work) / "probe.cpio.gz"
        packer.build(target, compressed, overrides=(("init", (INIT.read_bytes(), 0o755)),))
        with output.open("xb") as stream:
            stream.write(gzip.decompress(compressed.read_bytes()))
    print(f"DS124 diagnostic initramfs: {output}")
    return 0
if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
