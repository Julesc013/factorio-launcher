# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from tools import package_contract_tck, product_candidate
from tools.package.archive_inventory import zip_inventory
from tools.package.candidate_evidence import verify_bundle
from tools.package.payload_equivalence import PAYLOAD_ADAPTERS


VERSION = "0.1.0-alpha.5"
REVISION = "1" * 40
TREE = "2" * 40
REPOSITORY = "Julesc013/factorio-launcher"
WORKFLOW_REF = (
    f"{REPOSITORY}/.github/workflows/product-candidate.yml@refs/heads/candidate-test"
)


def provenance(job: str, attempt: str = "1") -> dict[str, str]:
    return product_candidate.github_provenance(
        REPOSITORY, WORKFLOW_REF, "123456", attempt, job
    )


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def valid_equivalence(
    platform: str,
    portable: dict[str, object],
    setup: dict[str, object],
) -> dict[str, object]:
    adapter_id = product_candidate.ADAPTERS[platform]
    adapter = PAYLOAD_ADAPTERS[adapter_id]
    digest = hashlib.sha256(f"{platform}-stage".encode()).hexdigest()
    return {
        "schema": "facman.package_payload_equivalence_tck.v1",
        "status": "pass",
        "authority": "contract_test_only_no_release_qualification",
        "adapter": adapter_id,
        "profile": adapter.profile_id,
        "canonical_file_count": 2,
        "canonical_stage_digest": digest,
        "payload_runtime_file_count": 2,
        "payload_runtime_digest": digest,
        "adapter_owned_files": list(adapter.required_adapter_files),
        "canonical_artifact": portable,
        "payload_artifact": setup,
        "problems": [],
    }


def rebind_manifest(root: Path) -> None:
    manifest = root / "product-candidate-bundle.v1.json"
    record = product_candidate.read_json(manifest)
    for field in ("assets", "evidence"):
        record[field] = [
            product_candidate.asset_record(root / item["filename"])
            for item in record[field]
        ]
    checksum = root / "SHA256SUMS"
    checksum.write_text(
        "".join(
            f"{item['sha256']}  {item['filename']}\n"
            for item in record["assets"] + record["evidence"]
        ),
        encoding="utf-8",
        newline="\n",
    )
    record["checksum"] = product_candidate.asset_record(checksum)
    write_json(manifest, record)


