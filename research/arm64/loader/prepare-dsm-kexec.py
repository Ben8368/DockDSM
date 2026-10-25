#!/usr/bin/env python3
"""Build a private, diskless DS124 kexec test initramfs from supplied boot files."""
import argparse
import importlib.util
import lzma
from pathlib import Path
import stat
import sys
import tempfile


REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "research/buildroot"))
from check_inputs import resolve_output_path  # noqa: E402

PACKER_PATH = Path(__file__).resolve().parent / "board/arm64-kexec/make-initramfs.py"
SPEC = importlib.util.spec_from_file_location("dockdsm_make_initramfs", PACKER_PATH)
PACKER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PACKER)

IMAGE_MAGIC_OFFSET = 0x38
IMAGE_MAGIC = b"ARM\x64"
CPIO_MAGICS = (b"070701", b"070702")


def _read_regular(path: Path, label: str) -> bytes:
    try:
        metadata = path.lstat()
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_size == 0:
            raise ValueError(f"{label} must be a nonempty regular file, not a symlink")
        return path.read_bytes()
    except OSError as error:
        raise ValueError(f"cannot read {label}: {path}") from error


def _decompress_if_needed(data: bytes, label: str, magic_check) -> bytes:
    if magic_check(data):
        return data
    try:
        expanded = lzma.decompress(data, format=lzma.FORMAT_ALONE)
    except lzma.LZMAError as error:
        raise ValueError(f"{label} is neither in the expected raw format nor LZMA-alone") from error
    if not magic_check(expanded):
        raise ValueError(f"{label} does not contain the expected ARM64 Image/cpio payload")
    return expanded


def prepare(buildroot_target: Path, kernel_path: Path, initrd_path: Path,
            output_path: Path) -> Path:
    target = buildroot_target.resolve(strict=True)
    if not target.is_dir():
        raise ValueError("Buildroot target must be a directory")
    output = resolve_output_path(REPO_ROOT, output_path)
    if output.exists():
        raise ValueError("output file already exists; refusing to overwrite it")

    kernel = _decompress_if_needed(
        _read_regular(kernel_path, "DS124 kernel"), "DS124 kernel",
        lambda payload: len(payload) >= IMAGE_MAGIC_OFFSET + len(IMAGE_MAGIC)
        and payload[IMAGE_MAGIC_OFFSET:IMAGE_MAGIC_OFFSET + len(IMAGE_MAGIC)] == IMAGE_MAGIC)
    initrd = _decompress_if_needed(
        _read_regular(initrd_path, "DS124 initrd"), "DS124 initrd",
        lambda payload: payload.startswith(CPIO_MAGICS))

    loader_init = Path(__file__).resolve().parent / "board/arm64-kexec/dsm-loader-init"
    with tempfile.TemporaryDirectory(prefix="dockdsm-dsm-kexec-input-") as temporary:
        kernel_file = Path(temporary) / "DSM_DS124_72806.Image"
        initrd_file = Path(temporary) / "DSM_DS124_72806.initrd.cpio"
        kernel_file.write_bytes(kernel)
        initrd_file.write_bytes(initrd)
        PACKER.build(
            target,
            output,
            overrides=(("init", (loader_init.read_bytes(), 0o755)),),
            extras=(("boot/DSM_DS124_72806.Image", kernel_file),
                    ("boot/DSM_DS124_72806.initrd.cpio", initrd_file)),
        )
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("buildroot_target", type=Path)
    parser.add_argument("dsm_kernel", type=Path,
                        help="DS124 ARM64 Image or PAT zImage (LZMA-alone)")
    parser.add_argument("dsm_initrd", type=Path,
                        help="uncompressed newc cpio or PAT rd.bin (LZMA-alone)")
    parser.add_argument("output", type=Path,
                        help="new initramfs path outside the repository")
    args = parser.parse_args()
    try:
        output = prepare(args.buildroot_target, args.dsm_kernel, args.dsm_initrd,
                         args.output)
    except (OSError, RuntimeError, ValueError) as error:
        parser.error(str(error))
    print(f"Private DS124 kexec test initramfs: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
