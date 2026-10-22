#!/usr/bin/env python3
"""Execute the actual issue dispatcher with mocked GitHub APIs; never dispatch live."""
import copy
import json
from pathlib import Path
import shutil
import subprocess
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = yaml.load((ROOT / '.github/workflows/bot-dispatch.yml').read_text(encoding='utf-8'),
                     Loader=yaml.BaseLoader)
SCRIPT = WORKFLOW['jobs']['dispatch']['steps'][0]['with']['script']
NODE = shutil.which('node') or shutil.which('node.exe')
HARNESS = r'''
let data = '';
process.stdin.setEncoding('utf8');
process.stdin.on('data', chunk => data += chunk);
process.stdin.on('end', async () => {
  const input = JSON.parse(data);
  const calls = [];
  const github = {rest: {
    issues: {
      get: async () => ({data: input.issue}),
      addLabels: async args => {calls.push({kind: 'label', args});}
    },
    repos: {getCollaboratorPermissionLevel: async args => {
      calls.push({kind: 'permission', username: args.username});
      if (input.permissionError) throw Error('permission lookup failed');
      return {data: {permission: input.permissions[args.username] || 'read'}};
    }}
  }};
  const context = {repo: {owner: 'fixture-owner', repo: 'fixture-repo'}, actor: input.actor,
    payload: {issue: {number: 42}}};
  try {
    const AsyncFunction = Object.getPrototypeOf(async function () {}).constructor;
    await new AsyncFunction('github', 'context', 'core', input.script)(github, context, {info: () => {}});
    console.log(JSON.stringify({calls}));
  } catch (error) {
    console.log(JSON.stringify({calls, error: error.message}));
  }
});
'''


class DispatchTests(unittest.TestCase):
    def setUp(self):
        self.body = ('### Task category\n\nDocumentation\n\n'
                     '### Allowed paths\n\nreadme.md\n\n'
                     '### Requested change\n\nFix the documented typo.\n\n'
                     '### Validation command\n\npython3 scripts/governance-docs-check.py\n\n'
                     '### Authorization\n\n- [x] I authorize Jules to implement only this scoped task.')
        self.input = {'script': SCRIPT, 'actor': 'maintainer',
                      'permissions': {'maintainer': 'admin'},
                      'issue': {'number': 42, 'state': 'open', 'user': {'login': 'maintainer'},
                                'labels': [{'name': 'bot:request'}], 'body': self.body}}

    def run_dispatch(self, expected):
        self.assertIsNotNone(NODE, 'Node.js is required to execute the github-script regression')
        result = subprocess.run([NODE, '-e', HARNESS], input=json.dumps(self.input),
                                text=True, encoding='utf-8', capture_output=True, check=True)
        output = json.loads(result.stdout)
        labels = [call for call in output['calls'] if call['kind'] == 'label']
        self.assertEqual(len(labels), int(expected), output)
        if expected:
            self.assertEqual(labels[0]['args'], {'owner': 'fixture-owner', 'repo': 'fixture-repo',
                                                'issue_number': 42, 'labels': ['jules']})
        return output

    def test_authorized_documentation_and_test_requests(self):
        for category, paths in [('Documentation', 'readme.md'),
                                ('Tests', 'tests/platform.sh\ntests/healthcheck.sh')]:
            with self.subTest(category=category):
                self.input['issue']['body'] = self.body.replace('Documentation', category).replace('readme.md', paths)
                self.run_dispatch(True)

    def test_live_permission_is_required_for_author_and_actor(self):
        for target in ('actor', 'author'):
            with self.subTest(target=target):
                saved = copy.deepcopy(self.input)
                if target == 'actor':
                    self.input['actor'] = 'outsider'
                else:
                    self.input['issue']['user']['login'] = 'outsider'
                    self.input['issue']['author_association'] = 'OWNER'
                self.run_dispatch(False)
                self.input = saved

    def test_bot_cannot_dispatch(self):
        self.input['actor'] = 'github-actions[bot]'
        self.input['permissions'][self.input['actor']] = 'admin'
        self.run_dispatch(False)

    def test_closed_pull_request_and_removed_request_label(self):
        for patch in ({'state': 'closed'}, {'pull_request': {}}, {'labels': []}):
            with self.subTest(patch=patch):
                original = copy.deepcopy(self.input['issue'])
                self.input['issue'].update(patch)
                self.run_dispatch(False)
                self.input['issue'] = original

    def test_protected_and_already_dispatched_tasks(self):
        for name in ('risk:high', 'security', 'data-loss', 'arm64', 'qemu',
                     'needs:hardware-test', 'hardware-testing', 'phase-acceptance',
                     'agent:codex', 'jules', 'dependencies', 'ci'):
            with self.subTest(name=name):
                self.input['issue']['labels'] = [{'name': 'bot:request'}, {'name': name}]
                self.run_dispatch(False)

    def test_paths_are_literal_and_limited(self):
        for path in ('src/install.sh', '.github/workflows/test.yml', '../readme.md',
                     'tests/../src/install.sh', 'tests/**', 'tests/a.py;echo x',
                     'docs/AI_RULES.md', 'docs/ADR/0008-test.md', 'docs/ci.md',
                     'docs/platforms.md', 'tests/qemu-patches.sh', 'docs/archive/test.md',
                     'tests/a.py\ntests/b.py\ntests/c.py\ntests/d.py', ''):
            with self.subTest(path=path):
                self.input['issue']['body'] = self.body.replace('readme.md', path)
                self.run_dispatch(False)

    def test_missing_fields_approval_and_ambiguous_headings(self):
        for body in (None, '', self.body.replace('[x]', '[ ]'),
                     self.body.replace('Documentation', 'Runtime'),
                     self.body.replace('### Validation command', '### Missing command'),
                     self.body + '\n### Allowed paths\nreadme.md'):
            with self.subTest(body=body):
                self.input['issue']['body'] = body
                self.run_dispatch(False)

    def test_crlf_issue_body(self):
        self.input['issue']['body'] = self.body.replace('\n', '\r\n')
        self.run_dispatch(True)

    def test_api_failure_stops_without_label(self):
        self.input['permissionError'] = True
        output = self.run_dispatch(False)
        self.assertIn('permission lookup failed', output['error'])

    def test_workflow_uses_minimal_permissions_and_no_checkout(self):
        self.assertEqual(WORKFLOW['permissions'], {'issues': 'write'})
        self.assertEqual(WORKFLOW['on']['issues']['types'], ['opened', 'labeled', 'reopened'])
        self.assertEqual(len(WORKFLOW['jobs']['dispatch']['steps']), 1)
        self.assertRegex(WORKFLOW['jobs']['dispatch']['steps'][0]['uses'],
                         r'^actions/github-script@[0-9a-f]{40}$')
        self.assertNotIn('$' + '{{', SCRIPT)
        template = yaml.safe_load((ROOT / '.github/ISSUE_TEMPLATE/0-bot-task.yml').read_text(encoding='utf-8'))
        self.assertEqual(template['labels'], ['bot:request'])


if __name__ == '__main__':
    unittest.main()
