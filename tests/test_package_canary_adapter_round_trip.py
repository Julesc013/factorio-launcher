# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import json
import tempfile
import tomllib
import unittest
from pathlib import Path

from tools import package_canary_adapter_round_trip, package_hash_manifest
from tools.package import archive


class PackageCanaryAdapterRoundTripTests(unittest.TestCase):
    FACMAN = "1" * 40
    ULK = "2" * 40
    USK = "3" * 40
    ULK_TREE = "4" * 40
    USK_TREE = "5" * 40

    @staticmethod
    def _candidate_version(facman_revision: str) -> str:
        with package_canary_adapter_round_trip.VERSION_PATH.open("rb") as handle:
            semver = str(tomllib.load(handle)["semver"])
        return f"{semver}+canary.{facman_revision[:12]}"

    def _package(self, root: Path) -> Path:
        package = root / "package"
        (package / "bin").mkdir(parents=True)
        (package / "bin/facman.exe").write_bytes(b"facman-canary")
        manifest = package / "manifest"
        manifest.mkdir()
        custody = {
            "schema": "facman.repaired_provider_canary.v1",
            "classification": "noncanonical_engineering_candidate",
            "candidate_version": self._candidate_version(self.FACMAN),
            "source_revisions": {
                "factorio_launcher": self.FACMAN,
                "universal_launcher": self.ULK,
                "universal_setup": self.USK,
            },
            "source_trees": {
                "universal_launcher": self.ULK_TREE,
                "universal_setup": self.USK_TREE,
            },
            "required_refs": {
                "universal_launcher": "refs/heads/task/ulk-repair",
                "universal_setup": "refs/heads/main",
            },
            "authority": {field: False for field in sorted(
                package_canary_adapter_round_trip.AUTHORITY_FIELDS
            )},
            "provider_adoption": False,
            "published": False,
            "release_eligible": False,
            "signed": False,
            "canonical_provider_pin_unchanged": True,
        }
        (manifest / "repaired-provider-canary.v1.json").write_text(
            json.dumps(custody, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        index = package / "release" / "index"
        index.mkdir(parents=True)
        (index / "workspace_lock.v1.toml").write_text(
            'schema = "flaunch.workspace_lock.v1"\n\n'
            '[[component]]\n'
            'id = "universal_launcher"\n'
            f'pin = "{self.ULK}"\n'
            f'tree = "{self.ULK_TREE}"\n\n'
            'required_ref = "refs/heads/task/ulk-repair"\n\n'
            '[[component]]\n'
            'id = "universal_setup"\n'
            f'pin = "{self.USK}"\n'
            f'tree = "{self.USK_TREE}"\n'
            'required_ref = "refs/heads/main"\n',
            encoding="utf-8",
        )
        package_hash_manifest.write_manifests(
            package, package_hash_manifest.component_records_from_files(package)
        )
        return package

    def _archive(self, package: Path, root: Path) -> Path:
        artifact = root / "candidate.zip"
        return archive.write(package, artifact, "zip", "2026-01-01T00:00:00Z")

    def test_exact_canary_root_and_zip_pass(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            package = self._package(root)
            artifact = self._archive(package, root)
            report = package_canary_adapter_round_trip.verify(
                package, artifact, self.FACMAN, self.ULK, self.USK
            )
        self.assertTrue(report["verified"])
        self.assertFalse(report["canonical_release_verified"])
        self.assertEqual(report["entry_count"], 5)
        self.assertEqual(
            report["content_projection_sha256"],
            report["archive_content_projection_sha256"],
        )

    def test_changed_root_after_archiving_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            package = self._package(root)
            artifact = self._archive(package, root)
            (package / "bin/facman.exe").write_bytes(b"changed")
            with self.assertRaisesRegex(ValueError, "integrity failed"):
                package_canary_adapter_round_trip.verify(
                    package, artifact, self.FACMAN, self.ULK, self.USK
                )

    def test_changed_declared_provider_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            package = self._package(root)
            artifact = self._archive(package, root)
            with self.assertRaisesRegex(ValueError, "source revisions"):
                package_canary_adapter_round_trip.verify(
                    package, artifact, self.FACMAN, "4" * 40, self.USK
                )


if __name__ == "__main__":
    unittest.main()
