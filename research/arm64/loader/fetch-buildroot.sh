#!/usr/bin/env bash
set -Eeuo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
lock_values=$(python3 - "$script_dir/../../buildroot/source-lock.json" <<'PY'
import json
from pathlib import Path
import sys

lock = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
print(lock["version"], lock["sha256"], sep="\t")
PY
)
IFS=$'\t' read -r expected_version expected_sha256 <<< "$lock_values"
unset lock_values
[[ -n "$expected_version" && -n "$expected_sha256" ]] || {
  echo 'ERROR: source-lock.json is missing Buildroot version or SHA256.' >&2
  exit 2
}
archive_name="buildroot-$expected_version.tar.xz"

if [[ $# -ne 1 || -z "$1" ]]; then
  echo "Usage: $0 /path/to/new/buildroot-$expected_version" >&2
  exit 2
fi
destination=$1
[[ "$destination" != / && ! -e "$destination" && ! -L "$destination" ]] || {
  echo "ERROR: destination must be a new path: $destination" >&2
  exit 2
}
parent=$(dirname -- "$destination")
mkdir -p -- "$parent"
tmp=$(mktemp -d "${TMPDIR:-/tmp}/dockdsm-buildroot.XXXXXX")
trap 'rm -rf -- "$tmp"' EXIT

curl --fail --silent --show-error --location --retry 3 \
  --proto '=https' --tlsv1.2 \
  "https://buildroot.org/downloads/$archive_name" -o "$tmp/$archive_name"
actual_sha256=$(python3 - "$tmp/$archive_name" <<'PY'
import hashlib
from pathlib import Path
import sys
h = hashlib.sha256()
with Path(sys.argv[1]).open('rb') as source:
    for block in iter(lambda: source.read(1024 * 1024), b''):
        h.update(block)
print(h.hexdigest())
PY
)
[[ "$actual_sha256" == "$expected_sha256" ]] || {
  echo "ERROR: Buildroot SHA256 mismatch: $actual_sha256" >&2
  exit 1
}

python3 - "$tmp/$archive_name" "$expected_version" <<'PY'
import pathlib
import sys
import tarfile
archive, version = sys.argv[1:]
root = f'buildroot-{version}'
with tarfile.open(archive, 'r:xz') as tar:
    for member in tar.getmembers():
        path = pathlib.PurePosixPath(member.name)
        if path.is_absolute() or '..' in path.parts or not path.parts or path.parts[0] != root:
            raise SystemExit(f'unsafe or unexpected archive path: {member.name!r}')
PY
tar --no-same-owner --no-same-permissions -xf "$tmp/$archive_name" -C "$tmp"
source="$tmp/buildroot-$expected_version"
grep -Fqx "export BR2_VERSION := $expected_version" "$source/Makefile"
python3 "$script_dir/../../buildroot/source_tree.py" seal "$source" \
  --version "$expected_version" --archive-sha256 "$actual_sha256"
mv -- "$source" "$destination"
printf 'Buildroot %s verified at %s (SHA256 %s)\n' "$expected_version" "$destination" "$actual_sha256"
