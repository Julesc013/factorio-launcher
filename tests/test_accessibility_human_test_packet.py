# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import copy
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from tools import accessibility_human_test_packet_check as packet_check


class AccessibilityHumanTestPacketTests(unittest.TestCase):
    SOURCE_REVISION = "a" * 40
    SOURCE_TREE = "b" * 40
    RESOLUTION_ROOT_DIGEST = "c" * 64
    RESOLUTION_DIGEST = "d" * 64
    STAGE_DIGEST = "e" * 64

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

    @staticmethod
    def write_artifacts(root: Path) -> tuple[Path, Path]:
        composition = root / "resolved-composition.v1.json"
        composition.write_text(
            json.dumps(
                {
                    "schema": "facman.release_resolution.v1",
                    "target_id": packet_check.EXPECTED_TARGET,
                    "resolution_digest": AccessibilityHumanTestPacketTests.RESOLUTION_DIGEST,
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        resolution = root / "release-resolution-set.v1.json"
        resolution.write_text(
            json.dumps(
                {
                    "schema": "facman.release_resolution_set.v1",
                    "target_id": packet_check.EXPECTED_TARGET,
                    "root_digest": AccessibilityHumanTestPacketTests.RESOLUTION_ROOT_DIGEST,
                    "records": {
                        composition.name: packet_check.domain_digest_value(
                            "facman.release_resolution.v1",
                            json.loads(composition.read_text(encoding="utf-8")),
                        ),
                    },
                    "source": {
                        "implementation_revision": AccessibilityHumanTestPacketTests.SOURCE_REVISION,
                        "build_tree": AccessibilityHumanTestPacketTests.SOURCE_TREE,
                        "dirty": False,
                        "release_eligible": True,
                        "providers": [
                            {
                                "id": provider_id,
                                "commit": commit,
                                "dirty": False,
                            }
                            for provider_id, commit in packet_check.EXPECTED_PROVIDERS.items()
                        ],
                    },
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        package = root / packet_check.load_toml(packet_check.ALPHA_SOURCE)["package"][
            "filename"
        ]
        stage = {
            "schema": "facman.stage_manifest.v1",
            "target_id": packet_check.EXPECTED_TARGET,
            "product_version": "facman-0.1.0-alpha.1",
            "artifact_id": "windows_winforms_technical_preview_zip",
            "resolution_digest": AccessibilityHumanTestPacketTests.RESOLUTION_DIGEST,
            "resolution_root_digest": AccessibilityHumanTestPacketTests.RESOLUTION_ROOT_DIGEST,
            "stage_digest": AccessibilityHumanTestPacketTests.STAGE_DIGEST,
        }
        with zipfile.ZipFile(package, "w") as archive:
            archive.writestr("bin/facman.exe", b"facman")
            archive.writestr("bin/FacMan.WinForms.exe", b"winforms")
            archive.writestr(
                "manifest/stage.v1.json",
                json.dumps(stage, sort_keys=True).encode("utf-8"),
            )
        return package, resolution

    @staticmethod
    def bind_fixture(package: Path, resolution: Path) -> dict:
        receipt, problems = packet_check.bind_pending_receipt(package, resolution)
        if problems:
            raise AssertionError(problems)
        return receipt

    @staticmethod
    def complete_human_fields(receipt: dict) -> None:
        receipt["receipt_id"] = "facman-accessibility-human-2026-08-24"
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

    def test_template_is_exact_inconclusive_and_non_authorizing(self) -> None:
        self.assertEqual(self.validate_template(), [])
        candidate = self.template["candidate"]
        self.assertEqual(
            self.template["receipt_id"], packet_check.EXPECTED_PENDING_RECEIPT_ID
        )
        self.assertEqual(
            candidate["candidate_id"], packet_check.EXPECTED_CANDIDATE_ID
        )
        self.assertEqual(
            candidate["source_revision"], packet_check.UNBOUND_REVISION
        )
        self.assertEqual(
            candidate["package_sha256"], packet_check.UNBOUND_SHA256
        )
        self.assertEqual(
            candidate["resolution_sha256"],
            packet_check.UNBOUND_SHA256,
        )
        self.assertEqual(
            candidate["provider_lock_sha256"],
            packet_check.EXPECTED_PROVIDER_LOCK_SHA256,
        )
        self.assertEqual(self.template["result"], "Inconclusive")
        self.assertTrue(
            all(item["result"] == "Inconclusive" for item in self.template["journeys"])
        )
        self.assertTrue(
            all(value is False for value in self.template["authority"].values())
        )

    def test_template_cannot_invent_a_pass(self) -> None:
        changed = copy.deepcopy(self.template)
        changed["result"] = "Pass"
        changed["journeys"][0]["result"] = "Pass"
        problems = self.validate_template(changed)
        self.assertTrue(
            any("template result must remain Inconclusive" in item for item in problems)
        )
        self.assertTrue(
            any("template journeys must remain Inconclusive" in item for item in problems)
        )

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
        self.assertTrue(
            any("complete ordered accessibility journey set" in item for item in problems)
        )

    def test_template_rejects_stale_source_package_and_resolution(self) -> None:
        controls = {
            "source_revision": "1" * 40,
            "package_sha256": "2" * 64,
            "resolution_sha256": "3" * 64,
        }
        for field, value in controls.items():
            with self.subTest(field=field):
                changed = copy.deepcopy(self.template)
                changed["candidate"][field] = value
                problems = self.validate_template(changed)
                self.assertTrue(
                    any("artifact-unassigned" in item for item in problems), problems
                )

    def test_template_rejects_provider_drift(self) -> None:
        changed = copy.deepcopy(self.template)
        changed["candidate"]["provider_lock_sha256"] = "2" * 64
        problems = self.validate_template(changed)
        self.assertTrue(any("artifact-unassigned" in item for item in problems))

    def test_packet_must_separate_mechanical_and_human_judgments(self) -> None:
        changed = self.packet_text.replace(
            "Mechanical prechecks do not constitute a human verdict.",
            "Mechanical checks are enough.",
        )
        problems = packet_check.validate_template(self.template, self.matrix, changed)
        self.assertTrue(any("Mechanical prechecks" in item for item in problems))

    def test_pending_packet_binds_exact_artifact_domains(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            package, resolution = self.write_artifacts(Path(raw))
            receipt = self.bind_fixture(package, resolution)
            self.assertEqual(
                packet_check.validate_pending_receipt(
                    receipt,
                    package,
                    resolution,
                    self.matrix,
                    self.packet_text,
                ),
                [],
            )

    def test_pending_packet_rejects_stale_resolution_root(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            package, resolution = self.write_artifacts(Path(raw))
            receipt = self.bind_fixture(package, resolution)
            record = json.loads(resolution.read_text(encoding="utf-8"))
            record["root_digest"] = "0" * 64
            resolution.write_text(
                json.dumps(record, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            problems = packet_check.validate_pending_receipt(
                receipt,
                package,
                resolution,
                self.matrix,
                self.packet_text,
            )
            self.assertTrue(
                any("stage resolution_root_digest" in item for item in problems),
                problems,
            )

    def test_completed_receipt_binds_artifacts_without_accepting_authority(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            package, resolution = self.write_artifacts(Path(raw))
            receipt = self.bind_fixture(package, resolution)
            self.complete_human_fields(receipt)
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

    def test_completed_receipt_rejects_missing_human_fields(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            package, resolution = self.write_artifacts(Path(raw))
            receipt = self.bind_fixture(package, resolution)
            problems = packet_check.validate_receipt(
                receipt,
                package,
                resolution,
                self.matrix,
                self.packet_text,
            )
            expected = (
                "new human receipt identity",
                "identified tester",
                "observed test time",
                "exact observed environment",
                "assistive technology used",
                "template-only journey observations",
            )
            for message in expected:
                self.assertTrue(any(message in item for item in problems), problems)

    def test_completed_receipt_rejects_non_candidate_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            package = root / "candidate.zip"
            resolution = root / "release-resolution-set.v1.json"
            package.write_bytes(b"not a zip")
            resolution.write_text('{"schema":"wrong"}\n', encoding="utf-8")
            problems = packet_check.validate_receipt(
                self.template,
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
        self.assertTrue(
            any("cannot retain unresolved findings" in item for item in problems)
        )


if __name__ == "__main__":
    unittest.main()
