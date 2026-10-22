#!/usr/bin/env python3
"""Offline branding and compatibility checks for the DockDSM rename."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = "Ben8368/DockDSM"
IMAGE = "ghcr.io/ben8368/dockdsm"


def read(name):
    return (ROOT / name).read_text(encoding="utf-8")


class DockDSMBrandingTests(unittest.TestCase):
    def test_entry_defaults_and_portal(self):
        entry = read("src/entry.sh")
        self.assertIn(': "${APP:="DockDSM"}"', entry)
        self.assertIn(f'https://github.com/{REPOSITORY}', entry)
        self.assertIn('<title>DockDSM</title>', read("src/print.sh"))

    def test_public_identity_and_deployment_images(self):
        self.assertIn('<h1 align="center">DockDSM', read("readme.md"))
        for name in ("compose.yml", "kubernetes.yml", ".devcontainer/codespaces.yml"):
            with self.subTest(file=name):
                text = read(name)
                self.assertRegex(text, rf"image: {re.escape(IMAGE)}:latest")
                self.assertNotIn("ghcr.io/ben8368/virtual-dsm", text)
        # Renaming does not publish packages; examples must keep this explicit.
        self.assertIn("不会自动发布镜像", read("readme.md"))
        self.assertIn('ghcr.io/${REPOSITORY,,}', read(".github/workflows/build.yml"))

    def test_upstream_attribution_preserved(self):
        self.assertIn("vdsm/virtual-dsm", read("NOTICE"))
        self.assertIn("AuxXxilium/arc", read("NOTICE"))
        self.assertIn("license.md", read("NOTICE"))
        self.assertIn("MIT License", read("license.md"))
        self.assertIn("Permission is hereby granted", read("license.md"))
        self.assertIn("88c2d4673aa428c9dc9c9ae90eaf63d0e8e2335c", read("docs/PROVENANCE.md"))
        self.assertIn("docs/PROVENANCE.md", read("readme.md"))

    def test_existing_storage_and_guest_identifiers_preserved(self):
        compose = read("compose.yml")
        self.assertIn("  dsm:", compose)
        self.assertIn("./dsm:/storage", compose)
        self.assertIn("virtualdsm", read("src/platform/common.sh"))
        self.assertIn("/usr/local/libexec/virtual-dsm/clock.sh", read("src/guest/virtual-dsm-clock.service"))
        self.assertIn("/usr/local/share/virtual-dsm/StorageManager.sha256", read("src/guest/virtual-dsm-storage-manager.service"))

    def test_arc_not_silently_added_to_production(self):
        for name in ("Dockerfile", "compose.yml", "src/entry.sh"):
            with self.subTest(file=name):
                text = read(name)
                self.assertNotRegex(text, r"(?i)(auxxxilium/arc|arc\.img)")


if __name__ == "__main__":
    unittest.main(verbosity=2)
