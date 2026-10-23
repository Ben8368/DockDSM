#!/usr/bin/env python3
"""Verify source identity, read-only auditing and incomplete-history reporting."""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('source_audit', ROOT / 'scripts/audit-bootloader-source.py')
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


def fixture_git_environment():
    """Keep fixture writes local, ignoring caller Git locations and configuration."""
    env = {key: value for key, value in os.environ.items()
           if not key.startswith('GIT_')}
    env.update(GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL=os.devnull,
               GIT_ALLOW_PROTOCOL='file', GIT_NO_LAZY_FETCH='1')
    return env


class SourceAuditTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='dockdsm source ')
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name) / 'source with spaces'
        self.repo.mkdir()
        self.git('init', '-q')
        self.git('config', 'core.hooksPath', '.no-hooks')
        self.git('config', 'core.autocrlf', 'false')
        self.git('config', 'user.name', 'Fixture')
        self.git('config', 'user.email', 'fixture@example.invalid')
        raw = b'fixture license\n'
        (self.repo / 'LICENSE').write_bytes(raw)
        # Never execute anything in the inherited source, even build entrypoints.
        (self.repo / 'img-gen.sh').write_bytes(b'exit 99\n')
        (self.repo / 'binary with spaces').write_bytes(b'\x7fELF\x00' * 50)
        self.git('add', '.')
        self.git('commit', '-qm', 'fixture')
        self.lock = dict(schema_version=1,
                         upstream=dict(repository='fixture', revision=self.git('rev-parse', 'HEAD'),
                                       tree=self.git('rev-parse', 'HEAD^{tree}')),
                         snapshot=dict(entries=3, blob_bytes=274),
                         evidence={'LICENSE': dict(sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw))},
                         distribution=dict(combined_artifact_allowed=False),
                         unlocked_dependencies=['fixture-buildroot'])

    def git(self, *args):
        return subprocess.check_output(['git', '-C', str(self.repo), *args],
                                       env=fixture_git_environment(),
                                       stderr=subprocess.PIPE, text=True).strip()

    def test_valid_audit_reports_binary_size_and_preserves_worktree(self):
        before = self.git('status', '--porcelain')
        result = audit.inventory(self.repo, self.lock)
        self.assertEqual(result['snapshot'], self.lock['snapshot'])
        self.assertEqual(result['largest'][0]['path'], 'binary with spaces')
        self.assertFalse(result['distribution']['combined_artifact_allowed'])
        self.assertFalse(result['local_history']['shallow'])
        self.assertFalse(result['local_history']['upstream_history_verified'])
        self.assertEqual(before, self.git('status', '--porcelain'))

    def test_dirty_worktree_cannot_replace_pinned_license_evidence(self):
        (self.repo / 'LICENSE').write_bytes(b'local text\n')
        result = audit.inventory(self.repo, self.lock)
        self.assertEqual(result['evidence_verified'], ['LICENSE'])
        self.assertEqual((self.repo / 'LICENSE').read_bytes(), b'local text\n')

    def test_wrong_head_fails(self):
        self.git('commit', '--allow-empty', '-qm', 'different revision')
        with self.assertRaisesRegex(ValueError, 'HEAD'):
            audit.inventory(self.repo, self.lock)

    def test_lock_tampering_fails(self):
        for field in ('tree', 'size', 'digest', 'schema'):
            with self.subTest(field=field):
                lock = copy.deepcopy(self.lock)
                if field == 'tree':
                    lock['upstream']['tree'] = '0' * 40
                elif field == 'size':
                    lock['snapshot']['blob_bytes'] += 1
                elif field == 'schema':
                    lock['schema_version'] = 2
                else:
                    lock['evidence']['LICENSE']['sha256'] = '0' * 64
                with self.assertRaises(ValueError):
                    audit.inventory(self.repo, lock)

    def test_shallow_clone_does_not_claim_complete_history(self):
        shallow = Path(self.tmp.name) / 'shallow'
        subprocess.run(['git', 'clone', '-q', '--depth=1', self.repo.as_uri(), str(shallow)],
                       check=True, capture_output=True, env=fixture_git_environment())
        result = audit.inventory(shallow, self.lock)
        self.assertTrue(result['local_history']['shallow'])
        self.assertFalse(result['local_history']['upstream_history_verified'])

    def test_partial_clone_cannot_fetch_missing_blobs(self):
        self.git('config', 'uploadpack.allowFilter', 'true')
        partial = Path(self.tmp.name) / 'partial'
        subprocess.run(['git', 'clone', '-q', '--filter=blob:none', '--no-checkout',
                        self.repo.as_uri(), str(partial)], check=True, capture_output=True,
                       env=fixture_git_environment())
        # A successful audit would mean Git silently fetched missing source blobs.
        with self.assertRaises((ValueError, subprocess.CalledProcessError)):
            audit.inventory(partial, self.lock)

    def test_polluted_environment_preserves_callers_repository(self):
        """Exercise setup, helper writes and both clones under foreign Git settings."""
        caller = Path(self.tmp.name) / 'caller repository'
        subprocess.run(['git', 'clone', '-q', self.repo.as_uri(), str(caller)],
                       check=True, capture_output=True, env=fixture_git_environment())
        (caller / 'untracked sentinel').write_bytes(b'keep caller data\n')
        (caller / 'LICENSE').write_bytes(b'uncommitted caller changes\n')

        def snapshot():
            return {str(path.relative_to(caller)): path.read_bytes()
                    for path in caller.rglob('*') if path.is_file()}

        before = snapshot()
        polluted = dict(os.environ, GIT_DIR=str(caller / '.git'),
                        GIT_WORK_TREE=str(caller), GIT_COMMON_DIR=str(caller / '.git'),
                        GIT_INDEX_FILE=str(caller / '.git/index'),
                        GIT_OBJECT_DIRECTORY=str(caller / '.git/objects'),
                        GIT_CONFIG_COUNT='1', GIT_CONFIG_KEY_0='core.bare',
                        GIT_CONFIG_VALUE_0='true')
        # Select only these tests so the child cannot recurse into this test.
        selected = ['test_valid_audit_reports_binary_size_and_preserves_worktree',
                    'test_shallow_clone_does_not_claim_complete_history',
                    'test_partial_clone_cannot_fetch_missing_blobs']
        result = subprocess.run(
            [os.sys.executable, str(Path(__file__).resolve()),
             *['SourceAuditTests.' + name for name in selected]],
            env=polluted, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('Ran 3 tests', result.stderr)
        self.assertEqual(before, snapshot(), 'fixture modified the caller repository')

    def test_inherited_git_environment_cannot_redirect_inspection(self):
        with mock.patch.dict(os.environ, {'GIT_DIR': '/missing', 'GIT_WORK_TREE': '/missing'}):
            self.assertEqual(audit.inventory(self.repo, self.lock)['snapshot'], self.lock['snapshot'])

    def test_cli_mismatch_fails_without_git_diagnostics(self):
        lock_path = Path(self.tmp.name) / 'lock.json'
        lock_path.write_text(json.dumps(self.lock), encoding='utf-8')
        result = subprocess.run(
            [os.sys.executable, str(ROOT / 'scripts/audit-bootloader-source.py'),
             '--source', self.tmp.name, '--lock', str(lock_path)],
            text=True, capture_output=True)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, '')
        self.assertIn('Git source inspection failed', result.stderr)
        self.assertNotIn('fatal:', result.stderr)

    def test_cli_malformed_lock_fails_closed(self):
        lock_path = Path(self.tmp.name) / 'invalid.json'
        lock_path.write_text('{', encoding='utf-8')
        result = subprocess.run(
            [os.sys.executable, str(ROOT / 'scripts/audit-bootloader-source.py'),
             '--source', str(self.repo), '--lock', str(lock_path)],
            text=True, capture_output=True)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, '')
        self.assertIn('Bootloader source audit failed', result.stderr)

    def test_repository_lock_remains_a_distribution_hold(self):
        lock = json.loads(audit.DEFAULT_LOCK.read_text(encoding='utf-8'))
        self.assertFalse(lock['distribution']['combined_artifact_allowed'])
        self.assertIn('arc-buildroot-essential', lock['unlocked_dependencies'])
        self.assertEqual(lock['upstream']['revision'], '99195dbdf4e0a21c5304ddb06e07dc57419679bc')


if __name__ == '__main__':
    unittest.main(verbosity=2)
