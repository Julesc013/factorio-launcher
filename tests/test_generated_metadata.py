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
        commands = data["commands"]
        self.assertEqual(len(commands), len(index["files"]))
        self.assertEqual(len({item["command_id"] for item in commands}), len(commands))
        self.assertEqual(
            {item["runtime_id"] for item in commands if item["registered"]},
            set(index["registered"]),
        )

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
