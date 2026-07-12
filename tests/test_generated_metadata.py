# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import json
import tomllib
import unittest

from tools.codegen import generate_metadata


class GeneratedMetadataTests(unittest.TestCase):
    def test_generated_outputs_match_canonical_inputs(self) -> None:
        self.assertEqual(generate_metadata.generate(write=False), [])

    def test_catalog_covers_every_indexed_contract_once(self) -> None:
        with generate_metadata.INDEX.open("rb") as handle:
            index = tomllib.load(handle)
        data = json.loads(generate_metadata.OUTPUTS["catalog_json"].read_text(encoding="utf-8"))
        self.assertEqual(data["schema"], "facman.generated_command_catalog.v2")
        commands = data["commands"]
        self.assertEqual(len(commands), len(index["files"]))
        self.assertEqual(len({item["command_id"] for item in commands}), len(commands))
        self.assertEqual(
            {item["runtime_id"] for item in commands if item["registered"]},
            set(index["registered"]),
        )
        for item in commands:
            self.assertTrue(item["native_id"])
            self.assertIsInstance(item["aliases"], list)
            self.assertEqual(item["writes_state"], "workspace_write" in item["effects"])

    def test_application_command_surfaces_are_generated(self) -> None:
        generated = {
            name: generate_metadata.OUTPUTS[name].read_text(encoding="utf-8")
            for name in ("application_ids", "application_lookup", "application_names", "application_writes")
        }
        self.assertIn("product_inspect", generated["application_ids"])
        self.assertIn('value == "dev.bug-report"', generated["application_lookup"])
        self.assertIn('return "product.inspect"', generated["application_names"])
        self.assertIn("CommandId::diagnostics_export", generated["application_writes"])

    def test_version_header_and_build_manifest_share_the_version_contract(self) -> None:
        with generate_metadata.VERSION.open("rb") as handle:
            version = tomllib.load(handle)
        with (generate_metadata.ROOT / "release/index/build_manifest.v1.toml").open("rb") as handle:
            build = tomllib.load(handle)
        header = generate_metadata.OUTPUTS["version_header"].read_text(encoding="utf-8")
        for key in ["canonical_version", "filename_version"]:
            self.assertEqual(build[key], version[key])
            self.assertIn(version[key], header)


if __name__ == "__main__":
    unittest.main()
