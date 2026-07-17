# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools import compliance_check, provenance_build


class ComplianceTests(unittest.TestCase):
    def test_repository_compliance_policy_is_machine_verifiable(self) -> None:
        self.assertEqual([], compliance_check.validate())

    def test_sbom_covers_every_installed_bundle_component(self) -> None:
        records = [
            {"name": "console_cli", "source_target": "facman_cli", "destination": "bin/facman", "runtime_role": "runtime_required"},
            {"name": "contracts_schema", "source_target": "contracts/schema", "destination": "contracts/schema", "runtime_role": "compatibility_reference"},
        ]
        build_info = {
            "source_revisions": {"factorio_launcher": "a" * 40},
            "profile_id": "test_profile",
            "canonical_version": "0.1.0-dev",
            "source_timestamp_utc": "2026-01-01T00:00:00Z",
        }
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "manifest").mkdir()
            path = provenance_build.write_package_sbom(root, build_info, records)
            document = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual([], provenance_build.verify_sbom_component_coverage(document, records))
        licenses = {package["name"]: package["licenseDeclared"] for package in document["packages"]}
        self.assertEqual("MIT", licenses["Universal Launcher"])
        self.assertEqual("MIT", licenses["Universal Setup"])

    def test_sbom_component_coverage_rejects_missing_component(self) -> None:
        record = {"name": "console_cli"}
        problems = provenance_build.verify_sbom_component_coverage({"packages": [], "relationships": []}, [record])
        self.assertTrue(problems)


if __name__ == "__main__":
    unittest.main()
