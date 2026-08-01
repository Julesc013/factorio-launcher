# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools import json_contract, windows_c1_release_candidate


class WindowsC1ReleaseCandidateTests(unittest.TestCase):
    def test_shell_and_backend_keep_exact_mode_and_route_boundaries(self) -> None:
        windows_c1_release_candidate.require_source_boundaries()

    def test_candidate_inspection_binds_package_source_and_checksum(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            package = root / "package"
            for relative in windows_c1_release_candidate.REQUIRED_PATHS:
                path = package / relative
                if Path(relative).suffix or relative.startswith("licenses/"):
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text("fixture\n", encoding="utf-8")
                else:
                    path.mkdir(parents=True, exist_ok=True)
            revision = "2" * 40
            (package / "manifest/package.v1.toml").write_text(
                'profile_id = "windows_legacy_winforms_x64"\n'
                'target_os = "windows"\n'
                'target_arch = "x64"\n'
                'entrypoint = "bin/FacMan.WinForms.exe"\n'
                f'source_revision = "{revision}"\n',
                encoding="utf-8",
            )
            (package / "manifest/build_info.v1.json").write_text(
                json.dumps({"source_commit": revision, "source_dirty": False}),
                encoding="utf-8",
            )
            artifact = root / "FacMan-0.1.0-windows-x64-portable.zip"
            artifact.write_bytes(b"candidate")
            checksum = artifact.with_name(artifact.name + ".sha256")
            checksum.write_text(
                f"{windows_c1_release_candidate.sha256(artifact)}  {artifact.name}\n",
                encoding="utf-8",
            )
            with (
                mock.patch.object(
                    windows_c1_release_candidate.package_hash_manifest,
                    "verify_manifest",
                    return_value=[],
                ),
                mock.patch.object(
                    windows_c1_release_candidate.provenance_build,
                    "verify_artifact_provenance",
                    return_value=[],
                ),
            ):
                report = windows_c1_release_candidate.inspect_candidate(package, artifact)
        self.assertEqual(revision, report["source_revision"])
        self.assertEqual("pass", report["qualification"]["package_construction"])

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
