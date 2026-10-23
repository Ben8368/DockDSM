#!/usr/bin/env python3
"""Offline regression tests for CI planning, fail-closed gating and workflow wiring."""
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import yaml

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts' / f'{name}.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


planner = load('ci-plan')
gate = load('ci-result')
tree = load('check-tree')


def workflow(name):
    return yaml.load((ROOT / '.github/workflows' / name).read_text(encoding='utf-8'),
                     Loader=yaml.BaseLoader)


class PlanningTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.previous = Path.cwd()
        os.chdir(self.tmp.name)
        self.addCleanup(os.chdir, self.previous)
        self.git('init', '-q', '-b', 'master')
        self.git('config', 'user.name', 'Fixture')
        self.git('config', 'user.email', 'fixture@example.invalid')
        self.git('config', 'core.hooksPath', '.no-hooks')
        self.git('config', 'core.autocrlf', 'false')
        self.commit('readme.md', 'initial')
        self.initial = self.git('rev-parse', 'HEAD')

    def git(self, *args):
        return subprocess.check_output(['git', *args], text=True, stderr=subprocess.PIPE).strip()

    def commit(self, name, text):
        path = Path(name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text + '\n', encoding='utf-8')
        self.git('add', '--', name)
        self.git('commit', '-q', '-m', 'fixture')
        return self.git('rev-parse', 'HEAD')

    def decision(self, event='push', base=None, force=False):
        data = {'before': base or self.initial}
        if event == 'pull_request':
            data = {'pull_request': {'base': {'sha': base or self.initial}}}
        return planner.plan(event, data, self.git('rev-parse', 'HEAD'), force)

    def test_root_and_unknown_base_are_full(self):
        self.assertTrue(self.decision()['images'])
        self.commit('docs/guide.md', 'guide')
        for base in ('0' * 40, 'a' * 40, '--bad'):
            with self.subTest(base=base):
                self.assertTrue(self.decision(base=base)['images'])

    def test_documentation_only_push_and_pr(self):
        self.commit('docs/guide.md', 'guide')
        for event in ('push', 'pull_request'):
            with self.subTest(event=event):
                result = self.decision(event)
                self.assertFalse(result['images'])
                self.assertEqual(result['reason'], 'documentation-only')

    def test_code_config_and_test_changes_are_full(self):
        for name in ('src/a.sh', 'Dockerfile', '.github/workflows/test.yml', 'tests/a.py',
                     'requirements.txt', 'compose.yml'):
            base = self.git('rev-parse', 'HEAD')
            self.commit(name, 'fixture')
            self.assertTrue(self.decision(base=base)['images'], name)

    def test_multi_commit_push_checks_entire_range(self):
        self.commit('src/a.sh', 'code')
        self.commit('docs/guide.md', 'guide')
        self.assertTrue(self.decision()['images'])

    def test_code_renamed_to_documentation_cannot_hide(self):
        self.commit('src/a.sh', 'code')
        base = self.git('rev-parse', 'HEAD')
        self.git('mv', 'src/a.sh', 'code.md')
        self.git('commit', '-q', '-m', 'rename')
        self.assertTrue(self.decision(base=base)['images'])

    def test_manual_release_and_explicit_full(self):
        self.commit('docs/guide.md', 'guide')
        for event in ('workflow_dispatch', 'workflow_call', 'schedule', 'unknown'):
            self.assertTrue(self.decision(event)['images'])
        self.assertTrue(self.decision(force=True)['images'])

    def test_rewritten_root_is_full_even_if_old_base_available(self):
        head_tree = self.git('rev-parse', 'HEAD^{tree}')
        self.git('update-ref', 'refs/heads/master',
                 self.git('commit-tree', head_tree, '-m', 'new root'))
        self.assertTrue(self.decision()['images'])


class GateTests(unittest.TestCase):
    def needs(self, images='true'):
        jobs = {name: {'result': 'success'} for name in gate.REQUIRED}
        jobs['plan']['outputs'] = {'images': images}
        if images == 'false':
            jobs['images']['result'] = 'skipped'
        return jobs

    def test_full_and_docs_success(self):
        for images in ('true', 'false'):
            self.assertEqual(gate.failures(self.needs(images)), [])

    def test_each_failure_cancel_skip_and_missing_fails_closed(self):
        for job in gate.REQUIRED:
            for result in ('failure', 'cancelled', 'skipped', 'missing'):
                needs = self.needs()
                needs[job]['result'] = result
                self.assertTrue(gate.failures(needs), (job, result))
        needs = self.needs()
        del needs['tests']
        self.assertTrue(gate.failures(needs))

    def test_invalid_plan_and_unexpected_image_skip(self):
        for value in ('', 'True', 'unknown'):
            self.assertTrue(gate.failures(self.needs(value)))
        needs = self.needs('false')
        needs['images']['result'] = 'success'
        self.assertTrue(gate.failures(needs))

    def test_gate_process_exits_nonzero_on_failed_tests(self):
        needs = self.needs()
        needs['tests']['result'] = 'failure'
        result = subprocess.run([sys.executable,
                                 str(ROOT / 'scripts/ci-result.py')],
                                env={**os.environ, 'CI_NEEDS': json.dumps(needs)},
                                capture_output=True)
        self.assertNotEqual(result.returncode, 0)


