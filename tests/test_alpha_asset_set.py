# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools import alpha_asset_set, alpha_publication_gate, alpha_qualification

SOURCE = "8362ddc55cbb98b538f4af410819c9503604ef99"
TREE = "859695fdcaead2e5e11c5454976432df13cacc1a"
PACKAGE = "facman-0.1.0-alpha.1-windows-winforms-x86_64-technical-preview.zip"


def digest_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


class AlphaAssetSetTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.qualification = self.root / "qualification"
        assurance = self.qualification / "root1/dist/assurance"
        assurance.mkdir(parents=True)
        resolution = self.qualification / "root1/resolution"
        resolution.mkdir(parents=True)
        package_path = self.qualification / "root1/dist" / PACKAGE
        package_path.write_bytes(b"exact alpha package")
        self.sbom_path = assurance / f"{PACKAGE}.sbom.spdx.v2.3.json"
        self.sbom_path.write_text('{"spdx":"fixture"}\n', encoding="utf-8")
        self.provenance_path = assurance / f"{PACKAGE}.provenance.v1.json"
        self.provenance = {
            "schema": "facman.canonical_candidate_provenance.v1",
            "status": "pass",
            "published": False,
            "source": {
                "revision": SOURCE,
                "tree": TREE,
                "dirty": False,
                "release_eligible": True,
            },
            "artifact": {"sha256": alpha_asset_set.sha256(package_path)},
            "resolution": {
                "root_digest": "1" * 64,
                "source_observation_digest": "2" * 64,
            },
            "stage": {"stage_digest": "3" * 64},
            "runtime_verifier": {
                "native_admission_ready": True,
                "source_release_eligible": True,
                "static_closure_verified": True,
            },
            "licences": [
                {
                    "component_id": "facman",
                    "path": "licenses/LICENSE",
                    "sha256": "4" * 64,
                    "size": 1087,
                    "spdx": "MIT",
                }
            ],
            "authority": {
                "factorio_execution_authorized": False,
                "product_authority_granted": False,
                "setup_mutation_authorized": False,
                "supported": False,
            },
        }
        self._write_json(self.provenance_path, self.provenance)
        self._write_json(
            resolution / "release-resolution-set.v1.json",
            {"schema": "facman.release_resolution_set.v1"},
        )
        self.comparison_path = self.qualification / "three-root-comparison.v1.json"
        self.comparison = {
            "schema": "facman.canonical_v2_three_root_comparison.v1",
            "source_revision": SOURCE,
            "source_tree": TREE,
            "source_observation_digest": "2" * 64,
            "resolution_root_digest": "1" * 64,
            "stage_digest": "3" * 64,
            "archive_sha256": alpha_asset_set.sha256(package_path),
            "sbom_sha256": alpha_asset_set.sha256(self.sbom_path),
            "provenance_sha256": alpha_asset_set.sha256(self.provenance_path),
            "roots": [
                {"id": f"root{index}", "file_count": 427, "total_bytes": 1000}
                for index in range(1, 4)
            ],
            "mismatch_count": 0,
            "mismatches": [],
            "qualification": {
                "stable_root_build": "pass_in_every_root",
                "native_package_verify": "pass_in_every_root",
                "drift_refusal": "pass_in_every_root",
                "archive_verify": "pass_in_every_root",
                "assurance_verify": "pass_in_every_root",
            },
            "authority": {
                "tagging": False,
                "signing": False,
                "publication": False,
                "support": False,
                "setup_mutation": False,
                "factorio_execution": False,
            },
        }
        self._write_json(self.comparison_path, self.comparison)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    @staticmethod
    def _write_json(path: Path, value: dict) -> None:
        path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def _machine(self) -> Path:
        output = self.root / "machine"
        alpha_asset_set.build_machine_assets(
            qualification_root=self.qualification,
            output_root=output,
            source_revision=SOURCE,
            release_source_root=alpha_asset_set.ROOT,
        )
        return output

    def _route(self, machine: Path) -> Path:
        candidate = alpha_asset_set.load_json(
            machine / "facman-0.1.0-alpha.1-candidate.v1.json"
        )
        ledger = alpha_asset_set.load_json(
            machine / "facman-0.1.0-alpha.1-release-ledger-entry.v1.json"
        )
        route = {
            "schema": "facman.human_test_receipt.v1",
            "receipt_id": "facman-alpha1-factorio-2.1.14-route",
            "candidate": {
                "candidate_id": candidate["candidate_id"],
                "source_revision": SOURCE,
                "package_sha256": alpha_asset_set.sha256(machine / PACKAGE),
                "resolution_sha256": ledger["resolution_sha256"],
                "provider_lock_sha256": candidate["providers"]["provider_lock_sha256"],
            },
            "tester": "route-observer",
            "tested_at": "2026-08-24T00:00:00Z",
            "environment": {
                "os": "Windows",
                "os_version": "11",
                "architecture": "x86_64",
                "display_profile": "route-observer",
                "assistive_technology": None,
            },
            "journeys": [
                {
                    "id": "factorio-2.1.14-play-to-menu",
                    "version": "1",
                    "result": "Pass",
                    "observations": ["Stable process and accepted menu observation."],
                }
            ],
            "result": "Pass",
            "observations": ["Archive and foreign state remained immutable."],
            "accepted_limitations": [],
            "unresolved_findings": [],
            "authority": {
                "beta_promotion": False,
                "stable_promotion": False,
                "route_promotion": False,
                "signing": False,
                "publication": False,
            },
        }
        path = self.root / "route.json"
        self._write_json(path, route)
        return path

    def test_machine_assets_are_exact_schema_valid_and_non_authorizing(self) -> None:
        machine = self._machine()
        names = {path.name for path in machine.iterdir()}
        self.assertEqual(len(names), 7)
        self.assertIn(PACKAGE, names)
        candidate = alpha_asset_set.load_json(
            machine / "facman-0.1.0-alpha.1-candidate.v1.json"
        )
        ledger = alpha_asset_set.load_json(
            machine / "facman-0.1.0-alpha.1-release-ledger-entry.v1.json"
        )
        self.assertEqual(candidate["source"]["revision"], SOURCE)
        self.assertEqual(candidate["status"], "qualified")
        self.assertFalse(any(candidate["authority"].values()))
        self.assertIsNone(ledger["human_receipt"])
        self.assertFalse(any(ledger["authority"].values()))

    def test_machine_assets_refuse_mismatch_authority_and_substitution(self) -> None:
        changed = copy.deepcopy(self.comparison)
        changed["mismatch_count"] = 1
        self._write_json(self.comparison_path, changed)
        with self.assertRaisesRegex(ValueError, "byte-identical"):
            self._machine()

        changed = copy.deepcopy(self.comparison)
        changed["authority"]["publication"] = True
        self._write_json(self.comparison_path, changed)
        with self.assertRaisesRegex(ValueError, "authority"):
            self._machine()

        self._write_json(self.comparison_path, self.comparison)
        package_path = self.qualification / "root1/dist" / PACKAGE
        package_path.write_bytes(b"substituted")
        with self.assertRaisesRegex(ValueError, "package digest"):
            self._machine()

    def test_machine_assets_require_every_machine_decision(self) -> None:
        changed = copy.deepcopy(self.comparison)
        changed["qualification"]["drift_refusal"] = "pending"
        self._write_json(self.comparison_path, changed)
        with self.assertRaisesRegex(ValueError, "every passing machine decision"):
            self._machine()

    def test_machine_assets_refuse_existing_output(self) -> None:
        output = self.root / "machine"
        output.mkdir()
        with self.assertRaisesRegex(ValueError, "must be new"):
            alpha_asset_set.build_machine_assets(
                qualification_root=self.qualification,
                output_root=output,
                source_revision=SOURCE,
                release_source_root=alpha_asset_set.ROOT,
            )

    def test_route_assembly_is_exact_and_still_non_authorizing(self) -> None:
        machine = self._machine()
        route = self._route(machine)
        output = self.root / "route-bound"
        receipt = alpha_asset_set.assemble_route_bound_assets(
            machine_root=machine,
            route_receipt=route,
            output_root=output,
        )
        self.assertEqual(receipt["pending"], ["publication_authority"])
        self.assertFalse(any(receipt["authority"].values()))
        self.assertEqual(len(list(output.iterdir())), 9)
        checksums = (
            output / "facman-0.1.0-alpha.1-checksums.txt"
        ).read_text(encoding="utf-8")
        self.assertEqual(len(checksums.splitlines()), 8)
        self.assertNotIn("publication-authority", checksums)

    def test_route_bound_assets_feed_the_existing_publication_gate_exactly(self) -> None:
        machine = self._machine()
        route = self._route(machine)
        output = self.root / "route-bound"
        alpha_asset_set.assemble_route_bound_assets(
            machine_root=machine,
            route_receipt=route,
            output_root=output,
        )
        package_sha = alpha_asset_set.sha256(output / PACKAGE)
        route_name = "facman-0.1.0-alpha.1-factorio-2.1.14-route-receipt.v1.json"
        route_sha = alpha_asset_set.sha256(output / route_name)
        authority_name = "facman-0.1.0-alpha.1-publication-authority.v1.json"
        authority = {
            "schema": "facman.alpha_publication_authority.v1",
            "version": "0.1.0-alpha.1",
            "tag": "v0.1.0-alpha.1",
            "source_revision": SOURCE,
            "package_sha256": package_sha,
            "route_receipt_sha256": route_sha,
            "decision": "authorize_exact_alpha_publication_once",
            "approved_by": "owner-fixture",
            "approved_at": "2026-08-24T00:00:00Z",
            "authority": {
                "tag_creation": True,
                "publication": True,
                "signing": False,
                "support_promotion": False,
                "route_promotion": False,
            },
        }
        authority_path = output / authority_name
        self._write_json(authority_path, authority)
        with mock.patch.object(alpha_publication_gate, "validate_source", return_value=[]):
            problems = alpha_publication_gate.validate_publish(
                source_revision=SOURCE,
                asset_root=output,
                route_receipt_sha256=route_sha,
                publication_authority_sha256=alpha_asset_set.sha256(authority_path),
            )
        self.assertEqual(problems, [])

    def test_route_assembly_refuses_nonpass_and_wrong_candidate(self) -> None:
        machine = self._machine()
        route_path = self._route(machine)
        route = alpha_asset_set.load_json(route_path)
        route["result"] = "Inconclusive"
        route["journeys"][0]["result"] = "Inconclusive"
        self._write_json(route_path, route)
        with self.assertRaisesRegex(ValueError, "passing route receipt"):
            alpha_asset_set.assemble_route_bound_assets(
                machine_root=machine,
                route_receipt=route_path,
                output_root=self.root / "route-bound-a",
            )

        route["result"] = "Pass"
        route["journeys"][0]["result"] = "Pass"
        route["candidate"]["package_sha256"] = "0" * 64
        self._write_json(route_path, route)
        with self.assertRaisesRegex(ValueError, "package differs"):
            alpha_asset_set.assemble_route_bound_assets(
                machine_root=machine,
                route_receipt=route_path,
                output_root=self.root / "route-bound-b",
            )

    def test_qualification_parser_defaults_to_three_stable_roots(self) -> None:
        parsed = alpha_qualification.parser().parse_args(
            [
                "--source-revision",
                SOURCE,
                "--output-root",
                "out",
                "--python",
                "python",
                "--msbuild",
                "msbuild",
            ]
        )
        self.assertEqual(parsed.root_count, 3)
        self.assertEqual(parsed.cmake_generator, "Visual Studio 17 2022")
        self.assertFalse(parsed.trust_passed_roots)

    def test_complete_byte_table_hash_is_content_bound(self) -> None:
        value = b"a\t1\t" + b"0" * 64 + b"\n"
        self.assertEqual(digest_bytes(value), hashlib.sha256(value).hexdigest())

    def test_machine_receipt_is_deterministic_and_no_clobber(self) -> None:
        receipt = {"schema": "fixture", "authority": {"publication": False}}
        path = self.root / "receipt.json"
        alpha_asset_set.write_receipt(path, receipt)
        self.assertEqual(alpha_asset_set.load_json(path), receipt)
        with self.assertRaisesRegex(ValueError, "receipt path must be new"):
            alpha_asset_set.write_receipt(path, receipt)


if __name__ == "__main__":
    unittest.main()
