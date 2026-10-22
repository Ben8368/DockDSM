#!/usr/bin/env python3
"""Conservative CI planning: only a proven documentation-only diff skips images."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess


def git(*args: str) -> str:
    return subprocess.check_output(['git', *args], encoding='utf-8').strip()


def documentation(path: str) -> bool:
    return path.endswith('.md') or path in {'NOTICE', 'license.md'}


def plan(event_name: str, event: dict, head: str, force: bool = False) -> dict:
    if force or event_name not in {'push', 'pull_request'}:
        return {'images': True, 'reason': 'explicit-full-validation'}
    if len(git('rev-list', '--parents', '-n', '1', head).split()) == 1:
        return {'images': True, 'reason': 'root-snapshot'}
    if event_name == 'pull_request':
        base = event.get('pull_request', {}).get('base', {}).get('sha', '')
    else:
        base = event.get('before', '')
    if not base or set(base) == {'0'}:
        return {'images': True, 'reason': 'initial-or-unknown-base'}
    try:
        # Resolve SHAs before diff; never interpret event data as an option/ref expression.
        if len(base) != 40 or any(c not in '0123456789abcdef' for c in base):
            raise ValueError('invalid base SHA')
        git('cat-file', '-e', base + '^{commit}')
        if event_name == 'pull_request':
            base = git('merge-base', base, head)
        paths = git('diff', '--name-only', '--no-renames', '-z', base, head, '--').split('\0')
    except (subprocess.CalledProcessError, ValueError):
        return {'images': True, 'reason': 'unavailable-base'}
    changed = [path for path in paths if path]
    docs_only = bool(changed) and all(documentation(path) for path in changed)
    return {'images': not docs_only,
            'reason': 'documentation-only' if docs_only else 'runtime-or-unknown-change'}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--force-images', action='store_true')
    args = parser.parse_args()
    event_path = os.environ.get('GITHUB_EVENT_PATH')
    event = json.loads(Path(event_path).read_text(encoding='utf-8')) if event_path else {}
    result = plan(os.environ.get('GITHUB_EVENT_NAME', ''), event, git('rev-parse', 'HEAD'),
                  args.force_images or os.environ.get('FORCE_IMAGES') == 'true')
    print(json.dumps(result))
    if output := os.environ.get('GITHUB_OUTPUT'):
        with Path(output).open('a', encoding='utf-8', newline='\n') as stream:
            stream.write(f"images={str(result['images']).lower()}\nreason={result['reason']}\n")


if __name__ == '__main__':
    main()
