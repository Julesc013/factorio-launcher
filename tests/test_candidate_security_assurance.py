# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import tempfile
import unittest
import zipfile
from pathlib import Path

from tools import candidate_security_assurance as assurance


class CandidateSecurityAssuranceTests(unittest.TestCase):
    def test_toml_source_revision_parser_is_exact(self) -> None:
        text = 'source_revision = "abc123"\nsource_revision_note = "wrong"\n'
        self.assertEqual(assurance._toml_string(text, "source_revision"), "abc123")
        self.assertIsNone(assurance._toml_string(text, "missing"))

    def test_zip_path_validation_refuses_traversal_and_windows_paths(self) -> None:
        self.assertTrue(assurance._safe_zip_name("bin/facman.exe"))
        self.assertFalse(assurance._safe_zip_name("../facman.exe"))
        self.assertFalse(assurance._safe_zip_name("C:/facman.exe"))
        self.assertFalse(assurance._safe_zip_name("bin\\facman.exe"))

    def test_sensitive_marker_detection_covers_private_paths_and_tokens(self) -> None:
        value = b"E:\\Downloads\\factorio-space-age_win_2.1.14.zip gho_abcdefghijklmnopqrstuvwxyz"
        matches = assurance._sensitive_markers(value)
        self.assertIn("E:\\Downloads", matches)
        self.assertIn("factorio-space-age_win_2.1.14.zip", matches)
        self.assertTrue(any(match.startswith("gho_") for match in matches))

    def test_zip_review_detects_case_collision_and_operator_payload(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            archive_path = Path(temporary) / "candidate.zip"
            with zipfile.ZipFile(archive_path, "w") as archive:
                archive.writestr("bin/FacMan.exe", b"one")
                archive.writestr("bin/facman.exe", b"two")
                archive.writestr("bin/facman_engineering_play_harness.exe", b"three")
            with zipfile.ZipFile(archive_path, "r") as archive:
                findings, _digests = assurance._zip_findings(archive)
        codes = {finding.code for finding in findings}
        self.assertIn("case_collision", codes)
        self.assertIn("operator_or_test_payload", codes)
        self.assertIn("unexpected_binary", codes)


if __name__ == "__main__":
    unittest.main()
