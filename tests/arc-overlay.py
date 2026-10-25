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
        (self.arc / 'marker2.txt').write_text('before\n', encoding='utf-8')
        (self.arc / 'marker3.txt').write_text('before\n', encoding='utf-8')
        (self.arc / 'marker4.txt').write_text('before\n', encoding='utf-8')
        (self.arc / 'marker5.txt').write_text('before\n', encoding='utf-8')
        (self.arc / 'marker6.txt').write_text('before\n', encoding='utf-8')
        self.git('add', 'marker.txt', 'marker2.txt', 'marker3.txt', 'marker4.txt',
                 'marker5.txt', 'marker6.txt')
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
        second_patch = patch.parent / '0002-arm64-grub-menu.patch'
        second_patch.write_text('diff --git a/marker2.txt b/marker2.txt\n'
                                '--- a/marker2.txt\n+++ b/marker2.txt\n'
                                '@@ -1 +1 @@\n-before\n+after\n', encoding='utf-8')
        third_patch = patch.parent / '0003-arm64-grub-esp.patch'
        third_patch.write_text('diff --git a/marker3.txt b/marker3.txt\n'
                               '--- a/marker3.txt\n+++ b/marker3.txt\n'
                               '@@ -1 +1 @@\n-before\n+after\n', encoding='utf-8')
        fourth_patch = patch.parent / '0004-dockdsm-ui-branding.patch'
        fourth_patch.write_text('diff --git a/marker4.txt b/marker4.txt\n'
                                '--- a/marker4.txt\n+++ b/marker4.txt\n'
                                '@@ -1 +1 @@\n-before\n+after\n', encoding='utf-8')
        fifth_patch = patch.parent / '0005-arm64-grub-workflow.patch'
        fifth_patch.write_text('diff --git a/marker5.txt b/marker5.txt\n'
                               '--- a/marker5.txt\n+++ b/marker5.txt\n'
                               '@@ -1 +1 @@\n-before\n+after\n', encoding='utf-8')
        sixth_patch = patch.parent / '0006-arm64-update-workflow.patch'
        sixth_patch.write_text('diff --git a/marker6.txt b/marker6.txt\n'
                               '--- a/marker6.txt\n+++ b/marker6.txt\n'
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
        self.assertEqual((path / 'marker2.txt').read_text(), 'after\n')
        self.assertEqual((path / 'marker3.txt').read_text(), 'after\n')
        self.assertEqual((path / 'marker4.txt').read_text(), 'after\n')
        self.assertEqual((path / 'marker5.txt').read_text(), 'after\n')
        self.assertEqual((path / 'marker6.txt').read_text(), 'after\n')
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
        self.assertEqual((self.arc / 'marker2.txt').read_text(), 'before\n')
        self.assertEqual((self.arc / 'marker3.txt').read_text(), 'before\n')
        self.assertEqual((self.arc / 'marker4.txt').read_text(), 'before\n')
        self.assertEqual((self.arc / 'marker5.txt').read_text(), 'before\n')

    def test_conflicting_worktree_rejected_without_changes(self):
        (self.arc / 'marker.txt').write_text('local work\n', encoding='utf-8')
        result = self.run_overlay(self.arc)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('does not apply cleanly', result.stderr)
        self.assertEqual((self.arc / 'marker.txt').read_text(), 'local work\n')
        self.assertEqual((self.arc / 'marker2.txt').read_text(), 'before\n')
        self.assertEqual((self.arc / 'marker3.txt').read_text(), 'before\n')
        self.assertEqual((self.arc / 'marker4.txt').read_text(), 'before\n')
        self.assertEqual((self.arc / 'marker5.txt').read_text(), 'before\n')

    def test_second_patch_conflict_does_not_partially_apply_first(self):
        (self.arc / 'marker2.txt').write_text('local work\n', encoding='utf-8')
        result = self.run_overlay(self.arc)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('0002-arm64-grub-menu.patch', result.stderr)
        self.assertIn('does not apply cleanly', result.stderr)
        self.assertEqual((self.arc / 'marker.txt').read_text(), 'before\n')
        self.assertEqual((self.arc / 'marker2.txt').read_text(), 'local work\n')
        self.assertEqual((self.arc / 'marker3.txt').read_text(), 'before\n')
        self.assertEqual((self.arc / 'marker4.txt').read_text(), 'before\n')
        self.assertEqual((self.arc / 'marker5.txt').read_text(), 'before\n')

    def test_third_patch_conflict_does_not_partially_apply_earlier_patches(self):
        (self.arc / 'marker3.txt').write_text('local work\n', encoding='utf-8')
        result = self.run_overlay(self.arc)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('0003-arm64-grub-esp.patch', result.stderr)
        self.assertIn('does not apply cleanly', result.stderr)
        self.assertEqual((self.arc / 'marker.txt').read_text(), 'before\n')
        self.assertEqual((self.arc / 'marker2.txt').read_text(), 'before\n')
        self.assertEqual((self.arc / 'marker3.txt').read_text(), 'local work\n')
        self.assertEqual((self.arc / 'marker4.txt').read_text(), 'before\n')

    def test_fourth_patch_conflict_does_not_partially_apply_earlier_patches(self):
        (self.arc / 'marker4.txt').write_text('local work\n', encoding='utf-8')
        result = self.run_overlay(self.arc)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('0004-dockdsm-ui-branding.patch', result.stderr)
        self.assertIn('does not apply cleanly', result.stderr)
        self.assertEqual((self.arc / 'marker.txt').read_text(), 'before\n')
        self.assertEqual((self.arc / 'marker2.txt').read_text(), 'before\n')
        self.assertEqual((self.arc / 'marker3.txt').read_text(), 'before\n')
        self.assertEqual((self.arc / 'marker4.txt').read_text(), 'local work\n')
        self.assertEqual((self.arc / 'marker5.txt').read_text(), 'before\n')

    def test_fifth_patch_conflict_does_not_partially_apply_earlier_patches(self):
        (self.arc / 'marker5.txt').write_text('local work\n', encoding='utf-8')
        result = self.run_overlay(self.arc)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('0005-arm64-grub-workflow.patch', result.stderr)
        self.assertIn('does not apply cleanly', result.stderr)
        for marker in ('marker.txt', 'marker2.txt', 'marker3.txt', 'marker4.txt'):
            self.assertEqual((self.arc / marker).read_text(), 'before\n')
        self.assertEqual((self.arc / 'marker5.txt').read_text(), 'local work\n')

    def test_sixth_patch_conflict_does_not_partially_apply_earlier_patches(self):
        (self.arc / 'marker6.txt').write_text('local work\n', encoding='utf-8')
        result = self.run_overlay(self.arc)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('0006-arm64-update-workflow.patch', result.stderr)
        self.assertIn('does not apply cleanly', result.stderr)
        for marker in ('marker.txt', 'marker2.txt', 'marker3.txt',
                       'marker4.txt', 'marker5.txt'):
            self.assertEqual((self.arc / marker).read_text(), 'before\n')
        self.assertEqual((self.arc / 'marker6.txt').read_text(), 'local work\n')

    def test_dockdsm_reboot_menu_labels_match_dispatch_cases(self):
        branding = (ROOT / 'patches/arc/0004-dockdsm-ui-branding.patch').read_text(
            encoding='utf-8')
        added_lines = '\n'.join(
            line[1:] for line in branding.splitlines()
            if line.startswith('+') and not line.startswith('+++'))
        for label in ('DockDSM: Config Mode', 'DockDSM: Automated Update Mode',
                      'DockDSM: Restart Network Service'):
            self.assertEqual(added_lines.count(label), 2, label)

    def test_arm64_model_filter_and_show_all_warning_are_present(self):
        architecture = (ROOT / 'patches/arc/0001-show-model-architecture.patch').read_text(
            encoding='utf-8')
        for expected in ('aarch64|arm64', '"${ARCH}" = "arm64"',
                         'Features[[:space:]]*:',
                         'Profile architecture ${ARCH} does not match loader architecture ${HOST_ARCH}',
                         '[ "${HOST_ARCH}" != "unknown" ]'):
            self.assertIn(expected, architecture)

    def test_arm64_grub_target_is_built_into_the_embedded_image(self):
        grub = (ROOT / 'patches/arc/0003-arm64-grub-esp.patch').read_text(
            encoding='utf-8')
        workflow = (ROOT / 'patches/arc/0005-arm64-grub-workflow.patch').read_text(
            encoding='utf-8')
        for expected in ('arm64-efi', 'TARGET_CC=aarch64-linux-gnu-gcc',
                         'TARGET_OBJCOPY=aarch64-linux-gnu-objcopy',
                         'TARGET_RANLIB=aarch64-linux-gnu-ranlib'):
            self.assertIn(expected, grub)
        self.assertIn('arm64-efi', workflow)
        self.assertIn('gcc-aarch64-linux-gnu', workflow)
        self.assertIn('"ARC"', workflow)

    def test_arm64_update_package_includes_grub_efi_modules(self):
        workflow = (ROOT / 'patches/arc/0006-arm64-update-workflow.patch').read_text(
            encoding='utf-8')
        self.assertIn('for T in i386-pc i386-efi x86_64-efi arm64-efi; do', workflow)

    def test_dockdsm_brand_covers_runtime_splash_and_title(self):
        branding = (ROOT / 'patches/arc/0004-dockdsm-ui-branding.patch').read_text(
            encoding='utf-8')
        for expected in ('DockDSM ${ARC_VERSION}', 'DockDSM Bootloader',
                         'DockDSM Update'):
            self.assertIn(expected, branding)


if __name__ == '__main__':
    unittest.main(verbosity=2)
