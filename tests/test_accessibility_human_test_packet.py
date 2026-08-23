# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import copy
import tempfile
import unittest
import zipfile
from pathlib import Path

from tools import accessibility_human_test_packet_check as packet_check


class AccessibilityHumanTestPacketTests(unittest.TestCase):
    def setUp(self) -> None:
        self.template = packet_check.load_template()
        self.matrix = packet_check.load_matrix()
        self.packet_text = packet_check.PACKET.read_text(encoding="utf-8")

    def validate_template(self, template: dict | None = None) -> list[str]:
        return packet_check.validate_template(
            template if template is not None else self.template,
            self.matrix,
            self.packet_text,
        )

    def test_template_is_exact_inconclusive_and_non_authorizing(self) -> None:
        self.assertEqual(self.validate_template(), [])
        candidate = self.template["candidate"]
        self.assertEqual(
            candidate["source_revision"], packet_check.EXPECTED_SOURCE_REVISION
        )
        self.assertEqual(candidate["package_sha256"], packet_check.ZERO_SHA256)
        self.assertEqual(candidate["resolution_sha256"], packet_check.ZERO_SHA256)
        self.assertEqual(
            candidate["provider_lock_sha256"],
            packet_check.EXPECTED_PROVIDER_LOCK_SHA256,
        )
        self.assertEqual(self.template["result"], "Inconclusive")
        self.assertTrue(
            all(item["result"] == "Inconclusive" for item in self.template["journeys"])
        )
        self.assertTrue(all(value is False for value in self.template["authority"].values()))

    def test_template_cannot_invent_a_pass(self) -> None:
        changed = copy.deepcopy(self.template)
        changed["result"] = "Pass"
        changed["journeys"][0]["result"] = "Pass"
        problems = self.validate_template(changed)
        self.assertTrue(any("template result must remain Inconclusive" in item for item in problems))
        self.assertTrue(any("template journeys must remain Inconclusive" in item for item in problems))

    def test_template_cannot_open_authority(self) -> None:
        changed = copy.deepcopy(self.template)
        changed["authority"]["publication"] = True
        problems = self.validate_template(changed)
        self.assertTrue(any("schema rejection" in item for item in problems))
        self.assertTrue(any("may not open" in item for item in problems))

    def test_template_requires_every_ordered_journey(self) -> None:
        changed = copy.deepcopy(self.template)
        changed["journeys"].pop()
        problems = self.validate_template(changed)
        self.assertTrue(any("complete ordered accessibility journey set" in item for item in problems))

    def test_template_rejects_source_and_provider_drift(self) -> None:
        changed = copy.deepcopy(self.template)
        changed["candidate"]["source_revision"] = "1" * 40
        changed["candidate"]["provider_lock_sha256"] = "2" * 64
        problems = self.validate_template(changed)
        self.assertTrue(any("exact packet source revision" in item for item in problems))
        self.assertTrue(any("exact provider lock" in item for item in problems))

    def test_packet_must_separate_mechanical_and_human_judgments(self) -> None:
        changed = self.packet_text.replace(
            "Mechanical prechecks do not constitute a human verdict.",
            "Mechanical checks are enough.",
        )
        problems = packet_check.validate_template(self.template, self.matrix, changed)
        self.assertTrue(any("Mechanical prechecks" in item for item in problems))

    def test_completed_receipt_binds_artifacts_without_accepting_authority(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            package = root / "candidate.zip"
            resolution = root / "release-resolution-set.v1.json"
            with zipfile.ZipFile(package, "w") as archive:
                archive.writestr("bin/facman.exe", b"facman")
                archive.writestr("bin/FacMan.WinForms.exe", b"winforms")
                archive.writestr("manifest/stage.v1.json", b"{}")
            resolution.write_text(
                """{
  "schema": "facman.release_resolution_set.v1",
  "target_id": "windows_winforms_technical_preview_x64",
  "source": {
    "implementation_revision": "601c5f49b7aa1cf4eb2b2af9733ac3e07e7ed27f",
    "dirty": false,
    "release_eligible": true,
    "providers": [
      {"id": "universal_launcher", "commit": "5479939ca5cbc9ee0f901608a92012778b4752ae"},
      {"id": "universal_setup", "commit": "d2a2aae7e61c47035c92334b0522143b4fea3880"}
    ]
  }
}
""",
                encoding="utf-8",
            )

            receipt = copy.deepcopy(self.template)
            receipt["receipt_id"] = "facman-accessibility-human-2026-08-24"
            receipt["candidate"]["candidate_id"] = "facman-candidate-601c5f49"
            receipt["candidate"]["package_sha256"] = packet_check.file_sha256(package)
            receipt["candidate"]["resolution_sha256"] = packet_check.file_sha256(
                resolution
            )
            receipt["tester"] = "Human tester"
            receipt["tested_at"] = "2026-08-24T01:00:00Z"
            receipt["environment"] = {
                "os": "Windows",
                "os_version": "11 24H2",
                "architecture": "x86_64",
                "display_profile": "100/150/200 percent and High Contrast",
                "assistive_technology": "Windows Narrator",
            }
            for journey in receipt["journeys"]:
                journey["result"] = "Inconclusive"
                journey["observations"] = [f"Observed {journey['id']} directly."]
            receipt["result"] = "Inconclusive"
            receipt["observations"] = ["Required journeys remain inconclusive."]
            receipt["unresolved_findings"] = ["Human acceptance is not granted."]

            self.assertEqual(
                packet_check.validate_receipt(
                    receipt,
                    package,
                    resolution,
                    self.matrix,
                    self.packet_text,
                ),
                [],
            )

            receipt["candidate"]["package_sha256"] = "3" * 64
            problems = packet_check.validate_receipt(
                receipt,
                package,
                resolution,
                self.matrix,
                self.packet_text,
            )
            self.assertTrue(any("package digest does not match" in item for item in problems))

    def test_completed_receipt_rejects_non_candidate_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            package = root / "candidate.zip"
            resolution = root / "release-resolution-set.v1.json"
            package.write_bytes(b"not a zip")
            resolution.write_text('{"schema":"wrong"}\n', encoding="utf-8")
            changed = copy.deepcopy(self.template)
            changed["candidate"]["package_sha256"] = packet_check.file_sha256(package)
            changed["candidate"]["resolution_sha256"] = packet_check.file_sha256(
                resolution
            )
            problems = packet_check.validate_receipt(
                changed,
                package,
                resolution,
                self.matrix,
                self.packet_text,
            )
            self.assertTrue(any("must be a ZIP candidate" in item for item in problems))
            self.assertTrue(any("wrong schema" in item for item in problems))

    def test_completed_pass_cannot_retain_unresolved_findings(self) -> None:
        changed = copy.deepcopy(self.template)
        changed["result"] = "Pass"
        for journey in changed["journeys"]:
            journey["result"] = "Pass"
        problems = packet_check.validate_receipt(
            changed,
            None,
            None,
            self.matrix,
            self.packet_text,
        )
        self.assertTrue(any("cannot retain unresolved findings" in item for item in problems))


if __name__ == "__main__":
    unittest.main()
