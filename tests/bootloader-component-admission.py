#!/usr/bin/env python3
"""Offline failure injection for component admission; all writes use disposable fixtures."""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import unittest
from unittest import mock

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


admission = module('admission', ROOT / 'scripts/check-bootloader-admission.py')
fixtures = module('fixtures', ROOT / 'tests/bootloader-source-audit.py')


class AdmissionTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.SourceAuditTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.root = Path(self.fixture.tmp.name)
        self.repo = self.fixture.repo
        self.lock = copy.deepcopy(self.fixture.lock)
        self.lock['upstream']['repository'] = 'https://example.invalid/fixture'
        self.manifest = admission.load(ROOT / admission.MANIFEST)
        self.manifest['source_lock'] = 'lock.json'
        self.manifest['observations'] = 'observations.json'
        (self.root / 'observations.json').write_text('{"repositories": {}}', encoding='utf-8')
        for component in self.manifest['components']:
            component['origin'] = dict(repository=self.lock['upstream']['repository'], paths=['LICENSE'], identity='source-lock')
            component['evidence'] = {'license': dict(kind='locked', path='LICENSE', sha256=None, bytes=None,
                                                    locator=self.lock['upstream']['repository'] + '/blob/' + self.lock['upstream']['revision'] + '/LICENSE')}
            component['source']['evidence'] = ['license']
            component['license']['evidence'] = ['license']
            component['artifacts'] = []
        self.save()

    def save(self):
        for path, value in [('manifest.json', self.manifest), ('lock.json', self.lock)]:
            (self.root / path).write_text(json.dumps(value), encoding='utf-8')

    def run_check(self):
        self.save()
        return admission.evaluate(self.root, 'manifest.json', self.repo.name)

    def evidence(self, name, raw):
        (self.root / name).write_bytes(raw)
        return dict(kind='local', path=name, sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw), locator='fixture review')

    def approve(self):
        self.lock['distribution']['combined_artifact_allowed'] = True
        self.lock['unlocked_dependencies'] = []
        for component in self.manifest['components']:
            component['source']['availability'] = 'complete'
            component['license']['unresolved'] = []
            component['blockers'] = []
            component['admission'] = dict(status='APPROVED', source_import=True, combined_build=True, distribution=True)
            for name, condition in component['conditions'].items():
                receipt = dict(schema_version=1, component=component['id'], condition=name, decision='verified',
                               source_identity=self.lock['upstream'], inputs=['license'], reviewer='synthetic fixture only',
                               explanation='Synthetic receipt exercises gates; never approves production inputs.')
                eid = 'review-' + name
                component['evidence'][eid] = self.evidence(component['id'] + '-' + name + '.json', json.dumps(receipt).encode())
                condition.update(result='verified', evidence=[eid])

    def test_real_manifest_schema_and_captured_text_hashes(self):
        manifest = admission.load(ROOT / admission.MANIFEST)
        lock = admission.load(ROOT / manifest['source_lock'])
        admission.validate(manifest, lock)
        admission.verify_observations(admission.load(ROOT / manifest['observations']))
        for c in manifest['components']:
            for e in c['evidence'].values():
                if e['kind'] == 'local':
                    raw = admission.local(ROOT, e['path']).read_bytes()
                    self.assertEqual(hashlib.sha256(raw).hexdigest(), e['sha256'])
                    self.assertEqual(len(raw), e['bytes'])

    def test_remote_tree_metadata_mutation_is_detected(self):
        observations = admission.load(ROOT / 'research/bootloader/evidence/github-observations-2026-10-23.json')
        trees = admission.load(ROOT / observations['tree_inventory']['path'])
        for name, rows in trees.items():
            with self.subTest(repository=name):
                self.assertEqual(admission.tree_identity(rows), observations['repositories'][name]['tree'])
                changed = copy.deepcopy(rows)
                changed[-1][2] = '0' * 40
                try:
                    self.assertNotEqual(admission.tree_identity(changed), observations['repositories'][name]['tree'])
                except ValueError:
                    pass
        changed = copy.deepcopy(observations)
        changed['repositories']['arc-lkm']['texts']['README.md']['text'] += 'tampered'
        with self.assertRaises(ValueError):
            admission.verify_observations(changed)

    def test_check_reports_holds_and_strict_fails(self):
        result = self.run_check()
        self.assertEqual(result['counts'], dict(APPROVED=0, BLOCKED=12, REVIEW_REQUIRED=4))
        self.assertFalse(result['strict_pass'])
        self.assertTrue(all(not c['source_import'] for c in result['components']))

    def test_complete_synthetic_receipts_can_pass(self):
        self.approve()
        self.assertTrue(self.run_check()['strict_pass'])

    def test_required_fields_mutation(self):
        for field in list(self.manifest['components'][0]):
            with self.subTest(field=field):
                value = self.manifest['components'][0].pop(field)
                with self.assertRaises(ValueError):
                    self.run_check()
                self.manifest['components'][0][field] = value

    def test_duplicate_or_unregistered_ids_fail(self):
        for value in (self.manifest['components'][1]['id'], 'not-registered'):
            self.manifest['components'][0]['id'] = value
            with self.assertRaises(ValueError):
                self.run_check()

    def test_duplicate_json_keys_fail(self):
        path = self.root / 'duplicate.json'
        path.write_text('{"id":1,"id":2}', encoding='utf-8')
        with self.assertRaises(ValueError):
            admission.load(path)

    def test_review_status_cannot_hide_unavailable_source(self):
        c = self.manifest['components'][0]
        c['source']['availability'] = 'unavailable'
        c['admission']['status'] = 'REVIEW_REQUIRED'
        with self.assertRaisesRegex(ValueError, 'REVIEW_REQUIRED'):
            self.run_check()

    def test_unknown_states_and_boolean_types_fail(self):
        c = self.manifest['components'][0]
        for value in ('approved', 'PENDING', None):
            c['admission']['status'] = value
            with self.assertRaises(ValueError):
                self.run_check()
        c['admission']['status'] = 'BLOCKED'
        c['admission']['distribution'] = 'false'
        with self.assertRaises(ValueError):
            self.run_check()

    def test_bad_sha_size_and_local_content_fail(self):
        c = self.manifest['components'][0]
        original = self.evidence('note.txt', b'evidence')
        for key, value in [('sha256', 'x' * 64), ('sha256', 'a' * 63), ('sha256', 'A' * 64),
                           ('bytes', True), ('bytes', -1), ('sha256', '0' * 64), ('bytes', 999)]:
            with self.subTest(key=key, value=value):
                c['evidence']['note'] = dict(original, **{key: value})
                with self.assertRaises(ValueError):
                    self.run_check()

    def test_manual_approved_and_gate_claims_fail(self):
        c = self.manifest['components'][0]
        c['admission']['status'] = 'APPROVED'
        with self.assertRaises(ValueError):
            self.run_check()
        c['admission']['status'] = 'REVIEW_REQUIRED'
        c['admission']['source_import'] = True
        with self.assertRaises(ValueError):
            self.run_check()

    def test_verified_flags_cannot_replace_subject_bound_receipts(self):
        c = self.manifest['components'][0]
        for condition in c['conditions'].values():
            condition.update(result='verified', evidence=['license'])
        with self.assertRaisesRegex(ValueError, 'receipt'):
            self.run_check()

    def test_remove_each_required_proof_blocks_approved(self):
        self.approve()
        baseline = copy.deepcopy(self.manifest)
        for name in self.manifest['components'][0]['conditions']:
            with self.subTest(condition=name):
                self.manifest = copy.deepcopy(baseline)
                self.manifest['components'][0]['conditions'][name]['result'] = 'missing'
                with self.assertRaises(ValueError):
                    self.run_check()
        for section, key, value in [('source', 'availability', 'unavailable'), ('source', 'evidence', []),
                                    ('license', 'evidence', []), ('license', 'unresolved', ['conflict'])]:
            self.manifest = copy.deepcopy(baseline)
            self.manifest['components'][0][section][key] = value
            with self.assertRaises(ValueError):
                self.run_check()

    def test_receipt_for_another_component_or_revision_fails(self):
        self.approve()
        c = self.manifest['components'][0]
        eid = 'review-source_complete'
        path = self.root / c['evidence'][eid]['path']
        receipt = json.loads(path.read_bytes())
        receipt['source_identity']['revision'] = '0' * 40
        c['evidence'][eid] = self.evidence(path.name, json.dumps(receipt).encode())
        with self.assertRaisesRegex(ValueError, 'identity'):
            self.run_check()

    def test_global_unlocked_inputs_cannot_be_bypassed(self):
        self.approve()
        self.lock['unlocked_dependencies'] = ['floating SDK']
        with self.assertRaises(ValueError):
            self.run_check()

    def test_source_lock_distribution_hold_cannot_be_bypassed(self):
        self.approve()
        self.lock['distribution']['combined_artifact_allowed'] = False
        with self.assertRaises(ValueError):
            self.run_check()

    def test_unlocked_or_placeholder_artifact_cannot_be_approved(self):
        self.approve()
        c = self.manifest['components'][0]
        for kind in ('unlocked_release', 'placeholder'):
            c['artifacts'] = [dict(path='release', kind=kind, evidence='license', source_relation='unknown')]
            with self.assertRaises(ValueError):
                self.run_check()

    def register_fixture_artifact(self):
        component = self.manifest['components'][0]
        path = 'binary with spaces'
        raw = (self.repo / path).read_bytes()
        component['evidence']['binary'] = dict(
            kind='git', path=path, sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw),
            locator=self.lock['upstream']['repository'] + '/blob/' + self.lock['upstream']['revision'] + '/' + path)
        component['artifacts'] = [dict(path=path, kind='pinned_blob', evidence='binary',
                                       source_relation='Synthetic artifact only')]
        return component

    def test_pinned_artifact_is_bound_to_exact_source_blob(self):
        self.approve()
        component = self.register_fixture_artifact()
        self.assertTrue(self.run_check()['strict_pass'])
        component['artifacts'][0]['evidence'] = 'license'
        with self.assertRaisesRegex(ValueError, 'artifact'):
            self.run_check()

    def test_local_receipt_cannot_impersonate_a_pinned_artifact(self):
        self.approve()
        component = self.register_fixture_artifact()
        raw = (self.repo / 'binary with spaces').read_bytes()
        component['evidence']['binary'] = self.evidence('binary with spaces', raw)
        with self.assertRaisesRegex(ValueError, 'artifact'):
            self.run_check()

    def test_pinned_artifact_path_cannot_escape_or_be_duplicated(self):
        self.approve()
        component = self.register_fixture_artifact()
        artifact = component['artifacts'][0]
        for path in ('../private', '/etc/passwd', 'C:/private', 'absent'):
            with self.subTest(path=path):
                artifact['path'] = path
                with self.assertRaises(ValueError):
                    self.run_check()
        artifact['path'] = 'binary with spaces'
        component['artifacts'].append(copy.deepcopy(artifact))
        with self.assertRaisesRegex(ValueError, 'artifact'):
            self.run_check()

    def test_placeholder_cannot_be_promoted_to_pinned_binary(self):
        manifest = admission.load(ROOT / admission.MANIFEST)
        lock = admission.load(ROOT / manifest['source_lock'])
        grub = next(c for c in manifest['components'] if c['id'] == 'grub')
        grub['artifacts'][0]['kind'] = 'pinned_blob'
        with self.assertRaisesRegex(ValueError, 'artifact'):
            admission.validate(manifest, lock)

    def test_verification_receipts_cannot_form_an_evidence_cycle(self):
        self.approve()
        component = self.manifest['components'][0]
        for name, other in (('source_complete', 'license_scope'), ('license_scope', 'source_complete')):
            eid = 'review-' + name
            path = component['evidence'][eid]['path']
            receipt = admission.load(self.root / path)
            receipt['inputs'] = ['review-' + other]
            component['evidence'][eid] = self.evidence(path, json.dumps(receipt).encode())
        with self.assertRaisesRegex(ValueError, 'circular'):
            self.run_check()

    def test_unavailable_origin_must_match_observed_repository_url(self):
        component = self.manifest['components'][0]
        component['origin'] = dict(repository='https://github.com/expected/unavailable',
                                   paths=['/'], identity='unresolved')
        component['source']['availability'] = 'unavailable'
        component['admission']['status'] = 'BLOCKED'
        observation = dict(repositories={}, unavailable={'unavailable': {
            'public': [dict(url=component['origin']['repository'], status=404)]}})
        (self.root / 'observations.json').write_text(json.dumps(observation), encoding='utf-8')
        self.assertFalse(self.run_check()['strict_pass'])
        component['origin']['repository'] = 'https://github.com/impostor/unavailable'
        with self.assertRaisesRegex(ValueError, 'origin'):
            self.run_check()

    def test_source_identity_mutation_fails(self):
        self.lock['upstream']['revision'] = '0' * 40
        with self.assertRaises((ValueError, subprocess.CalledProcessError)):
            self.run_check()

    def test_unsafe_paths_rejected_before_file_read(self):
        c = self.manifest['components'][0]
        for value in ('../secret', '/etc/passwd', 'C:/secret', 'a/../../secret', 'a\\b',
                      'a//b', './secret', 'file:stream', 'a/..'):
            with self.subTest(path=value):
                c['evidence']['note'] = dict(kind='local', path=value, sha256='0' * 64, bytes=0, locator='unsafe')
                with self.assertRaises(ValueError):
                    self.run_check()
        with self.assertRaises(ValueError):
            admission.local(self.root, str(ROOT / 'license.md'))

    def test_git_paths_cannot_be_revision_expressions(self):
        c = self.manifest['components'][0]
        for path in ('HEAD:LICENSE', '../LICENSE', ':LICENSE'):
            c['evidence']['evil'] = dict(kind='git', path=path, sha256='0' * 64, bytes=0, locator='unsafe')
            with self.assertRaises(ValueError):
                self.run_check()

    def test_external_gitdir_common_and_alternates_fail(self):
        info = self.repo / '.git/objects/info'
        info.mkdir(exist_ok=True)
        (info / 'alternates').write_text(str(ROOT / '.git/objects'), encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'alternates'):
            self.run_check()
        (info / 'alternates').unlink()
        (self.repo / '.git/commondir').write_text(str(ROOT / '.git'), encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'common'):
            self.run_check()
        (self.repo / '.git/commondir').unlink()
        other = self.root / 'external-source'
        other.mkdir()
        (other / '.git').write_text('gitdir: ' + str(ROOT / '.git'), encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'storage'):
            admission.evaluate(self.root, 'manifest.json', other.name)

    def test_git_config_include_is_rejected(self):
        with (self.repo / '.git/config').open('a', encoding='utf-8') as f:
            f.write('\n[include]\n path = /private/config\n')
        with self.assertRaisesRegex(ValueError, 'includes'):
            self.run_check()

    def test_local_fsmonitor_cannot_execute_a_helper(self):
        sentinel = self.root / 'helper-executed'
        self.fixture.git('config', 'core.fsmonitor', 'touch ' + str(sentinel))
        self.run_check()
        self.assertFalse(sentinel.exists())

    def test_worktree_config_include_is_rejected(self):
        (self.repo / '.git/config.worktree').write_text('[includeIf "gitdir:**"]\n path = /private/config\n', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'includes'):
            self.run_check()

    def test_original_path_must_exist_in_fixed_source(self):
        self.manifest['components'][0]['origin']['paths'] = ['does-not-exist']
        with self.assertRaisesRegex(ValueError, 'path absent'):
            self.run_check()

    def test_link_escape_rejected(self):
        link = self.root / 'outside'
        try:
            link.symlink_to(ROOT, target_is_directory=True)
        except OSError:
            if os.name != 'nt':
                raise
            subprocess.run(['cmd', '/c', 'mklink', '/J', str(link), str(ROOT)], check=True, capture_output=True)
        self.addCleanup(link.unlink if link.is_symlink() else link.rmdir)
        with self.assertRaises(ValueError):
            admission.local(self.root, 'outside/license.md')

    def test_no_lazy_fetch_and_no_pack_or_user_file_changes(self):
        self.fixture.git('config', 'uploadpack.allowFilter', 'true')
        partial = self.root / 'partial'
        subprocess.run(['git', 'clone', '-q', '--filter=blob:none', '--no-checkout',
                        self.repo.as_uri(), str(partial)], check=True, capture_output=True,
                       env=fixtures.fixture_git_environment())
        before = self.snapshot(partial)
        with self.assertRaises((ValueError, subprocess.CalledProcessError)):
            admission.evaluate(self.root, 'manifest.json', partial.name)
        self.assertEqual(before, self.snapshot(partial), 'lazy fetch or Git write occurred')

    @staticmethod
    def snapshot(root):
        return {str(p.relative_to(root)): (p.read_bytes(), p.stat().st_mtime_ns)
                for p in root.rglob('*') if p.is_file()}

    def test_environment_pollution_offline_and_read_only(self):
        self.save()
        before = self.snapshot(self.root)
        polluted = dict(GIT_DIR=str(ROOT / '.git'), GIT_WORK_TREE=str(ROOT), GIT_INDEX_FILE=str(ROOT / '.git/index'),
                        GIT_COMMON_DIR=str(ROOT / '.git'), GIT_OBJECT_DIRECTORY=str(ROOT / '.git/objects'),
                        GIT_CONFIG_COUNT='1', GIT_CONFIG_KEY_0='core.bare', GIT_CONFIG_VALUE_0='true',
                        GIT_CONFIG_GLOBAL='/nonexistent', GIT_SSH_COMMAND='exit 99')
        original = admission.audit.subprocess.check_output
        def offline_git(command, **kwargs):
            self.assertEqual(command[0], 'git')
            self.assertEqual(kwargs['env']['GIT_ALLOW_PROTOCOL'], '')
            self.assertEqual(kwargs['env']['GIT_NO_LAZY_FETCH'], '1')
            self.assertNotIn('GIT_DIR', kwargs['env'])
            return original(command, **kwargs)
        with mock.patch.dict(os.environ, polluted), mock.patch.object(socket, 'socket', side_effect=AssertionError('network forbidden')):
            with mock.patch.object(admission.audit.subprocess, 'check_output', side_effect=offline_git):
                self.assertFalse(admission.evaluate(self.root, 'manifest.json', self.repo.name)['strict_pass'])
        self.assertEqual(before, self.snapshot(self.root), 'inspection wrote source, objects, config or user data')

    def test_cli_modes_and_sanitized_error(self):
        with mock.patch.object(admission, 'ROOT', self.root):
            for mode, expected in [('--check', 0), ('--strict', 2)]:
                with mock.patch.object(sys, 'argv', ['admission', mode, '--manifest', 'manifest.json', '--source', self.repo.name]):
                    with mock.patch('builtins.print'):
                        self.assertEqual(admission.main(), expected)
            with mock.patch.object(sys, 'argv', ['admission', '--check', '--manifest', '../outside']):
                with mock.patch('builtins.print') as printer:
                    self.assertEqual(admission.main(), 1)
                    self.assertNotIn('fatal:', str(printer.call_args))


if __name__ == '__main__':
    unittest.main(verbosity=2)
