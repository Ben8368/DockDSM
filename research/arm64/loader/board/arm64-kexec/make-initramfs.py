#!/usr/bin/env python3
"""Build deterministic newc initramfs images without privileged mknod/cpio."""
import gzip
import os
from pathlib import Path
import stat
import sys
import tempfile


EPOCH = int(os.environ.get("SOURCE_DATE_EPOCH", "0"))


def _entry(name, mode, data=b"", rdevmajor=0, rdevminor=0, ino=1):
    encoded_name = name.encode("utf-8") + b"\0"
    values = (ino, mode, 0, 0, 1, EPOCH, len(data), 0, 0,
              rdevmajor, rdevminor, len(encoded_name), 0)
    header = b"070701" + b"".join(f"{value:08x}".encode("ascii") for value in values)
    record = header + encoded_name
    record += bytes((-len(record)) % 4)
    record += data
    record += bytes((-len(data)) % 4)
    return record


def _walk(root):
    root = Path(root)
    for directory, subdirs, filenames in os.walk(root, followlinks=False):
        subdirs.sort()
        filenames.sort()
        current = Path(directory)
        for path in sorted((current / name for name in subdirs + filenames),
                           key=lambda item: item.relative_to(root).as_posix()):
            relative = path.relative_to(root).as_posix()
            metadata = path.lstat()
            mode = metadata.st_mode
            if stat.S_ISDIR(mode):
                yield relative, stat.S_IFDIR | stat.S_IMODE(mode), b"", 0, 0
            elif stat.S_ISREG(mode):
                yield relative, stat.S_IFREG | stat.S_IMODE(mode), path.read_bytes(), 0, 0
            elif stat.S_ISLNK(mode):
                yield relative, stat.S_IFLNK | stat.S_IMODE(mode), os.readlink(path).encode(), 0, 0
            elif stat.S_ISCHR(mode):
                yield relative, stat.S_IFCHR | stat.S_IMODE(mode), b"", os.major(metadata.st_rdev), os.minor(metadata.st_rdev)
            elif stat.S_ISBLK(mode):
                yield relative, stat.S_IFBLK | stat.S_IMODE(mode), b"", os.major(metadata.st_rdev), os.minor(metadata.st_rdev)
            elif stat.S_ISFIFO(mode):
                yield relative, stat.S_IFIFO | stat.S_IMODE(mode), b"", 0, 0
            else:
                raise ValueError(f"unsupported initramfs entry type: {relative}")


def build(root, output, overrides=(), extras=()):
    root = Path(root)
    output = Path(output)
    replaced = dict(overrides)
    records = {}
    for name, mode, data, major, minor in _walk(root):
        if name in replaced:
            data, mode = replaced.pop(name)
            mode = stat.S_IFREG | mode
            major = minor = 0
        records[name] = (mode, data, major, minor)
    if replaced:
        raise ValueError("initramfs override path does not exist: " + ", ".join(sorted(replaced)))
    for name, source in extras:
        source = Path(source)
        if not source.is_file() or not source.stat().st_size:
            raise ValueError(f"required initramfs input is missing or empty: {source}")
        parent = Path(name).parent
        ancestors = []
        while parent != Path("."):
            ancestors.append(parent.as_posix())
            parent = parent.parent
        for directory in reversed(ancestors):
            records.setdefault(directory, (stat.S_IFDIR | 0o755, b"", 0, 0))
        records[name] = (stat.S_IFREG | 0o644, source.read_bytes(), 0, 0)
    records.setdefault("dev", (stat.S_IFDIR | 0o755, b"", 0, 0))
    records["dev/console"] = (stat.S_IFCHR | 0o600, b"", 5, 1)
    records["dev/null"] = (stat.S_IFCHR | 0o666, b"", 1, 3)

    output.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix="." + output.name + ".", dir=output.parent)
    try:
        with os.fdopen(fd, "wb") as raw, gzip.GzipFile(filename="", mode="wb", fileobj=raw,
                                                        mtime=EPOCH, compresslevel=9) as compressed:
            for ino, name in enumerate(sorted(records), start=1):
                mode, data, major, minor = records[name]
                compressed.write(_entry(name, mode, data, major, minor, ino))
            compressed.write(_entry("TRAILER!!!", 0, b"", ino=len(records) + 1))
        os.replace(temporary, output)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def main(argv):
    if len(argv) != 6:
        raise SystemExit("usage: make-initramfs.py TARGET_DIR KERNEL BINARIES_DIR TARGET_INIT LOADER_INIT")
    target, kernel, binaries, target_init, loader_init = map(Path, argv[1:])
    binaries.mkdir(parents=True, exist_ok=True)
    target_archive = binaries / "dockdsm-target.cpio.gz"
    loader_archive = binaries / "dockdsm-loader.cpio.gz"
    build(target, target_archive, overrides=(("init", (Path(target_init).read_bytes(), 0o755)),))
    build(target, loader_archive,
          overrides=(("init", (Path(loader_init).read_bytes(), 0o755)),),
          extras=(("boot/Image", kernel), ("boot/dockdsm-target.cpio.gz", target_archive)))


if __name__ == "__main__":
    main(sys.argv)
