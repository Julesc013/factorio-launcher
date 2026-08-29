# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import copy
import hashlib
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from tools import alpha_portable_test_packet as packet


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class AlphaPortableTestPacketTests(unittest.TestCase):
    def qualification(self, root: Path) -> tuple[Path, Path]:
        providers = [
            {
                "id": provider_id,
                "source_revision": revision,
                "source_tree": tree,
                "package_version": "0.1.0-alpha.1",
                "package_identity": f"sha256:{'3' * 64}",
                "abi_version": "1",
                "abi_manifest_sha256": "4" * 64,
                "contract_set_id": "facman.contracts.v1",
                "contract_digest": "5" * 64,
            }
            for provider_id, revision, tree in (
                ("universal_launcher", "6" * 40, "7" * 40),
                ("universal_setup", "8" * 40, "9" * 40),
            )
        ]
        specs = (
            ("windows_cli_x64_portable", "windows_portable_cli_x64", "facman-0.1.0-alpha.1-windows-cli-x64-portable.zip"),
            ("windows_tui_x64_portable", "windows_portable_tui_x64", "facman-0.1.0-alpha.1-windows-tui-x64-portable.zip"),
            ("windows_winforms_x64_portable", "windows_legacy_winforms_x64", "FacMan-0.1.0-alpha.1-windows-x64-portable.zip"),
        )
        machine = root / "machine"
        machine.mkdir()
        packages = []
        for index, (package_id, profile, filename) in enumerate(specs):
            archive = machine / filename
            members = {
                "manifest/hashes.sha256": f"{package_id}/hashes".encode(),
                "manifest/package.v1.toml": f"{package_id}/manifest".encode(),
            }
            with zipfile.ZipFile(archive, "w") as package_archive:
                for name, payload in members.items():
                    package_archive.writestr(name, payload)
            sidecars = {}
            for role, suffix in (
                ("sbom", ".sbom.spdx.v2.3.json"),
                ("provenance", ".provenance.v1.json"),
                ("licence_inventory", ".licence-inventory.v1.json"),
            ):
                path = machine / f"{filename}{suffix}"
                path.write_bytes(f"{package_id}/{role}".encode())
                sidecars[role] = path
            packages.append(
                {
                    "id": package_id,
                    "profile": profile,
                    "filename": filename,
                    "source_revision": "a" * 40,
                    "source_tree": "b" * 40,
                    "providers": providers,
                    "contract_set_sha256": "c" * 64,
                    "state_identity": "facman.workspace.v1",
                    "package_tree_sha256": hashlib.sha256(members["manifest/hashes.sha256"]).hexdigest(),
                    "archive_sha256": digest(archive),
                    "embedded_manifest_sha256": hashlib.sha256(members["manifest/package.v1.toml"]).hexdigest(),
                    "sbom_sha256": digest(sidecars["sbom"]),
                    "provenance_sha256": digest(sidecars["provenance"]),
                    "licence_inventory_sha256": digest(sidecars["licence_inventory"]),
                    "file_count": len(members),
                    "uncompressed_bytes": sum(len(payload) for payload in members.values()),
                    "archive_bytes": archive.stat().st_size,
                }
            )
        value = {
            "schema": "facman.alpha1_final_dev_three_root_qualification.v1",
            "status": "pass",
            "source_revision": "a" * 40,
            "source_tree": "b" * 40,
            "root_count": 3,
            "roots": ["root1", "root2", "root3"],
            "packages": packages,
            "comparison_table_sha256": "e" * 64,
            "mismatch_count": 0,
            "mismatches": [],
            "classification": {
                "platform": "Windows 10/11 x64", "support": "unsupported alpha",
                "signed": False, "published": False, "distribution": "portable",
                "accepted_real_play_routes": 0,
            },
            "qualification": {
                key: "pass_in_every_root"
                for key in (
                    "fresh_roots", "native_static_debug_release", "native_shared_debug_release",
                    "package_runtime", "hash_manifest", "drift_refusal", "byte_identical_archives",
                )
            },
            "authority": {
                "tagging": False, "signing": False, "publication": False, "support": False,
                "setup_mutation": False, "factorio_execution": False, "human_verdict": False,
            },
        }
        path = root / "three-root-qualification.v1.json"
        path.write_text(json.dumps(value), encoding="utf-8")
        return path, machine

    def test_tracked_template_is_unbound_and_human_only(self) -> None:
        self.assertEqual(packet.validate(packet.load_json(packet.TEMPLATE), bound=False), [])

    def test_bind_records_all_exact_packages_and_keeps_verdict_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _, machine = self.qualification(root)
            value = packet.bound_record(root, machine)
            self.assertEqual(packet.validate(value, bound=True), [])
            self.assertEqual([item["id"] for item in value["candidate"]["packages"]], list(packet.PACKAGE_IDS))
            self.assertTrue(all(item["result"] == "Inconclusive" for item in value["test_lanes"]))

    def test_bind_refuses_changed_package_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            qualification, machine = self.qualification(root)
            value = json.loads(qualification.read_text(encoding="utf-8"))
            (machine / value["packages"][0]["filename"]).write_bytes(b"drift")
            with self.assertRaisesRegex(ValueError, "absent or differs"):
                packet.bound_record(root, machine)

    def test_completed_packet_requires_exact_observed_lanes_and_assigned_environment(self) -> None:
        value = copy.deepcopy(packet.load_json(packet.TEMPLATE))
        value["packet_status"] = "human_execution_complete"
        value["tester"] = "Jules"
        value["tested_at"] = "2026-08-30T00:00:00Z"
        value["environment"] = {"windows": "Windows 11", "linux_preview": "Ubuntu 24.04"}
        value["result"] = "Pass"
        value["observations"] = ["All declared lanes were directly assessed."]
        value["unresolved_findings"] = []
        for lane in value["test_lanes"]:
            lane["tester"] = "Jules"
            lane["result"] = "Pass"
            lane["observations"] = ["Direct observation recorded."]
        self.assertEqual(packet.completed_human_problems(value), [])

        value["test_lanes"][0]["id"] = "substituted.lane"
        value["test_lanes"][1]["tester"] = "UNASSIGNED"
        value["test_lanes"][2]["observations"] = []
        value["environment"]["linux_preview"] = "UNASSIGNED"
        problems = packet.completed_human_problems(value)
        self.assertTrue(any("exact nine ordered" in item for item in problems), problems)
        self.assertTrue(any("assigned tester" in item for item in problems), problems)
        self.assertTrue(any("direct observations" in item for item in problems), problems)
        self.assertTrue(any("assigned test environments" in item for item in problems), problems)


if __name__ == "__main__":
    unittest.main()
