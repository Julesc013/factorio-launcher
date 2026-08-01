# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools import json_contract, windows_c1_release_candidate


class WindowsC1ReleaseCandidateTests(unittest.TestCase):
    def test_shell_and_backend_keep_exact_mode_and_route_boundaries(self) -> None:
        windows_c1_release_candidate.require_source_boundaries()

    def test_provisional_report_contains_package_proof_without_release_claim(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            artifact = root / "FacMan-0.1.0-windows-x64-portable.zip"
            checksum = root / (artifact.name + ".sha256")
            artifact.write_bytes(b"candidate")
            checksum.write_text("placeholder\n", encoding="utf-8")
            report = windows_c1_release_candidate.evidence_report(
                source_revision="1" * 40,
                artifact=artifact,
                checksum=checksum,
            )
        self.assertEqual(
            [],
            json_contract.validate(
                report, json_contract.load_schema(windows_c1_release_candidate.SCHEMA)
            ),
        )
        self.assertEqual("pass", report["package"]["component_closure"])
        self.assertFalse(report["claims"]["release_candidate"])
        self.assertFalse(report["claims"]["supported_release"])
        self.assertEqual(
            "blocked_by_exact_route_authority", report["qualification"]["live_play"]
        )

    def test_required_closure_includes_shell_backend_pins_and_release_material(self) -> None:
        required = set(windows_c1_release_candidate.REQUIRED_PATHS)
        self.assertTrue(
            {
                "bin/FacMan.WinForms.exe",
                "bin/facman.exe",
                "bin/ulk.dll",
                "bin/usk.dll",
                "bin/flb_factorio.dll",
                "manifest/sbom.spdx.v2.3.json",
                "manifest/hashes.sha256",
                windows_c1_release_candidate.RELEASE_NOTES,
            }.issubset(required)
        )

    def test_release_blockers_cover_clean_machines_accessibility_route_and_signing(self) -> None:
        blockers = " ".join(windows_c1_release_candidate.BLOCKERS)
        for marker in ("windows_10", "windows_11", "accessibility", "scaling", "route", "signing"):
            self.assertIn(marker, blockers)


if __name__ == "__main__":
    unittest.main()
