#!/usr/bin/env python3
"""Check setup failure propagation and check-only behavior without installing packages."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class SetupTests(unittest.TestCase):
    """Use disposable executable tool stubs, never the caller's venv or package manager."""

    def setUp(self):
        """Copy the real setup script into an isolated repository fixture."""
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / 'scripts').mkdir()
        shutil.copyfile(ROOT / 'scripts/jules-setup.sh', self.root / 'scripts/jules-setup.sh')
        self.bin = self.root / 'bin'
        self.bin.mkdir()
        self.log = self.root / 'calls'
        self.env = {**os.environ, 'PATH': str(self.bin) + os.pathsep + os.defpath,
                    'MOCK_BIN': str(self.bin), 'CALLS': str(self.log)}
        self.stub('uname', 'echo Linux')
        self.stub('node', 'exit 0')
        self.stub('git', 'exit 0')
        self.stub('shellcheck', 'exit 0')
        self.stub('venv-python', '''printf '%s\\n' "$*" >> "$CALLS"
if [[ "$*" == *pip* && ${FAIL_INSTALL:-0} == 1 ]]; then exit 17; fi
if [[ "$*" == scripts/governance-docs-check.py && ${FAIL_CHECK:-0} == 1 ]]; then exit 19; fi
''')
        self.stub('python3', '''printf 'python3 %s\\n' "$*" >> "$CALLS"
if [[ "$*" == '-m venv .venv/jules' ]]; then
  /bin/mkdir -p .venv/jules/bin
  /bin/cp "$MOCK_BIN/venv-python" .venv/jules/bin/python
fi
''')

    def stub(self, name, body):
        """Create a stub with a fixed interpreter to avoid recursive PATH resolution."""
        path = self.bin / name
        path.write_text('#!/bin/bash\nset -eu\n' + body + '\n', encoding='utf-8')
        path.chmod(0o755)

    def run_setup(self, *args):
        """Run actual shell control flow and return output plus tool calls."""
        result = subprocess.run(['/bin/bash', str(self.root / 'scripts/jules-setup.sh'), *args],
                                cwd=self.root, env=self.env, capture_output=True, text=True)
        calls = self.log.read_text() if self.log.exists() else ''
        return result, calls

    def test_non_linux_and_bad_arguments_do_not_install(self):
        """Unsupported hosts and misspelled modes stop before mutations."""
        self.stub('uname', 'echo Darwin')
        for args in ((), ('--unknown',), ('--check', 'extra')):
            with self.subTest(args=args):
                result, calls = self.run_setup(*args)
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertEqual(calls, '')
                self.assertFalse((self.root / '.venv').exists())

    def test_missing_snapshot_check_does_not_create_one(self):
        """A check-only run cannot silently install dependencies."""
        result, calls = self.run_setup('--check')
        self.assertEqual(result.returncode, 2)
        self.assertNotIn('-m venv', calls)
        self.assertFalse((self.root / '.venv').exists())

    def test_setup_then_check_runs_gates_without_reinstalling(self):
        """Successful setup enables check-only reuse, retaining the actual gate commands."""
        result, calls = self.run_setup()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('PyYAML==6.0.3', calls)
        self.log.unlink()
        result, calls = self.run_setup('--check')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn('pip', calls)
        self.assertNotIn('-m venv', calls)
        self.assertIn('tests/bot-dispatch.py', calls)

    def test_install_and_gate_failures_preserve_exit_codes(self):
        """Dependency or baseline failures must prevent a successful snapshot message."""
        for flag, code in (('FAIL_INSTALL', 17), ('FAIL_CHECK', 19)):
            with self.subTest(flag=flag):
                self.env.pop('FAIL_INSTALL', None)
                self.env[flag] = '1'
                self.log.unlink(missing_ok=True)
                result, calls = self.run_setup()
                self.assertEqual(result.returncode, code, result.stderr)
                self.assertNotIn('setup passed', result.stdout)
                self.assertNotIn('tests/bot-dispatch.py', calls)


if __name__ == '__main__':
    unittest.main()
