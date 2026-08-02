# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools import json_contract, windows_c1_release_candidate
from tools.package import pipeline as package_pipeline


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
                report = windows_c1_release_candidate.inspect_candidate(
                    package, artifact, revision
                )
        self.assertEqual(revision, report["source_revision"])
        self.assertEqual("pass", report["qualification"]["package_construction"])

    def test_candidate_inspection_rejects_unexpected_source_revision(self) -> None:
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
            with self.assertRaisesRegex(ValueError, "candidate source revision"):
                windows_c1_release_candidate.inspect_candidate(
                    package, artifact, "3" * 40
                )

    def test_expected_source_revision_requires_exact_sha(self) -> None:
        for revision in ("", "1" * 39, "A" * 40, "G" * 40, "1" * 41):
            with self.subTest(revision=revision):
                with self.assertRaisesRegex(ValueError, "40 lowercase hexadecimal"):
                    windows_c1_release_candidate.require_revision(revision)

    def test_repository_revision_is_an_exact_sha(self) -> None:
        self.assertRegex(
            windows_c1_release_candidate.repository_revision(), r"^[0-9a-f]{40}$"
        )

    def test_ci_binds_checkout_candidate_and_artifact_to_same_source(self) -> None:
        workflow = (windows_c1_release_candidate.ROOT / ".github/workflows/ci.yml").read_text(
            encoding="utf-8"
        )
        immutable_source = "${{ github.event.pull_request.head.sha || github.sha }}"
        self.assertIn(f"FACMAN_CI_SOURCE_SHA: {immutable_source}", workflow)
        self.assertIn(f"ref: {immutable_source}", workflow)
        self.assertIn(f'--expected-source-revision "{immutable_source}"', workflow)
        self.assertIn(f"windows-c1-release-candidate-{immutable_source}", workflow)

    def test_ci_provenance_prefers_explicit_checked_out_source(self) -> None:
        revision = "4" * 40
        with mock.patch.dict(
            "os.environ",
            {
                "GITHUB_ACTIONS": "true",
                "GITHUB_SHA": "5" * 40,
                "FACMAN_CI_SOURCE_SHA": revision,
                "GITHUB_RUN_ID": "1",
                "GITHUB_RUN_ATTEMPT": "1",
                "GITHUB_WORKFLOW": "ci",
                "GITHUB_REPOSITORY": "Julesc013/factorio-launcher",
            },
            clear=True,
        ):
            identity = windows_c1_release_candidate.provenance_build.ci_identity(revision)
        self.assertEqual(revision, identity["source_sha"])

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
        self.assertEqual("absent", report["package"]["developer_machine_paths"])
        self.assertFalse(report["claims"]["release_candidate"])
        self.assertFalse(report["claims"]["supported_release"])
        self.assertEqual(
            "blocked_by_exact_route_authority", report["qualification"]["live_play"]
        )

    def test_candidate_rejects_concrete_developer_machine_paths(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            leaked = root / "docs/release/checkpoints/historical.md"
            leaked.parent.mkdir(parents=True)
            leaked.write_text(
                "stage: C:\\Users\\OperatorName\\AppData\\Local\\Temp\\facman-stage\\\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "developer-machine path"):
                windows_c1_release_candidate.require_no_developer_machine_paths(root)

    def test_packaged_release_documents_exclude_historical_checkpoint_tree(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            source = root / "source"
            destination = root / "destination"
            source.mkdir()
            (source / "release-notes.md").write_text("release\n", encoding="utf-8")
            checkpoint = source / "checkpoints/historical.md"
            checkpoint.parent.mkdir()
            checkpoint.write_text("host evidence\n", encoding="utf-8")
            package_pipeline.copy_release_documents(source, destination)
            self.assertTrue((destination / "release-notes.md").is_file())
            self.assertFalse((destination / "checkpoints").exists())

    def test_packaged_release_metadata_excludes_repository_execution_truth(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            profile = package_pipeline.load_toml(
                windows_c1_release_candidate.ROOT
                / "release/profiles/windows_legacy_winforms_x64/profile.toml"
            )
            package_pipeline.copy_release_metadata(
                windows_c1_release_candidate.ROOT / "release",
                root / "release",
                profile,
            )
            self.assertTrue((root / "release/index/release_index.v1.toml").is_file())
            self.assertTrue((root / profile["package_manifest"]).is_file())
            self.assertFalse((root / "release/index/project_status.v2.toml").exists())
            self.assertFalse((root / "release/index/plan.v1.toml").exists())
            windows_c1_release_candidate.require_no_developer_machine_paths(root)

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