class ProductCandidateTests(unittest.TestCase):
    def populate_platform(
        self, inputs: Path, platform: str, github: dict[str, str] | None = None
    ) -> Path:
        root = inputs / platform
        suffixes = product_candidate.ASSET_SUFFIXES[platform]
        portable = root / "dist" / f"FacMan-{VERSION}-{suffixes[0]}"
        setup = root / "setup" / f"FacMan-{VERSION}-{suffixes[1]}"
        portable.parent.mkdir(parents=True)
        setup.parent.mkdir(parents=True)
        portable.write_bytes(f"{platform}-portable".encode())
        setup.write_bytes(f"{platform}-setup".encode())
        assets = [product_candidate.asset_record(portable), product_candidate.asset_record(setup)]
        receipt = root / "evidence" / f"{platform}-payload-equivalence.v1.json"
        write_json(receipt, valid_equivalence(platform, *assets))
        with patch.object(product_candidate, "source_tree", return_value=TREE):
            product_candidate.platform_record(
                root, VERSION, platform, REVISION, github or provenance("platform")
            )
        return receipt

    def assemble(self, root: Path) -> tuple[Path, Path, Path]:
        inputs = root / "inputs"
        for platform in product_candidate.ASSET_SUFFIXES:
            self.populate_platform(inputs, platform)
        output = root / "bundle"
        with patch.object(product_candidate, "source_tree", return_value=TREE):
            record = product_candidate.bundle(
                inputs, output, VERSION, REVISION, provenance("bundle"), "platform"
            )
        return inputs, output, record

    def test_bundle_binds_exactly_six_assets_and_complete_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            _, output, record_path = self.assemble(Path(temporary))
            record = product_candidate.read_json(record_path)
            self.assertEqual(6, len(record["assets"]))
            self.assertEqual(provenance("bundle"), record["github"])
            self.assertEqual("platform", record["platform_job"])
            self.assertEqual(TREE, record["source_tree"])
            self.assertEqual(product_candidate.AUTHORITY, record["authority"])
            self.assertEqual(record, verify_bundle(output))

    def test_standalone_verify_and_exact_output_allowlist(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            _, output, _ = self.assemble(Path(temporary))
            expected = {
                *(f"FacMan-{VERSION}-{suffix}" for values in product_candidate.ASSET_SUFFIXES.values() for suffix in values),
                *(f"{platform}-candidate-evidence.v1.json" for platform in product_candidate.ASSET_SUFFIXES),
                *(f"{platform}-payload-equivalence.v1.json" for platform in product_candidate.ASSET_SUFFIXES),
                "SHA256SUMS",
                "product-candidate-bundle.v1.json",
            }
            self.assertEqual(expected, {path.name for path in output.iterdir()})
            self.assertEqual(0, product_candidate.main(["verify", "--root", str(output)]))
            (output / "unexpected.txt").write_text("unexpected", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "output allowlist differs"):
                verify_bundle(output)
            (output / "unexpected.txt").unlink()
            (output / "unexpected-directory").mkdir()
            with self.assertRaisesRegex(ValueError, "non-file"):
                verify_bundle(output)

    def test_each_emitted_file_tamper_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _, output, _ = self.assemble(root)
            names = sorted(path.name for path in output.iterdir())
            self.assertEqual(14, len(names))
            for index, name in enumerate(names):
                with self.subTest(name=name):
                    case = root / f"tamper-{index}"
                    shutil.copytree(output, case)
                    with (case / name).open("ab") as stream:
                        stream.write(b"tamper")
                    with self.assertRaises((ValueError, json.JSONDecodeError)):
                        verify_bundle(case)

    def test_coordinated_rehash_cannot_elevate_or_relabel_evidence(self) -> None:
        mutations = (
            ("windows-candidate-evidence.v1.json", ("authority", "release"), True),
            ("macos-candidate-evidence.v1.json", ("github", "run_attempt"), "2"),
            ("linux-candidate-evidence.v1.json", ("payload_equivalence", "adapter"), "other"),
            ("windows-payload-equivalence.v1.json", ("profile",), "other"),
        )
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _, output, _ = self.assemble(root)
            for index, (name, keys, replacement) in enumerate(mutations):
                with self.subTest(name=name, keys=keys):
                    case = root / f"rebound-{index}"
                    shutil.copytree(output, case)
                    target = case / name
                    value = product_candidate.read_json(target)
                    nested: dict[str, object] = value
                    for key in keys[:-1]:
                        child = nested[key]
                        self.assertIsInstance(child, dict)
                        nested = child  # type: ignore[assignment]
                    nested[keys[-1]] = replacement
                    write_json(target, value)
                    rebind_manifest(case)
                    with self.assertRaises(ValueError):
                        verify_bundle(case)

    def test_bundle_refuses_mixed_run_attempts(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            inputs = root / "inputs"
            for platform in product_candidate.ASSET_SUFFIXES:
                github = provenance("platform", "2" if platform == "macos" else "1")
                self.populate_platform(inputs, platform, github)
            with (
                patch.object(product_candidate, "source_tree", return_value=TREE),
                self.assertRaisesRegex(ValueError, "GitHub provenance differs"),
            ):
                product_candidate.bundle(
                    inputs, root / "bundle", VERSION, REVISION,
                    provenance("bundle"), "platform",
                )

    def test_malformed_provenance_refuses_cleanly(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _, output, _ = self.assemble(root)
            manifest = output / "product-candidate-bundle.v1.json"
            for index, operation in enumerate(("missing", "extra")):
                with self.subTest(operation=operation):
                    case = root / f"provenance-{index}"
                    shutil.copytree(output, case)
                    value = product_candidate.read_json(
                        case / "product-candidate-bundle.v1.json"
                    )
                    if operation == "missing":
                        del value["github"]["job"]
                    else:
                        value["github"]["unexpected"] = "value"
                    write_json(case / manifest.name, value)
                    with self.assertRaisesRegex(ValueError, "provenance fields differ"):
                        verify_bundle(case)
                    self.assertEqual(
                        1, product_candidate.main(["verify", "--root", str(case)])
                    )

    def test_bundle_refuses_asset_or_equivalence_tampering(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            inputs = root / "inputs"
            receipts = {
                platform: self.populate_platform(inputs, platform)
                for platform in product_candidate.ASSET_SUFFIXES
            }
            windows_setup = inputs / "windows/setup" / f"FacMan-{VERSION}-windows-x64-setup.exe"
            windows_setup.write_bytes(b"tampered setup")
            with patch.object(product_candidate, "source_tree", return_value=TREE), self.assertRaises(ValueError):
                product_candidate.bundle(
                    inputs, root / "asset-tamper", VERSION, REVISION,
                    provenance("bundle"), "platform",
                )
            windows_setup.write_bytes(b"windows-setup")
            receipt = product_candidate.read_json(receipts["macos"])
            receipt["canonical_stage_digest"] = "3" * 64
            receipt["payload_runtime_digest"] = "3" * 64
            write_json(receipts["macos"], receipt)
            with patch.object(product_candidate, "source_tree", return_value=TREE), self.assertRaises(ValueError):
                product_candidate.bundle(
                    inputs, root / "receipt-tamper", VERSION, REVISION,
                    provenance("bundle"), "platform",
                )

    def test_source_tree_refuses_wrong_head_and_dirty_checkout(self) -> None:
        cases = (("3" * 40, ""), (REVISION, " M tracked-file"))
        for head, status in cases:
            with self.subTest(head=head, status=status), patch.object(
                product_candidate.subprocess, "check_output", side_effect=[head, status]
            ), self.assertRaisesRegex(ValueError, "exact clean requested revision"):
                product_candidate.source_tree(REVISION)

    def test_self_extracting_zip_inventory_hashes_only_bounded_members(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            setup = Path(temporary) / "FacManSetup.exe"
            setup.write_bytes(b"MZ bounded bootstrap")
            info = zipfile.ZipInfo("facman/generations/test/facman.exe")
            info.create_system = 3
            info.external_attr = 0o100755 << 16
            with zipfile.ZipFile(setup, "a", compression=zipfile.ZIP_STORED) as archive:
                archive.writestr(info, b"runtime")
            records = zip_inventory(setup)
            self.assertEqual(1, len(records))
            self.assertEqual("facman/generations/test/facman.exe", records[0].path)
            self.assertEqual(hashlib.sha256(b"runtime").hexdigest(), records[0].sha256)
            self.assertEqual(0o755, records[0].mode)

    def test_archive_inventory_refuses_noncanonical_member_spelling(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            archive_path = Path(temporary) / "payload.zip"
            with zipfile.ZipFile(archive_path, "w") as archive:
                archive.writestr("facman//runtime", b"runtime")
            with self.assertRaisesRegex(ValueError, "non-canonical ZIP member"):
                zip_inventory(archive_path)

    def test_failed_equivalence_never_writes_a_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            stage = root / "stage"
            stage.mkdir()
            (stage / "FacMan.exe").write_bytes(b"canonical")
            setup = root / "setup.exe"
            with zipfile.ZipFile(setup, "w") as archive:
                archive.writestr(f"facman/generations/{VERSION}/FacMan.exe", b"tampered")
                archive.writestr("facman/maintenance/FacManSetup.exe", b"setup")
                archive.writestr("facman/state/current-generation.v1.json", b"state")
            receipt = root / "receipt.json"
            result = package_contract_tck.main([
                "--profile", "windows_product_x64", "--canonical-stage", str(stage),
                "--payload-zip", str(setup), "--adapter", "windows_setup_overlay_v1",
                "--version", VERSION, "--receipt", str(receipt),
            ])
            self.assertEqual(1, result)
            self.assertFalse(receipt.exists())

    def test_success_receipt_binds_artifacts_and_refuses_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            stage = root / "stage"
            stage.mkdir()
            (stage / "FacMan.exe").write_bytes(b"canonical")
            portable = root / f"FacMan-{VERSION}-windows-x64-portable.zip"
            portable.write_bytes(b"portable")
            setup = root / f"FacMan-{VERSION}-windows-x64-setup.exe"
            with zipfile.ZipFile(setup, "w") as archive:
                archive.writestr(f"facman/generations/{VERSION}/FacMan.exe", b"canonical")
                archive.writestr("facman/maintenance/FacManSetup.exe", b"setup")
                archive.writestr("facman/state/current-generation.v1.json", b"state")
            receipt = root / "evidence/receipt.json"
            arguments = [
                "--profile", "windows_product_x64", "--canonical-stage", str(stage),
                "--payload-zip", str(setup), "--canonical-artifact", str(portable),
                "--payload-artifact", str(setup), "--adapter", "windows_setup_overlay_v1",
                "--version", VERSION, "--receipt", str(receipt),
            ]
            self.assertEqual(0, package_contract_tck.main(arguments))
            value = json.loads(receipt.read_text(encoding="utf-8"))
            self.assertEqual(product_candidate.asset_record(portable), value["canonical_artifact"])
            self.assertEqual(product_candidate.asset_record(setup), value["payload_artifact"])
            original = receipt.read_bytes()
            self.assertEqual(1, package_contract_tck.main(arguments))
            self.assertEqual(original, receipt.read_bytes())


if __name__ == "__main__":
    unittest.main()
