#!/usr/bin/env python3
"""Regression tests for governance-docs-check.py against minimal fixtures."""
from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from typing import Callable

ROOT = Path(__file__).resolve().parents[1]
CHECK = ROOT / 'scripts' / 'governance-docs-check.py'

FILES = {
    'AGENTS.md': '''# AI 协作规范

## 开局与按需读取

见 [治理](docs/GOVERNANCE.md)。

## 不可跨越的边界

- 不伪造。

## 治理文档自治理

遵守 docs/GOVERNANCE.md。
''',
    'CONTEXT.md': '''# 当前状态

> **最后确认：** 2026-10-22
> **阶段：** fixture 说明

## 当前决策

- fixture。

## 近期优先级

1. fixture。

## 最近验证

- 2026-10-22：[记录](evidence.md)。

## 按需入口

- [治理](docs/GOVERNANCE.md)
''',
    'LESSONS.md': '''# Lessons Router

| 任务 | 加载 |
| --- | --- |
| 治理 | [docs/lessons/governance.md](docs/lessons/governance.md) |
| QEMU | [docs/lessons/qemu.md](docs/lessons/qemu.md) |
| ARM64 | [docs/lessons/arm64.md](docs/lessons/arm64.md) |
| Windows | [docs/lessons/windows.md](docs/lessons/windows.md) |
''',
    'CLAUDE.md': '# 摘要\n\n见 AGENTS.md。\n',
    '.cursorrules': '# 摘要\n\n见 AGENTS.md。\n',
    'readme.md': '# Fixture\n',
    'SECURITY.md': '# Fixture\n',
    'evidence.md': '# Evidence\n',
    'docs/lessons/governance.md': '# Governance\n',
    'docs/lessons/qemu.md': '# QEMU\n',
    'docs/lessons/arm64.md': '# ARM64\n',
    'docs/lessons/windows.md': '# Windows\n',
    'docs/GOVERNANCE.md': '# Governance\n',
    'docs/AI_RULES.md': '# AI rules\n',
    'docs/PRODUCT.md': '# Product\n',
    'docs/QUALITY.md': '# Quality\n',
    'docs/RISK_REGISTER.md': '# Risk\n',
    'docs/TECH_DEBT.md': '# Tech debt\n',
    'docs/MAINTAINERS.md': '# Maintainers\n',
    'docs/platforms.md': '# Platforms\n',
    'docs/ci.md': '# CI\n',
    'docs/arm64-development.md': '# ARM64 development\n',
    'docs/ADR/README.md': '''# Architecture Decision Records

| 编号 | 状态 | 决策 |
| --- | --- | --- |
| [0001](0001-fixture.md) | 已接受 | fixture |
''',
    'docs/ADR/0001-fixture.md': '''# ADR 0001：fixture

- 状态：已接受
- 日期：2026-10-22

## 背景

fixture
''',
}


def write_tree(base: Path) -> None:
    for name, text in FILES.items():
        path = base / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding='utf-8', newline='\n')


def run_check(case: Path) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env['PYTHONIOENCODING'] = 'utf-8'
    env['GIT_CEILING_DIRECTORIES'] = str(case.parent)
    return subprocess.run(
        [sys.executable, str(CHECK), '--root', str(case)],
        cwd=case, env=env, text=True, encoding='utf-8', errors='replace',
        capture_output=True, check=False)


def expect(case: Path, accepted: bool, fragment: str = '') -> bool:
    result = run_check(case)
    ok = result.returncode == 0 if accepted else result.returncode != 0
    if ok and fragment and fragment not in (result.stderr + result.stdout):
        ok = False
    if not ok:
        print(f'FAIL: expected accepted={accepted}, rc={result.returncode}')
        print(result.stderr or result.stdout)
    return ok


def mutate(base: Path, name: str, old: str, new: str) -> None:
    path = base / name
    text = path.read_text(encoding='utf-8')
    if old not in text:
        raise AssertionError(f'fixture text not found in {name}: {old}')
    path.write_text(text.replace(old, new, 1), encoding='utf-8', newline='\n')


def main() -> int:
    failures = 0
    with tempfile.TemporaryDirectory(prefix='dockdsm-governance-') as tmp:
        fixture = Path(tmp) / 'fixture'
        write_tree(fixture)

        cases: list[tuple[str, bool, str, Callable[[Path], object]]] = [
            ('baseline', True, '', lambda case: None),
            ('prose-stage-with-phase-claim', False, '未提供 Phase 编号',
             lambda case: mutate(case, 'readme.md', '# Fixture\n', '# Fixture\n\n当前处于 **Phase 3**。\n')),
            ('phase-mismatch', False, '不一致', lambda case: (
                mutate(case, 'CONTEXT.md', '> **阶段：** fixture 说明', '> **阶段：** Phase 2'),
                mutate(case, 'readme.md', '# Fixture\n', '# Fixture\n\n当前处于 Phase 3。\n'))),
            ('phase-match', True, '', lambda case: (
                mutate(case, 'CONTEXT.md', '> **阶段：** fixture 说明', '> **阶段：** Phase 2'),
                mutate(case, 'readme.md', '# Fixture\n', '# Fixture\n\n当前处于 Phase 2。\n'))),
            ('adr-index-mismatch', False, '与索引状态',
             lambda case: mutate(case, 'docs/ADR/README.md', '| 已接受 |', '| 已拒绝 |')),
            ('partial-without-scope', False, '替代范围', lambda case: (
                mutate(case, 'docs/ADR/0001-fixture.md', '- 状态：已接受', '- 状态：部分替代'),
                mutate(case, 'docs/ADR/README.md', '| 已接受 |', '| 部分替代 |'))),
            ('replaced-without-link', False, '缺少指向替代 ADR 的链接',
             lambda case: (
                 mutate(case, 'docs/ADR/0001-fixture.md', '- 状态：已接受', '- 状态：已替代'),
                 mutate(case, 'docs/ADR/README.md', '| 已接受 |', '| 已替代 |'))),
        ]

        for name, accepted, fragment, prepare in cases:
            case = Path(tmp) / f'case-{name}'
            shutil.copytree(fixture, case)
            prepare(case)
            if expect(case, accepted, fragment):
                print(f'PASS {name}')
            else:
                print(f'FAIL {name}')
                failures += 1

    if failures:
        print(f'{failures} governance test(s) failed')
        return 1
    print('governance-docs tests passed')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
