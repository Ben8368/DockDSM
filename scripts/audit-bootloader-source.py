#!/usr/bin/env python3
"""Inventory pinned Git objects without executing or copying upstream code."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LOCK = ROOT / 'research/bootloader/source-lock.json'


def git(source: Path, *args: str) -> bytes:
    """Run a fixed read-only Git command against the explicitly selected repository."""
    env = {key: value for key, value in os.environ.items()
           if not key.startswith('GIT_')}
    env['GIT_CONFIG_NOSYSTEM'] = '1'
    env['GIT_CONFIG_GLOBAL'] = os.devnull
    env['GIT_OPTIONAL_LOCKS'] = '0'
    env['GIT_NO_REPLACE_OBJECTS'] = '1'
    env['GIT_NO_LAZY_FETCH'] = '1'
    # Also block transports on Git versions that lack GIT_NO_LAZY_FETCH.
    env['GIT_ALLOW_PROTOCOL'] = ''
    return subprocess.check_output(['git', '--no-pager', '-c', 'core.fsmonitor=false', '-C', str(source), *args],
                                   env=env, stderr=subprocess.PIPE)


def inventory(source: Path, lock: dict) -> dict:
    """Verify a source lock, then report object sizes and local history limits."""
    if lock['schema_version'] != 1:
        raise ValueError('unsupported source lock schema')
    revision, expected_tree = (lock['upstream'][key] for key in ('revision', 'tree'))
    if any(not re.fullmatch(r'[0-9a-f]{40}', value) for value in (revision, expected_tree)):
        raise ValueError('source revision/tree must be full Git SHA-1 identities')
    if git(source, 'rev-parse', 'HEAD').decode().strip() != revision:
        raise ValueError('source HEAD does not match locked revision')
    if git(source, 'rev-parse', revision + '^{tree}').decode().strip() != expected_tree:
        raise ValueError('source tree does not match lock')
    entries = []
    for record in git(source, 'ls-tree', '-r', '-l', '-z', revision).split(b'\0'):
        if not record:
            continue
        metadata, path = record.split(b'\t', 1)
        mode, kind, oid, size = metadata.split()
        if kind == b'blob' and not size.isdigit():
            raise ValueError('source blob is unavailable locally: ' + path.decode('utf-8'))
        entries.append(dict(path=path.decode('utf-8'), mode=mode.decode(),
                            kind=kind.decode(), oid=oid.decode(),
                            size=int(size) if size != b'-' else 0))
    snapshot = dict(entries=len(entries), blob_bytes=sum(e['size'] for e in entries))
    if snapshot != lock['snapshot']:
        raise ValueError('source file count/size does not match lock')
    by_path = {entry['path']: entry for entry in entries}
    for path, expected in lock['evidence'].items():
        if path not in by_path or by_path[path]['kind'] != 'blob':
            raise ValueError(f'evidence is not a locked blob: {path}')
        raw = git(source, 'cat-file', 'blob', by_path[path]['oid'])
        actual = dict(sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw))
        if actual != expected:
            raise ValueError(f'evidence digest/size does not match lock: {path}')
    shallow = git(source, 'rev-parse', '--is-shallow-repository').strip() == b'true'
    # Git storage is a local clone property; it is not the size of this snapshot
    # or evidence that all upstream history has been obtained.
    storage = dict(line.split(': ', 1) for line in
                   git(source, 'count-objects', '-v').decode().splitlines())
    return dict(schema_version=1, upstream=lock['upstream'], snapshot=snapshot,
                largest=sorted(entries, key=lambda e: (-e['size'], e['path']))[:12],
                evidence_verified=sorted(lock['evidence']),
                local_history=dict(shallow=shallow,
                                   reachable_commits=int(git(source, 'rev-list', '--count', revision)),
                                   upstream_history_verified=False),
                local_storage=storage, reads='locked Git objects, not working tree files',
                distribution=lock['distribution'],
                unlocked_dependencies=lock['unlocked_dependencies'])


def main() -> int:
    """Print a JSON audit or fail closed on identity/evidence mismatches."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True, help='local upstream Git checkout')
    parser.add_argument('--lock', type=Path, default=DEFAULT_LOCK)
    args = parser.parse_args()
    try:
        lock = json.loads(args.lock.read_text(encoding='utf-8'))
        result = inventory(args.source.resolve(strict=True), lock)
    except (OSError, ValueError, KeyError, TypeError, subprocess.CalledProcessError) as error:
        # Git stderr can contain local URLs/credentials. Do not echo it.
        message = ('Git source inspection failed' if isinstance(error, subprocess.CalledProcessError)
                   else str(error))
        print(f'Bootloader source audit failed: {message}', file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
