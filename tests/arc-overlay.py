#!/usr/bin/env python3
"""Offline Git fixtures for the pinned research overlay; no upstream downloads."""
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'research/arc/apply-patches.sh'


class OverlayTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='dockdsm overlay ')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.arc = self.root / 'vendor/arc'
        self.arc.mkdir(parents=True)
        self.git('init', '-q')
        self.git('config', 'user.name', 'Fixture')
        self.git('config', 'user.email', 'fixture@example.invalid')
        self.git('config', 'core.hooksPath', '.no-hooks')
        self.git('config', 'core.autocrlf', 'false')
        (self.arc / 'marker.txt').write_text('before\n', encoding='utf-8')
        self.git('add', 'marker.txt')
        self.git('commit', '-qm', 'fixture')
        revision = self.git('rev-parse', 'HEAD')
        self.script = self.root / 'research/arc/apply-patches.sh'
        self.script.parent.mkdir(parents=True)
        source = SCRIPT.read_text(encoding='utf-8')
        # Replace only the pinned input in an isolated script copy. All Git/path
        # handling under test is the repository implementation.
        source, count = re.subn(r'(?m)^EXPECTED_REV="[0-9a-f]{40}"$',
                                f'EXPECTED_REV="{revision}"', source)
        self.assertEqual(count, 1)
        self.script.write_text(source, encoding='utf-8')
        patch = self.root / 'patches/arc/0001-show-model-architecture.patch'
        patch.parent.mkdir(parents=True)
        patch.write_text('diff --git a/marker.txt b/marker.txt\n'
                         '--- a/marker.txt\n+++ b/marker.txt\n'
                         '@@ -1 +1 @@\n-before\n+after\n', encoding='utf-8')

    def git(self, *args):
        return subprocess.check_output(['git', '-C', str(self.arc), *args],
                                       text=True, stderr=subprocess.PIPE).strip()

    def run_overlay(self, *args, cwd=None):
        return subprocess.run(['bash', str(self.script), *map(str, args)],
                              cwd=cwd or self.root, text=True, capture_output=True)

    def assert_applied(self, path, *args, cwd=None):
        result = self.run_overlay(*args, cwd=cwd)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('Applied DockDSM ARC patch', result.stdout)
        self.assertEqual((path / 'marker.txt').read_text(), 'after\n')
        repeated = self.run_overlay(*args, cwd=cwd)
        self.assertEqual(repeated.returncode, 0, repeated.stdout + repeated.stderr)
        self.assertIn('already applied', repeated.stdout)

    def test_default_path_from_another_directory(self):
        self.assert_applied(self.arc, cwd=self.root / 'research')

    def test_relative_path(self):
        self.assert_applied(self.arc, 'vendor/arc')

    def test_absolute_path_with_spaces(self):
        self.assert_applied(self.arc, self.arc)

    def test_relative_linked_worktree_git_file(self):
        linked = self.root / 'linked arc'
        self.git('worktree', 'add', '--detach', str(linked), 'HEAD')
        self.assertTrue((linked / '.git').is_file())
        self.assert_applied(linked, 'linked arc')
        self.assertEqual((self.arc / 'marker.txt').read_text(), 'before\n')

    def test_relative_submodule_git_file(self):
        parent = self.root / 'parent'
        subprocess.run(['git', 'init', '-q', str(parent)], check=True, capture_output=True)
        subprocess.run(['git', '-c', 'protocol.file.allow=always', '-C', str(parent),
                        'submodule', 'add', str(self.arc), 'nested arc'],
                       check=True, capture_output=True)
        nested = parent / 'nested arc'
        self.assertTrue((nested / '.git').read_text().startswith('gitdir: ../'))
        self.assert_applied(nested, 'parent/nested arc')

    def test_missing_checkout_rejected(self):
        result = self.run_overlay('missing arc')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('submodule is missing', result.stderr)
        self.assertEqual((self.arc / 'marker.txt').read_text(), 'before\n')

    def test_wrong_revision_rejected_without_changes(self):
        self.git('commit', '--allow-empty', '-qm', 'wrong revision')
        result = self.run_overlay(self.arc)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('revision mismatch', result.stderr)
        self.assertEqual((self.arc / 'marker.txt').read_text(), 'before\n')

    def test_conflicting_worktree_rejected_without_changes(self):
        (self.arc / 'marker.txt').write_text('local work\n', encoding='utf-8')
        result = self.run_overlay(self.arc)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('does not apply cleanly', result.stderr)
        self.assertEqual((self.arc / 'marker.txt').read_text(), 'local work\n')


if __name__ == '__main__':
    unittest.main(verbosity=2)
