#!/usr/bin/env python3
"""Check every tracked UTF-8 text file, including a freshly initialized root tree."""
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
TEXT_SUFFIXES = {'.md', '.sh', '.py', '.yml', '.yaml', '.json', '.patch', '.service',
                 '.conf', '.js', '.c', '.h', '.S', '.ld', '.gdb', '.txt', '.args', '.sha256'}
TEXT_NAMES = {'Dockerfile', 'NOTICE', '.gitattributes', '.gitignore', '.dockerignore',
              '.cursorrules', '.shellcheckrc', 'commit-msg'}


def check(name: str, raw: bytes) -> list[str]:
    expected_text = Path(name).suffix in TEXT_SUFFIXES or Path(name).name in TEXT_NAMES
    try:
        text = raw.decode('utf-8')
    except UnicodeDecodeError:
        return [f'{name}: expected UTF-8 text'] if expected_text else []
    if b'\0' in raw and not expected_text:
        return []
    errors = []
    if text.startswith('\ufeff'):
        errors.append(f'{name}: UTF-8 BOM is not allowed')
    if '\r' in text:
        errors.append(f'{name}: use LF line endings')
    # Unified diff context lines legitimately contain trailing spaces.
    if not name.endswith('.patch'):
        for number, line in enumerate(text.splitlines(), 1):
            if line.rstrip(' \t') != line:
                errors.append(f'{name}:{number}: trailing whitespace')
    return errors


def main() -> int:
    tracked = subprocess.check_output(['git', 'ls-files', '-z'], cwd=ROOT).decode().split('\0')
    errors = []
    for name in filter(None, tracked):
        path = ROOT / name
        if not path.is_file():
            errors.append(f'{name}: tracked file is missing')
            continue
        errors.extend(check(name, path.read_bytes()))
    if errors:
        print('\n'.join(errors), file=sys.stderr)
        return 1
    print('Tracked tree: UTF-8/LF and whitespace checks passed.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
