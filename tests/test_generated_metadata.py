# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import hashlib
import json
import re
import tomllib
import unittest
from pathlib import Path

from tools.codegen import generate_metadata


def canonical_schema_tree_digest() -> str:
    hasher = hashlib.sha256()
    paths = sorted(
        (path for path in generate_metadata.SCHEMA_ROOT.rglob("*") if path.is_file()),
        key=lambda path: path.relative_to(generate_metadata.ROOT).as_posix(),
    )
    for path in paths:
        relative_path = path.relative_to(generate_metadata.ROOT).as_posix()
        contents = path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
        hasher.update(relative_path.encode("utf-8"))
        hasher.update(b"\0")
        hasher.update(contents)
        hasher.update(b"\0")
    return hasher.hexdigest()


def generated_value(text: str, pattern: str) -> str:
    match = re.search(pattern, text, flags=re.MULTILINE)
    if match is None:
        raise AssertionError(f"generated digest constant not found: {pattern}")
    return match.group(1)


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

    def test_generated_digest_constants_match_canonical_inputs(self) -> None:
        _index, _version, commands, command_catalog_digest = generate_metadata.load_sources()
        contract_set_digest = canonical_schema_tree_digest()
        self.assertRegex(command_catalog_digest, r"^[0-9a-f]{64}$")
        self.assertRegex(contract_set_digest, r"^[0-9a-f]{64}$")
        self.assertEqual(generate_metadata.contract_set_digest(commands), contract_set_digest)

        for output_name in ("catalog_json", "grammar_json", "frontend_json"):
            generated = json.loads(
                generate_metadata.OUTPUTS[output_name].read_text(encoding="utf-8")
            )
            self.assertEqual(generated["source_digest"], command_catalog_digest)

        version_header = generate_metadata.OUTPUTS["version_header"].read_text(
            encoding="utf-8"
        )
        self.assertEqual(
            generated_value(
                version_header,
                r'^#define FACMAN_COMMAND_CATALOG_SHA256 "([0-9a-f]{64})"$',
            ),
            command_catalog_digest,
        )
        self.assertEqual(
            generated_value(
                version_header,
                r'^#define FACMAN_CONTRACT_SET_SHA256 "([0-9a-f]{64})"$',
            ),
            contract_set_digest,
        )

        winforms_catalog = generate_metadata.OUTPUTS["winforms_catalog"].read_text(
            encoding="utf-8"
        )
        self.assertEqual(
            generated_value(
                winforms_catalog,
                r'public static string CommandCatalogSha256 \{ get \{ return "([0-9a-f]{64})"; \} \}',
            ),
            command_catalog_digest,
        )
        self.assertEqual(
            generated_value(
                winforms_catalog,
                r'public static string ContractSetSha256 \{ get \{ return "([0-9a-f]{64})"; \} \}',
            ),
            contract_set_digest,
        )

    def test_digest_framing_normalizes_line_endings(self) -> None:
        expected = hashlib.sha256(b"contracts/schema/example.json\0value\n\0").hexdigest()
        for contents in (b"value\n", b"value\r\n", b"value\r"):
            hasher = hashlib.sha256()
            generate_metadata.digest_entry(
                hasher, Path("contracts/schema/example.json"), contents
            )
            self.assertEqual(hasher.hexdigest(), expected)


if __name__ == "__main__":
    unittest.main()
