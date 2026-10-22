#!/usr/bin/env python3
"""Exercise the real x86 installer selection and disk-preservation paths."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
DEFAULT = 'DSM_VirtualDSM_72806'
LEGACY = 'DSM_VirtualDSM_42962'


class InstallerStateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='x86-installer-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.storage = self.root / 'storage with spaces'
        self.storage.mkdir()
        self.run = self.root / 'run'
        self.run.mkdir()
        self.binds = self.root / 'binds'
        self.binds.mkdir()
        # Redirect only container paths; run the production function bodies.
        source = (REPO / 'src/install.sh').read_text()
        source = source.replace('. /run/pat.sh', '. "$REPO/src/pat.sh"')
        source = source.replace('rm -rf /tmp/dsm', 'rm -rf "$QEMU_DIR/dsm"')
        source = source.replace('local pat="/$BASE.pat"', 'local pat="$QEMU_DIR/$BASE.pat"')
        self.script = self.root / 'install.sh'
        self.script.write_text(source)

    def pair(self, base, boot=b'original boot', system=b'original system'):
        for suffix, content in (('boot.img', boot), ('system.img', system)):
            if content is not None:
                (self.storage / (base + '.' + suffix)).write_bytes(content)

    def snapshot(self):
        return {p.name: ('link', os.readlink(p)) if p.is_symlink() else
                ('file', p.read_bytes()) if p.is_file() else ('dir',)
                for p in self.storage.iterdir()}

    def invoke(self, url=''):
        env = os.environ.copy()
        env.update(REPO=str(REPO), STORAGE=str(self.storage), QEMU_DIR=str(self.run),
                   TEST_BINDS=str(self.binds), URL=url, COUNTRY='US', TZ='',
                   CONNECTIONS='1')
        wrapper = r'''
set -Eeuo pipefail
strip() { printf '%s' "$1"; }
error() { printf '%s\n' "$*" >&2; }
info() { :; }
html() { :; }
find() {
  if [[ "$1" == / ]]; then shift; command find "$TEST_BINDS" "$@";
  else command find "$@"; fi
}
# Production helpers are loaded first, then host and installation side effects
# are replaced. installDSM itself is left intact and invoked as in production.
source_without_entry() { sed '/^installDSM || exit /,$d' "$1"; }
. <(source_without_entry "$1")
checkSse42() { :; }
reservePorts() { :; }
prepareMac() { :; }
checkDsmFilesystem() { :; }
checkDsmSpace() { :; }
makeDir() { mkdir -p "$1"; }
downloadPat() { printf '%s' "$URL" > "$QEMU_DIR/download-attempt"; return 69; }
extractPat() { echo 'Unexpected extraction' >&2; return 98; }
installDSM || exit $?
'''
        return subprocess.run(['bash', '-c', wrapper, 'fixture', str(self.script)],
                              env=env, text=True, capture_output=True, timeout=10)

    def assert_preserved(self, expected, url=''):
        before = self.snapshot()
        result = self.invoke(url)
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        self.assertEqual(self.snapshot(), before, result.stderr)
        self.assertFalse((self.run / 'download-attempt').exists())
        if expected == 65:
            self.assertIn('existing images are preserved', result.stderr)

    def test_partial_selected_installations_are_preserved(self):
        cases = [
            ('recorded-current', DEFAULT, DEFAULT, ''),
            ('recorded-old', 'DSM_VirtualDSM_69057', 'DSM_VirtualDSM_69057', ''),
            ('legacy', LEGACY, None, ''),
            ('default-without-marker', DEFAULT, None, ''),
            ('explicit-url', 'custom', None, 'https://example.invalid/custom.pat'),
            ('encoded-url', 'custom_name', None, 'https://example.invalid/custom%20name.pat'),
            ('local-bind', 'DSM_VirtualDSM', None, ''),
        ]
        # Each subcase gets an independent filesystem and fresh environment.
        for name, base, recorded, url in cases:
            for missing in ('boot', 'system'):
                with self.subTest(source=name, missing=missing):
                    fixture = InstallerStateTests()
                    fixture.setUp()
                    try:
                        if recorded:
                            (fixture.storage / 'dsm.ver').write_text(recorded)
                        if name == 'local-bind':
                            (fixture.binds / 'boot.pat').write_bytes(b'local PAT')
                        fixture.pair(base, boot=None if missing == 'boot' else b'boot',
                                     system=None if missing == 'system' else b'user DSM state')
                        (fixture.storage / (base + '.pat')).write_bytes(b'cached PAT')
                        (fixture.storage / (base + '.agent')).write_bytes(b'agent')
                        fixture.assert_preserved(65, url)
                    finally:
                        fixture.doCleanups()

    def test_empty_and_broken_images_are_preserved(self):
        for kind in ('empty', 'broken-link', 'directory'):
            with self.subTest(kind=kind):
                fixture = InstallerStateTests()
                fixture.setUp()
                try:
                    (fixture.storage / 'dsm.ver').write_text(DEFAULT)
                    image = fixture.storage / (DEFAULT + '.system.img')
                    if kind == 'empty':
                        image.touch()
                    elif kind == 'broken-link':
                        image.symlink_to('missing-original-disk')
                    else:
                        image.mkdir()
                    fixture.assert_preserved(65)
                finally:
                    fixture.doCleanups()

    def test_complete_recorded_pair_needs_no_pat(self):
        (self.storage / 'dsm.ver').write_text(DEFAULT)
        self.pair(DEFAULT)
        self.assert_preserved(0)

    def test_complete_legacy_pair_is_reused(self):
        self.pair(LEGACY)
        self.assert_preserved(0)

    def test_complete_default_pair_without_marker_is_reused(self):
        self.pair(DEFAULT)
        self.assert_preserved(0)

    def test_complete_custom_pair_is_reused(self):
        self.pair('custom')
        self.assert_preserved(0, 'https://example.invalid/custom.pat')

    def test_complete_directory_bind_is_reused(self):
        (self.binds / 'boot.pat').mkdir()
        self.pair('DSM_VirtualDSM')
        self.assert_preserved(0)

    def test_empty_storage_can_reach_acquisition(self):
        result = self.invoke()
        self.assertEqual(result.returncode, 69, result.stderr)
        self.assertTrue((self.run / 'download-attempt').read_text().endswith(DEFAULT + '.pat'))
        self.assertFalse(list(self.storage.glob('*.img')))


if __name__ == '__main__':
    unittest.main(verbosity=2)
