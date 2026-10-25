#!/usr/bin/env python3
"""Fail closed when required CI jobs fail, cancel or unexpectedly skip."""
import json
import os
import sys

REQUIRED = {'plan', 'docs', 'lint', 'tests', 'qemu-patches', 'research-smoke',
            'arm64-loader', 'x86_64-loader', 'images'}


def failures(needs: dict) -> list[str]:
    errors = []
    if set(needs) != REQUIRED:
        errors.append('CI dependency set differs from the required policy')
    images = needs.get('plan', {}).get('outputs', {}).get('images')
    if images not in {'true', 'false'}:
        errors.append('CI plan must explicitly select images=true or false')
    for name in sorted(REQUIRED):
        result = needs.get(name, {}).get('result', 'missing')
        expected = 'skipped' if name == 'images' and images == 'false' else 'success'
        if result != expected:
            errors.append(f'{name}: {result}; expected {expected}')
    return errors


def main() -> int:
    needs = json.loads(os.environ['CI_NEEDS'])
    errors = failures(needs)
    summary = '\n'.join(f"- {name}: {job.get('result', 'missing')}" for name, job in needs.items())
    print(summary)
    if path := os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(path, 'a', encoding='utf-8', newline='\n') as stream:
            stream.write('## DockDSM CI result\n\n' + summary + '\n')
    if errors:
        print('\n'.join(errors), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
