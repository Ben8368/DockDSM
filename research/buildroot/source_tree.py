"""Seal and verify the extracted Buildroot source tree used by loader builds."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import tempfile


PROVENANCE_NAME = ".dockdsm-buildroot-source.json"
SCHEMA_VERSION = 1
LOCK = Path(__file__).with_name("source-lock.json")


def tree_fingerprint(root: Path) -> str:
    root = root.resolve(strict=True)
    if not root.is_dir():
        raise ValueError("Buildroot source root is not a directory")
    entries: list[Path] = []
    for directory, directories, files in os.walk(root, topdown=True, followlinks=False):
        current = Path(directory)
        kept_directories = []
        for name in sorted(directories):
            path = current / name
            if path.is_symlink():
                entries.append(path)
            else:
                kept_directories.append(name)
                entries.append(path)
        directories[:] = kept_directories
        entries.extend(current / name for name in sorted(files))

    digest = hashlib.sha256()
    for path in sorted(entries, key=lambda item: item.relative_to(root).as_posix()):
        relative = path.relative_to(root).as_posix()
        if relative == PROVENANCE_NAME or relative.startswith(".dockdsm-buildroot-source."):
            continue
        metadata = path.lstat()
        mode = stat.S_IMODE(metadata.st_mode)
        if stat.S_ISDIR(metadata.st_mode):
            kind, size, content_hash = "directory", 0, ""
        elif stat.S_ISREG(metadata.st_mode):
            file_digest = hashlib.sha256()
            size = 0
            with path.open("rb") as source:
                for block in iter(lambda: source.read(1024 * 1024), b""):
                    file_digest.update(block)
                    size += len(block)
            kind, content_hash = "file", file_digest.hexdigest()
        elif stat.S_ISLNK(metadata.st_mode):
            target = os.readlink(path).encode("utf-8")
            kind, size = "symlink", len(target)
            content_hash = hashlib.sha256(target).hexdigest()
        else:
            raise ValueError(f"unsupported Buildroot source entry type: {relative}")
        record = json.dumps(
            {"path": relative, "kind": kind, "mode": mode,
             "size": size, "sha256": content_hash},
            sort_keys=True, separators=(",", ":")).encode("utf-8")
        digest.update(len(record).to_bytes(8, "big"))
        digest.update(record)
    return digest.hexdigest()


def _locked_values(lock_path: Path) -> tuple[str, str]:
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    return lock["version"], lock["sha256"]


def seal_source_tree(root: Path, version: str, archive_sha256: str,
                     lock_path: Path = LOCK) -> Path:
    locked_version, locked_sha256 = _locked_values(lock_path)
    if (version, archive_sha256) != (locked_version, locked_sha256):
        raise ValueError("Buildroot archive metadata does not match the source lock")
    marker = root / PROVENANCE_NAME
    payload = {
        "schema_version": SCHEMA_VERSION,
        "version": version,
        "archive_sha256": archive_sha256,
        "tree_sha256": tree_fingerprint(root),
    }
    descriptor, temporary = tempfile.mkstemp(prefix=".dockdsm-buildroot-source.", dir=root)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as output:
            json.dump(payload, output, sort_keys=True, indent=2)
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, marker)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise
    return marker


def verify_source_tree(root: Path, lock_path: Path = LOCK) -> None:
    locked_version, locked_sha256 = _locked_values(lock_path)
    marker = root / PROVENANCE_NAME
    try:
        if not stat.S_ISREG(marker.lstat().st_mode):
            raise ValueError("Buildroot source provenance marker is not a regular file")
        payload = json.loads(marker.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError("Buildroot source provenance marker is missing or invalid") from error
    expected_fields = {"schema_version", "version", "archive_sha256", "tree_sha256"}
    if not isinstance(payload, dict) or set(payload) != expected_fields:
        raise ValueError("Buildroot source provenance marker has unexpected fields")
    if (type(payload["schema_version"]) is not int
            or payload["schema_version"] != SCHEMA_VERSION
            or payload["version"] != locked_version
            or payload["archive_sha256"] != locked_sha256):
        raise ValueError("Buildroot source provenance does not match the shared source lock")
    if payload["tree_sha256"] != tree_fingerprint(root):
        raise ValueError("Buildroot source tree changed after archive verification")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("seal", "verify"))
    parser.add_argument("root", type=Path)
    parser.add_argument("--version")
    parser.add_argument("--archive-sha256")
    args = parser.parse_args()
    try:
        if args.action == "seal":
            if args.version is None or args.archive_sha256 is None:
                parser.error("seal requires --version and --archive-sha256")
            marker = seal_source_tree(args.root, args.version, args.archive_sha256)
            print(f"Sealed verified Buildroot source tree: {marker}")
        else:
            if args.version is not None or args.archive_sha256 is not None:
                parser.error("verify does not accept archive metadata")
            verify_source_tree(args.root)
            print("Buildroot source tree provenance verified.")
    except (OSError, KeyError, json.JSONDecodeError, ValueError) as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
