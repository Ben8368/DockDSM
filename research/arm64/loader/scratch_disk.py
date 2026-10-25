"""Create the disposable raw disk used only by the DS124 SATA probe."""
from __future__ import annotations

import os
from pathlib import Path
import stat


SCRATCH_NAME = "dockdsm-ds124-scratch-sata1.img"
SCRATCH_BYTES = 2 * 1024 * 1024 * 1024


def create_scratch_sata1(directory: str | Path, repository: str | Path) -> Path:
    """Create one private sparse disk, failing closed on every existing path."""
    raw_directory = Path(directory)
    if raw_directory.is_symlink():
        raise ValueError("scratch output directory must not be a symlink")
    try:
        output = raw_directory.resolve(strict=True)
        root = Path(repository).resolve(strict=True)
        metadata = output.stat()
    except OSError as error:
        raise ValueError("scratch output directory and repository must already exist") from error
    if not output.is_dir() or stat.S_IMODE(metadata.st_mode) & 0o077:
        raise ValueError("scratch output directory must be a private directory (mode 0700)")
    if output == root or root in output.parents:
        raise ValueError("scratch SATA image must be outside the repository")

    image = output / SCRATCH_NAME
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
    flags |= getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(image, flags, 0o600)
    except FileExistsError as error:
        raise ValueError("scratch SATA image already exists; refusing to reuse or overwrite it") from error
    try:
        os.ftruncate(descriptor, SCRATCH_BYTES)
        os.fsync(descriptor)
        metadata = os.fstat(descriptor)
        if metadata.st_size != SCRATCH_BYTES or metadata.st_blocks != 0:
            raise ValueError("filesystem did not create a sparse 2 GiB scratch disk")
    except BaseException:
        os.close(descriptor)
        image.unlink(missing_ok=True)
        raise
    else:
        os.close(descriptor)
    return image


def verify_scratch_sata1(directory: str | Path, repository: str | Path) -> Path:
    """Require the isolated disk to remain an untouched sparse blank image."""
    raw_directory = Path(directory)
    if raw_directory.is_symlink():
        raise ValueError("scratch output directory must not be a symlink")
    try:
        output = raw_directory.resolve(strict=True)
        root = Path(repository).resolve(strict=True)
        directory_metadata = output.stat()
    except OSError as error:
        raise ValueError("scratch output directory and repository must already exist") from error
    if not output.is_dir() or stat.S_IMODE(directory_metadata.st_mode) & 0o077:
        raise ValueError("scratch output directory must be a private directory (mode 0700)")
    if output == root or root in output.parents:
        raise ValueError("scratch SATA image must be outside the repository")

    image = output / SCRATCH_NAME
    try:
        metadata = image.lstat()
    except OSError as error:
        raise ValueError("scratch SATA image is missing") from error
    if (not stat.S_ISREG(metadata.st_mode) or stat.S_IMODE(metadata.st_mode) != 0o600
            or metadata.st_size != SCRATCH_BYTES or metadata.st_nlink != 1
            or metadata.st_blocks != 0):
        raise ValueError("scratch SATA image was replaced, allocated, or changed from its blank 2 GiB state")
    return image
