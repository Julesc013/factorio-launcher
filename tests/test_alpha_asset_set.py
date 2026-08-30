# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools import alpha_asset_set, alpha_qualification

SOURCE = "8362ddc55cbb98b538f4af410819c9503604ef99"
TREE = "859695fdcaead2e5e11c5454976432df13cacc1a"


class AlphaAssetSetTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.qualification = self.root / "qualification"
        self.root1 = self.qualification / "root1"
        self.root1.mkdir(parents=True)
        provider_lock = alpha_asset_set.load_toml(
            alpha_asset_set.ROOT / "release/index/providers.lock.v2.toml"
        )
        self.providers = [
            {
                "id": item["id"],
                "source_revision": item["source_revision"],
                "source_tree": item["source_tree"],
                "package_version": item["package_version"],
                "package_identity": (
                    f"{item['package_identity_kind']}:{item['package_digest']}"
                ),
                "abi_version": item["abi_version"],
                "abi_manifest_sha256": item["abi_manifest_digest"],
                "contract_set_id": item["contract_set_id"],
                "contract_digest": item["contract_digest"],
            }
            for item in provider_lock["provider"]
        ]
        self.packages = []
        for index, spec in enumerate(alpha_qualification.PACKAGE_SPECS, start=1):
            package_root = self.root1 / "packages" / spec["profile"]
            manifest = package_root / "manifest"
            licenses = package_root / "licenses"
            manifest.mkdir(parents=True)
            licenses.mkdir()
            (manifest / "package.v1.toml").write_text(
                f'profile = "{spec["profile"]}"\n', encoding="utf-8"
            )
            (manifest / "sbom.spdx.v2.3.json").write_text(
                json.dumps({"profile": spec["profile"]}) + "\n", encoding="utf-8"
            )
            (manifest / "hashes.sha256").write_text(
                f"{'a' * 64}  bin/facman.exe\n", encoding="utf-8"
            )
            (licenses / "LICENSE").write_text("fixture license\n", encoding="utf-8")
            dist = self.root1 / "dist"
            dist.mkdir(exist_ok=True)
            archive = dist / spec["filename"]
            archive.write_bytes(f"package-{index}".encode("ascii"))
            provenance = dist / f"{spec['filename']}.provenance.v1.json"
            provenance.write_text(
                json.dumps({"profile": spec["profile"]}) + "\n", encoding="utf-8"
            )
            licence = dist / f"{spec['filename']}.licence-inventory.v1.json"
            alpha_qualification.licence_inventory(
                package_root, licence, spec["profile"]
            )
            files = [path for path in package_root.rglob("*") if path.is_file()]
            self.packages.append(
                {
                    "id": spec["id"],
                    "profile": spec["profile"],
                    "filename": spec["filename"],
                    "source_revision": SOURCE,
                    "source_tree": TREE,
                    "providers": self.providers,
                    "contract_set_sha256": "1" * 64,
                    "state_identity": "facman.workspace.v1",
                    "package_tree_sha256": alpha_asset_set.sha256(
                        manifest / "hashes.sha256"
                    ),
                    "archive_sha256": alpha_asset_set.sha256(archive),
                    "embedded_manifest_sha256": alpha_asset_set.sha256(
                        manifest / "package.v1.toml"
                    ),
                    "sbom_sha256": alpha_asset_set.sha256(
                        manifest / "sbom.spdx.v2.3.json"
                    ),
                    "provenance_sha256": alpha_asset_set.sha256(provenance),
                    "licence_inventory_sha256": alpha_asset_set.sha256(licence),
                    "file_count": len(files),
                    "uncompressed_bytes": sum(path.stat().st_size for path in files),
                    "archive_bytes": archive.stat().st_size,
                }
            )
        self.comparison_path = self.qualification / "three-root-qualification.v1.json"
        self.comparison = {
            "schema": "facman.alpha1_final_dev_three_root_qualification.v1",
            "status": "pass",
            "source_revision": SOURCE,
            "source_tree": TREE,
            "root_count": 3,
            "roots": ["root1", "root2", "root3"],
            "packages": self.packages,
            "comparison_table_sha256": "2" * 64,
            "mismatch_count": 0,
            "mismatches": [],
            "classification": {
                "platform": "Windows 10/11 x64",
                "support": "unsupported alpha",
                "signed": False,
                "published": False,
                "distribution": "portable",
                "accepted_real_play_routes": 0,
            },
            "qualification": {
                "fresh_roots": "pass_in_every_root",
                "native_static_debug_release": "pass_in_every_root",
                "native_shared_debug_release": "pass_in_every_root",
                "package_runtime": "pass_in_every_root",
                "hash_manifest": "pass_in_every_root",
                "drift_refusal": "pass_in_every_root",
                "byte_identical_archives": "pass_in_every_root",
            },
            "authority": {
                "tagging": False,
                "signing": False,
                "publication": False,
                "support": False,
                "setup_mutation": False,
                "factorio_execution": False,
                "human_verdict": False,
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

    def _tag(self, machine: Path) -> Path:
        candidate = machine / "facman-0.1.0-alpha.1-candidate.v1.json"
        receipt = {
            "schema": "facman.alpha_tag_receipt.v1",
            "tag": "v0.1.0-alpha.1",
            "tag_object_sha": "3" * 40,
            "tag_ruleset_ids": [99],
            "source_revision": SOURCE,
            "source_tree": TREE,
            "candidate_sha256": alpha_asset_set.sha256(candidate),
            "eligibility_sha256": "4" * 64,
            "github_run_id": "123",
            "created_at": "2026-08-28T00:00:00Z",
            "publication": False,
            "signing": False,
        }
        path = self.root / "tag-receipt.json"
        self._write_json(path, receipt)
        output = self.root / "tag"
        alpha_asset_set.assemble_tag_assets(
            machine_root=machine, tag_receipt=path, output_root=output
        )
        return output

    def _route(self, tag_root: Path) -> Path:
        candidate = alpha_asset_set.load_json(
            tag_root / "facman-0.1.0-alpha.1-candidate.v1.json"
        )
        route_package = tag_root / "FacMan-0.1.0-alpha.1-windows-x64-portable.zip"
        route = {
            "schema": "facman.human_test_receipt.v1",
            "receipt_id": "facman.successor-play.human-verdict.05",
            "candidate": {
                "candidate_id": candidate["candidate_id"],
                "source_revision": SOURCE,
                "package_sha256": alpha_asset_set.sha256(route_package),
                "resolution_sha256": candidate["resolution"]["root_sha256"],
                "provider_lock_sha256": candidate["providers"]["provider_lock_sha256"],
            },
            "tester": "Jules",
            "tested_at": "2026-08-28T00:00:00Z",
            "environment": {
                "os": "Windows",
                "os_version": "11",
                "architecture": "x86_64",
                "display_profile": "route-observer",
                "assistive_technology": None,
            },
            "journeys": [
                {
                    "id": journey_id,
                    "version": "route-v5",
                    "result": "Pass",
                    "observations": ["Stable process and accepted direct observation."],
                }
                for journey_id in (
                    "facman.factorio-2-1-14.play-to-menu",
                    "facman.factorio-2-1-14.last-run-truth",
                    "facman.factorio-2-1-14.relaunch-save-visibility",
                )
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

    def _human(self, tag_root: Path) -> Path:
        candidate = alpha_asset_set.load_json(
            tag_root / "facman-0.1.0-alpha.1-candidate.v1.json"
        )
        packages = []
        for package in self.packages:
            package = copy.deepcopy(package)
            package.pop("source_revision")
            package.pop("source_tree")
            packages.append(package)
        lane_templates = alpha_asset_set.alpha_portable_test_packet.load_json(
            alpha_asset_set.alpha_portable_test_packet.TEMPLATE
        )["test_lanes"]
        human = {
            "schema": "facman.alpha1_portable_human_test_receipt.v1",
            "receipt_id": "facman-alpha1-exact-package-human-acceptance",
            "packet_status": "human_execution_complete",
            "candidate": {
                "source_revision": SOURCE,
                "source_tree": TREE,
                "qualification_sha256": candidate["evidence"]["test_summary_sha256"],
                "packages": packages,
            },
            "classification": {
                "windows_product": "Windows 10/11 x64 unsupported unsigned unpublished portable alpha",
                "linux_cli_tui": "exploratory package-preview evidence only",
                "linux_gtk": "frontend-only prototype; not a complete portable product package",
                "facman_sdk": "experimental engineering consumers; no public SDK compatibility promise",
                "accepted_real_play_routes": 0,
            },
            "tester": "human-observer",
            "tested_at": "2026-08-28T00:00:00Z",
            "environment": {"os": "Windows 11", "architecture": "x86_64"},
            "test_lanes": [
                {
                    "id": lane["id"],
                    "scope": lane["scope"],
                    "classification": lane["classification"],
                    "tester": "human-observer",
                    "result": "Pass",
                    "checks": copy.deepcopy(lane["checks"]),
                    "observations": ["accepted"],
                }
                for lane in lane_templates
            ],
            "result": "Pass",
            "observations": ["All exact-package lanes passed."],
            "accepted_limitations": [],
            "unresolved_findings": [],
            "authority": {
                "tagging": False,
                "beta_promotion": False,
                "stable_promotion": False,
                "route_promotion": False,
                "signing": False,
                "publication": False,
                "support": False,
                "factorio_execution": False,
            },
        }
        path = self.root / "human.json"
        self._write_json(path, human)
        return path

    def test_machine_assets_bind_three_packages_and_remain_non_authorizing(self) -> None:
        machine = self._machine()
        self.assertEqual(len(list(machine.iterdir())), 14)
        candidate = alpha_asset_set.load_json(
            machine / "facman-0.1.0-alpha.1-candidate.v1.json"
        )
        self.assertEqual(len(candidate["artifacts"]), 3)
        self.assertFalse(any(candidate["authority"].values()))

    def test_machine_assets_refuse_mismatch_authority_and_substitution(self) -> None:
        changed = copy.deepcopy(self.comparison)
        changed["mismatch_count"] = 1
        self._write_json(self.comparison_path, changed)
        with self.assertRaisesRegex(ValueError, "byte-identical"):
            self._machine()

        self._write_json(self.comparison_path, self.comparison)
        archive = self.root1 / "dist" / self.packages[0]["filename"]
        archive.write_bytes(b"substituted")
        with self.assertRaisesRegex(ValueError, "substituted"):
            self._machine()

    def test_tag_and_public_assembly_are_separate_exact_stages(self) -> None:
        machine = self._machine()
        tag = self._tag(machine)
        self.assertEqual(len(list(tag.iterdir())), 16)
        route = self._route(tag)
        human = self._human(tag)
        public = self.root / "public"
        receipt = alpha_asset_set.assemble_public_assets(
            tag_root=tag,
            route_receipt=route,
            human_receipt=human,
            output_root=public,
        )
        self.assertEqual(receipt["pending"], ["publication_authority"])
        self.assertEqual(len(list(public.iterdir())), 19)
        self.assertEqual(
            receipt["human_receipt_sha256"], alpha_asset_set.sha256(human)
        )
        self.assertFalse(any(receipt["authority"].values()))

    def test_public_assembly_refuses_inconclusive_or_substituted_human_evidence(self) -> None:
        machine = self._machine()
        tag = self._tag(machine)
        route = self._route(tag)
        human_path = self._human(tag)
        human = alpha_asset_set.load_json(human_path)
        human["packet_status"] = "exact_artifacts_bound_pending_human_execution"
        human["result"] = "Inconclusive"
        human["tested_at"] = None
        human["tester"] = "UNASSIGNED"
        for lane in human["test_lanes"]:
            lane["result"] = "Inconclusive"
            lane["tester"] = "UNASSIGNED"
        self._write_json(human_path, human)
        with self.assertRaisesRegex(ValueError, "completed human execution"):
            alpha_asset_set.assemble_public_assets(
                tag_root=tag,
                route_receipt=route,
                human_receipt=human_path,
                output_root=self.root / "inconclusive-public",
            )

        human_path = self.root / "human-substituted.json"
        human["packet_status"] = "human_execution_complete"
        human["result"] = "Pass"
        human["tested_at"] = "2026-08-28T00:00:00Z"
        human["tester"] = "human-observer"
        for lane in human["test_lanes"]:
            lane["result"] = "Pass"
            lane["tester"] = "human-observer"
        human["candidate"]["packages"][0]["archive_sha256"] = "f" * 64
        self._write_json(human_path, human)
        with self.assertRaisesRegex(ValueError, "archive differs"):
            alpha_asset_set.assemble_public_assets(
                tag_root=tag,
                route_receipt=route,
                human_receipt=human_path,
                output_root=self.root / "substituted-public",
            )

    def test_public_assembly_refuses_substituted_or_unobserved_human_lane(self) -> None:
        machine = self._machine()
        tag = self._tag(machine)
        route = self._route(tag)
        human_path = self._human(tag)
        human = alpha_asset_set.load_json(human_path)
        human["test_lanes"][0]["id"] = "substituted.lane"
        human["test_lanes"][1]["observations"] = []
        self._write_json(human_path, human)
        with self.assertRaisesRegex(ValueError, "exact nine ordered test lanes"):
            alpha_asset_set.assemble_public_assets(
                tag_root=tag,
                route_receipt=route,
                human_receipt=human_path,
                output_root=self.root / "substituted-lane-public",
            )

        human_path = self._human(tag)
        human = alpha_asset_set.load_json(human_path)
        human["test_lanes"][0]["checks"].append("unreviewed substituted check")
        self._write_json(human_path, human)
        with self.assertRaisesRegex(ValueError, "immutable field checks"):
            alpha_asset_set.assemble_public_assets(
                tag_root=tag,
                route_receipt=route,
                human_receipt=human_path,
                output_root=self.root / "substituted-check-public",
            )

    def test_tag_assembly_refuses_wrong_candidate_binding(self) -> None:
        machine = self._machine()
        candidate = machine / "facman-0.1.0-alpha.1-candidate.v1.json"
        receipt = {
            "schema": "facman.alpha_tag_receipt.v1",
            "tag": "v0.1.0-alpha.1",
            "tag_object_sha": "3" * 40,
            "tag_ruleset_ids": [99],
            "source_revision": SOURCE,
            "source_tree": TREE,
            "candidate_sha256": "0" * 64,
            "eligibility_sha256": "4" * 64,
            "github_run_id": "123",
            "created_at": "2026-08-28T00:00:00Z",
            "publication": False,
            "signing": False,
        }
        path = self.root / "wrong-tag.json"
        self._write_json(path, receipt)
        with self.assertRaisesRegex(ValueError, "candidate digest"):
            alpha_asset_set.assemble_tag_assets(
                machine_root=machine,
                tag_receipt=path,
                output_root=self.root / "wrong-tag-output",
            )
        self.assertTrue(candidate.is_file())

    def test_qualification_parser_defaults_to_three_fresh_roots(self) -> None:
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

    def test_qualification_script_entry_point_loads_repository_tools(self) -> None:
        completed = subprocess.run(
            [sys.executable, "tools/alpha_qualification.py", "--help"],
            cwd=alpha_qualification.ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("Build and compare all exact FacMan", completed.stdout)

    def test_qualification_command_failure_includes_log_tail(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            log = Path(temporary) / "failed-command.log"
            with self.assertRaisesRegex(RuntimeError, "qualification-log-tail"):
                alpha_qualification.run(
                    [
                        sys.executable,
                        "-c",
                        "print('qualification-log-tail'); raise SystemExit(7)",
                    ],
                    cwd=alpha_qualification.ROOT,
                    log=log,
                )
            self.assertIn("qualification-log-tail", log.read_text(encoding="utf-8"))

    def test_qualification_clone_is_full_and_non_promisor(self) -> None:
        destination = self.root / "facman"
        with (
            mock.patch.object(alpha_qualification, "run") as run_mock,
            mock.patch.object(
                alpha_qualification,
                "git",
                side_effect=[SOURCE, ""],
            ),
        ):
            alpha_qualification.clone_exact(
                url="https://example.invalid/facman.git",
                destination=destination,
                revision=SOURCE,
                branch="dev",
                log=self.root / "clone.log",
            )

        clone_command = run_mock.call_args_list[0].args[0]
        self.assertEqual(clone_command[:2], ["git", "clone"])
        self.assertIn("--no-local", clone_command)
        self.assertIn("--no-hardlinks", clone_command)
        self.assertIn("--no-checkout", clone_command)
        self.assertFalse(
            any(argument.startswith("--filter=") for argument in clone_command)
        )
        self.assertNotIn("--depth", clone_command)

    def test_comparison_detects_cross_root_archive_drift(self) -> None:
        other = copy.deepcopy(self.comparison)
        records = [
            {
                "root_id": "root1",
                "source_revision": SOURCE,
                "source_tree": TREE,
                "packages": copy.deepcopy(self.packages),
            },
            {
                "root_id": "root2",
                "source_revision": SOURCE,
                "source_tree": TREE,
                "packages": copy.deepcopy(self.packages),
            },
        ]
        records[1]["packages"][0]["archive_sha256"] = "f" * 64
        mismatches, _table = alpha_qualification.compare_records(records)
        self.assertEqual(mismatches[0]["field"], "archive_sha256")
        self.assertEqual(other["mismatch_count"], 0)

    def test_machine_receipt_is_deterministic_and_no_clobber(self) -> None:
        receipt = {"schema": "fixture", "authority": {"publication": False}}
        path = self.root / "receipt.json"
        alpha_asset_set.write_receipt(path, receipt)
        self.assertEqual(alpha_asset_set.load_json(path), receipt)
        with self.assertRaisesRegex(ValueError, "receipt path must be new"):
            alpha_asset_set.write_receipt(path, receipt)


if __name__ == "__main__":
    unittest.main()