class TreeTests(unittest.TestCase):
    def test_lf_utf8_and_whitespace(self):
        self.assertEqual(tree.check('guide.md', b'hello\n'), [])
        self.assertTrue(tree.check('guide.md', b'hello \n'))
        self.assertTrue(tree.check('a.sh', b'echo hi\r\n'))
        self.assertTrue(tree.check('a.py', b'\xff'))
        self.assertTrue(tree.check('a.md', b'\xef\xbb\xbfhello'))
        self.assertEqual(tree.check('screen.jpg', b'\xff\x00'), [])

    def check_fixture(self, *, initialized=False, missing=False, bad_text=False):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            def git(*args):
                return subprocess.check_output(['git', *args], cwd=root,
                                               stderr=subprocess.PIPE, text=True).strip()

            git('init', '-q')
            git('-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid',
                '-c', 'core.hooksPath=.no-hooks', 'commit', '-q', '--allow-empty', '-m', 'fixture')
            revision = git('rev-parse', 'HEAD')
            name = 'guide with spaces.md'
            (root / name).write_bytes(b'hello \n' if bad_text else b'hello\n')
            git('-c', 'core.autocrlf=false', 'add', '--', name)
            git('update-index', '--add', '--cacheinfo', '160000', revision, 'vendor/arc with spaces')
            if initialized:
                nested = root / 'vendor/arc with spaces'
                nested.mkdir(parents=True)
                subprocess.run(['git', 'init', '-q', str(nested)], check=True,
                               capture_output=True)
                (nested / 'ignored.md').write_bytes(b'inherited tree \r\n')
            if missing:
                (root / name).unlink()
            stdout, stderr = io.StringIO(), io.StringIO()
            with mock.patch.object(tree, 'ROOT', root), contextlib.redirect_stdout(stdout), \
                    contextlib.redirect_stderr(stderr):
                code = tree.main()
            return code, stderr.getvalue()

    def test_uninitialized_gitlink_is_not_a_missing_file(self):
        self.assertEqual(self.check_fixture(), (0, ''))

    def test_initialized_gitlink_is_not_scanned_as_a_regular_file(self):
        self.assertEqual(self.check_fixture(initialized=True), (0, ''))

    def test_gitlink_does_not_hide_missing_regular_files(self):
        code, errors = self.check_fixture(missing=True)
        self.assertEqual(code, 1)
        self.assertIn('guide with spaces.md: tracked file is missing', errors)

    def test_gitlink_does_not_hide_invalid_regular_text(self):
        code, errors = self.check_fixture(bad_text=True)
        self.assertEqual(code, 1)
        self.assertIn('guide with spaces.md:1: trailing whitespace', errors)

    def test_patch_context_is_preserved(self):
        self.assertEqual(tree.check('a.patch', b' \n+code\n'), [])


class WiringTests(unittest.TestCase):
    def test_gate_dependencies_and_scopes(self):
        ci = workflow('test.yml')
        self.assertEqual(set(ci['jobs']['result']['needs']), gate.REQUIRED)
        self.assertEqual(ci['jobs']['result']['if'], 'always()')
        self.assertEqual(ci['jobs']['images']['if'], "needs.plan.outputs.images == 'true'")
        self.assertEqual(ci['permissions'], {'contents': 'read'})
        self.assertIn('push', ci['on'])
        self.assertIn('pull_request', ci['on'])
        self.assertNotIn('pull_request_target', ci['on'])
        self.assertEqual(ci['on']['workflow_call']['inputs']['full']['default'], 'true')
        self.assertEqual(ci['jobs']['plan']['steps'][0]['with']['fetch-depth'], '0')

    def test_publication_forces_full_validation(self):
        publish = workflow('build.yml')
        self.assertEqual(set(publish['on']), {'workflow_dispatch'})
        self.assertEqual(publish['jobs']['checks']['with']['full'], 'true')
        self.assertIn('checks', publish['jobs']['publish']['needs'])
        self.assertEqual(publish['jobs']['publish']['permissions']['packages'], 'write')
        self.assertFalse((ROOT / '.github/workflows/hub.yml').exists())

    def test_native_architectures_and_bot_policy(self):
        ci = workflow('test.yml')
        images = workflow('arm-qemu-build.yml')
        for job in (ci['jobs']['tests'], images['jobs']['image']):
            arches = {item['arch'] for item in job['strategy']['matrix']['include']}
            self.assertEqual(arches, {'amd64', 'arm64'})
        deps = yaml.load((ROOT / '.github/dependabot.yml').read_text(encoding='utf-8'),
                         Loader=yaml.BaseLoader)
        self.assertTrue(all(item['open-pull-requests-limit'] == '0' for item in deps['updates']))


if __name__ == '__main__':
    unittest.main()
