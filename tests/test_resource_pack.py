# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import tempfile
import unittest
import zipfile
from pathlib import Path

from tools import package_runtime_smoke, resource_pack


class ResourcePackTests(unittest.TestCase):
    def test_pack_is_reproducible_and_verifiable(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = root / "first.resources"
            second = root / "second.resources"
            first_record = resource_pack.build(resource_pack.ROOT, first)
            second_record = resource_pack.build(resource_pack.ROOT, second)
            self.assertEqual(first.read_bytes(), second.read_bytes())
            self.assertEqual(first_record["sha256"], second_record["sha256"])
            verified = resource_pack.verify(first)
            self.assertEqual(verified["status"], "pass")
            self.assertGreater(verified["entry_count"], 100)
            self.assertIn("contracts/schema/common/result.v1.schema.json", verified["entries"])
            self.assertIn("content/factorio/product/factorio.product.toml", verified["entries"])
            self.assertNotIn("release/index/plan.v1.toml", verified["entries"])

    def test_export_requires_a_new_destination(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            pack = root / "facman.resources"
            destination = root / "exported"
            resource_pack.build(resource_pack.ROOT, pack)
            record = resource_pack.export(pack, destination)
            self.assertEqual(record["status"], "pass")
            self.assertTrue((destination / resource_pack.MANIFEST_PATH).is_file())
            with self.assertRaisesRegex(ValueError, "must not exist"):
                resource_pack.export(pack, destination)

    def test_tampered_payload_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            pack = root / "facman.resources"
            resource_pack.build(resource_pack.ROOT, pack)
            with zipfile.ZipFile(pack, "a") as archive:
                archive.writestr("contracts/schema/common/result.v1.schema.json", b"{}\n")
            with self.assertRaisesRegex(ValueError, "duplicate|colliding"):
                resource_pack.verify(pack)

    def test_package_runtime_accepts_the_embedded_resource_layout(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest = root / "manifest"
            manifest.mkdir()
            for name in (
                "package.v1.toml", "components.v1.json", "hashes.sha256",
                "sbom.spdx.v2.3.json",
            ):
                (manifest / name).touch()
            resource_pack.build(resource_pack.ROOT, root / "facman.resources")
            layout, schema = package_runtime_smoke.assert_required_layout(root)
            self.assertEqual("embedded", layout["layout"])
            self.assertEqual(
                "https://json-schema.org/draft/2020-12/schema",
                schema["$schema"],
            )


if __name__ == "__main__":
    unittest.main()
