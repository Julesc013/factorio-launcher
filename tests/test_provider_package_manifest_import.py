# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import copy
import ctypes
import dataclasses
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from typing import Any

import jsonschema

from tools import provider_package_manifest_import as provider_import


ROOT = Path(__file__).resolve().parents[1]


class ProviderPackageManifestImportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.source = self.root / "provider-source"
        self.source.mkdir()
        self._git("init", "--initial-branch=main")
        self._git("config", "user.email", "provider-fixture@example.invalid")
        self._git("config", "user.name", "Provider Fixture")
        (self.source / "provider.txt").write_text("provider\n", encoding="utf-8")
        self._git("add", "provider.txt")
        self._git("commit", "-m", "fixture provider")
        self.commit = self._git("rev-parse", "HEAD")
        self.tree = self._git("rev-parse", "HEAD^{tree}")
        self.packages = self._build_matrix()
        self.policy = self._policy()
        self.index = self.root / "index"
        self.index.mkdir()
        for filename in provider_import.INDEX_FILENAMES:
            shutil.copy2(ROOT / "release" / "index" / filename, self.index / filename)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _git(self, *arguments: str) -> str:
        completed = subprocess.run(
            ["git", *arguments],
            cwd=self.source,
            check=True,
            text=True,
            encoding="utf-8",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        return completed.stdout.strip()

    @staticmethod
    def _entry(root: Path, path: Path) -> dict[str, Any]:
        return {
            "path": path.relative_to(root).as_posix(),
            "sha256": provider_import.sha256_file(path),
            "size": path.stat().st_size,
        }

    def _build_package(self, system: str, linkage: str) -> tuple[Path, Path]:
        root = self.root / "packages" / f"{system}-{linkage}"
        native_schema = {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "$id": "https://example.invalid/fixture.provider_package_manifest.v1.schema.json",
            "type": "object",
            "additionalProperties": False,
            "required": [
                "schema",
                "source",
                "provider",
                "package",
                "inventories",
                "licence",
                "qualification",
            ],
            "properties": {
                "schema": {"const": "fixture.provider_package_manifest.v1"},
                "source": {"type": "object"},
                "provider": {"type": "object"},
                "package": {"type": "object"},
                "inventories": {"type": "object"},
                "licence": {"type": "object"},
                "qualification": {"type": "object"},
            },
        }
        files = {
            "include/provider/provider.h": "#define PROVIDER_ABI 0x00010009\n",
            "share/provider/contracts/contract.json": '{"contract":1}\n',
            "share/provider/contracts/provider_package_manifest.v1.schema.json": (
                json.dumps(native_schema, indent=2, sort_keys=True) + "\n"
            ),
            "share/provider/abi/provider.v1.toml": 'schema = "provider.abi.v1"\n',
            "share/licenses/provider/LICENSE": "fixture licence\n",
            f"lib/{system}-{linkage}.bin": f"{system}:{linkage}\n",
        }
        for relative, content in files.items():
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        artifacts = [
            self._entry(root, path)
            for path in sorted(root.rglob("*"), key=lambda item: item.as_posix())
            if path.is_file()
        ]
        contracts = [
            entry
            for entry in artifacts
            if entry["path"].startswith("share/provider/contracts/")
            or entry["path"].startswith("share/provider/abi/")
        ]
        headers = [entry for entry in artifacts if entry["path"].startswith("include/")]
        manifest = {
            "schema": "fixture.provider_package_manifest.v1",
            "source": {
                "commit": self.commit,
                "ref": "refs/heads/main",
                "repository": "Example/provider",
                "tree": self.tree,
            },
            "provider": {
                "id": "fixture-provider",
                "package_version": "1.9.1",
                "c_abi": {
                    "major": 1,
                    "minor": 9,
                    "manifest_sha256": "a" * 64,
                },
                "state_format": {
                    "read_versions": [1, 2],
                    "write_version": 2,
                },
                "maturity": "experimental_prerelease",
            },
            "package": {
                "os": {"linux": "Linux", "macos": "Darwin", "windows": "Windows"}[
                    system
                ],
                "architecture": "x86_64",
                "configuration": "Release",
                "linkage": linkage,
                "installed_targets": [
                    "Provider::Headers",
                    f"Provider::Core{linkage.title()}",
                ],
            },
            "inventories": {
                "artifacts": artifacts,
                "artifacts_sha256": provider_import.sha256_bytes(
                    provider_import.canonical_json_bytes(artifacts)
                ),
                "contracts": contracts,
                "contracts_sha256": provider_import.sha256_bytes(
                    provider_import.canonical_json_bytes(contracts)
                ),
                "public_headers": headers,
                "public_headers_sha256": provider_import.sha256_bytes(
                    provider_import.canonical_json_bytes(headers)
                ),
            },
            "licence": {"expression": "MIT"},
            "qualification": {"tck_revision": self.commit},
        }
        path = root / "share/provider/provider-package-manifest.v1.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(provider_import.canonical_json_bytes(manifest))
        return path, root

    def _build_matrix(self) -> list[tuple[Path, Path]]:
        return [
            self._build_package(system, linkage)
            for system, linkage in sorted(provider_import.EXPECTED_PROFILES)
        ]

    def _policy(self) -> provider_import.ImportPolicy:
        manifests = [
            json.loads(path.read_text(encoding="utf-8")) for path, _ in self.packages
        ]
        artifact_digests = {
            f"{provider_import._normalized_system(manifest['package']['os'])}/"
            f"{manifest['package']['linkage']}": manifest["inventories"][
                "artifacts_sha256"
            ]
            for manifest in manifests
        }
        inventory = manifests[0]["inventories"]
        return provider_import.ImportPolicy(
            provider_id="universal_launcher",
            manifest_provider_id="fixture-provider",
            manifest_schema="fixture.provider_package_manifest.v1",
            repository="Example/provider",
            source_ref="refs/heads/main",
            package_version="1.9.1",
            abi_major=1,
            abi_minor=9,
            abi_manifest_sha256="a" * 64,
            state_formats={
                "state_format": {
                    "read_versions": [1, 2],
                    "write_version": 2,
                }
            },
            artifacts_sha256=artifact_digests,
            contracts_sha256=inventory["contracts_sha256"],
            contract_set=tuple(
                (entry["path"], entry["size"], entry["sha256"])
                for entry in inventory["contracts"]
            ),
            contract_set_sha256=inventory["contracts_sha256"],
            public_headers_sha256=inventory["public_headers_sha256"],
            configuration="Release",
            architecture="x86_64",
            licence="MIT",
            required_targets={
                "static": ("Provider::Headers", "Provider::CoreStatic"),
                "shared": ("Provider::Headers", "Provider::CoreShared"),
            },
        )

    def _accepted(self) -> list[provider_import.AcceptedPackage]:
        return provider_import.accept_matrix(
            [path for path, _ in self.packages],
            [root for _, root in self.packages],
            self.policy,
            self.source,
            "refs/heads/main",
        )

    def _policy_value(self) -> dict[str, Any]:
        return {
            "schema": provider_import.POLICY_SCHEMA,
            "provider_id": self.policy.provider_id,
            "manifest_provider_id": self.policy.manifest_provider_id,
            "manifest_schema": self.policy.manifest_schema,
            "repository": self.policy.repository,
            "source_ref": self.policy.source_ref,
            "package_version": self.policy.package_version,
            "abi": {
                "major": self.policy.abi_major,
                "minor": self.policy.abi_minor,
                "manifest_sha256": self.policy.abi_manifest_sha256,
            },
            "state_formats": self.policy.state_formats,
            "inventory": {
                "artifacts_sha256": self.policy.artifacts_sha256,
                "contracts_sha256": self.policy.contracts_sha256,
                "contract_set": provider_import._inventory_objects(
                    self.policy.contract_set
                ),
                "contract_set_sha256": self.policy.contract_set_sha256,
                "public_headers_sha256": self.policy.public_headers_sha256,
            },
            "configuration": self.policy.configuration,
            "architecture": self.policy.architecture,
            "licence": self.policy.licence,
            "required_targets": {
                key: list(value) for key, value in self.policy.required_targets.items()
            },
        }

    def test_projects_every_identity_surface_reproducibly(self) -> None:
        packages = self._accepted()
        current = provider_import.load_release_inputs(self.index)
        first = provider_import.project_release_inputs(
            current,
            packages,
            self.policy,
            self.commit,
        )
        second = provider_import.project_release_inputs(
            copy.deepcopy(current),
            packages,
            self.policy,
            self.commit,
        )
        first_bytes = provider_import.render_release_inputs(first)
        self.assertEqual(first_bytes, provider_import.render_release_inputs(second))
        workspace = provider_import._row(
            first["workspace_lock.v1.toml"]["component"],
            "universal_launcher",
            "workspace",
        )
        dependency = provider_import._row(
            first["dependency_lock.v1.toml"]["component"],
            "universal_launcher",
            "dependency",
        )
        provider = provider_import._row(
            first["providers.lock.v2.toml"]["provider"],
            "universal_launcher",
            "provider",
        )
        build = provider_import._row(
            first["build_manifest.v1.toml"]["component"],
            "universal_launcher",
            "build",
        )
        sbom = provider_import._row(
            first["sbom.components.v1.json"]["components"],
            "universal_launcher",
            "SBOM",
        )
        self.assertEqual(workspace["pin"], self.commit)
        self.assertEqual(workspace["tree"], self.tree)
        self.assertEqual(dependency["version"], "1.9.1")
        self.assertEqual(build["version"], "1.9.1")
        self.assertEqual(sbom["version"], "1.9.1")
        self.assertEqual(provider["cmake_package_version"], "1.9.1")
        self.assertEqual(provider["abi_version"], "1.9")
        rows = [
            row
            for row in first["providers.lock.v2.toml"]["sdk_package"]
            if row["provider_id"] == "universal_launcher"
        ]
        self.assertEqual(
            {(row["system"], row["linkage"]) for row in rows},
            provider_import.EXPECTED_PROFILES,
        )
        self.assertTrue(all(row["source_revision"] == self.commit for row in rows))
        self.assertTrue(all(row["package_version"] == "1.9.1" for row in rows))
        untouched = [
            row
            for row in first["providers.lock.v2.toml"]["sdk_package"]
            if row["provider_id"] != "universal_launcher"
        ]
        original_untouched = [
            row
            for row in current["providers.lock.v2.toml"]["sdk_package"]
            if row["provider_id"] != "universal_launcher"
        ]
        self.assertEqual(untouched, original_untouched)
        self.assertEqual(
            first["providers.lock.v2.toml"]["sdk_qualification_evidence_revision"],
            current["providers.lock.v2.toml"]["sdk_qualification_evidence_revision"],
        )

        provider_import.verify_or_apply(self.index, first_bytes, apply=True)
        applied = provider_import.load_release_inputs(self.index)
        repeated = provider_import.project_release_inputs(
            applied,
            packages,
            self.policy,
            self.commit,
        )
        repeated_bytes = provider_import.render_release_inputs(repeated)
        self.assertEqual(first_bytes, repeated_bytes)
        provider_import.verify_or_apply(self.index, repeated_bytes, apply=False)

        policy_value = self._policy_value()
        policy_schema = json.loads(
            (
                ROOT
                / "contracts/schema/release/provider_package_import_policy.v1.schema.json"
            ).read_text(encoding="utf-8")
        )
        jsonschema.Draft202012Validator(policy_schema).validate(policy_value)
        policy_path = self.root / "policy.json"
        policy_path.write_text(json.dumps(policy_value), encoding="utf-8")
        self.assertEqual(provider_import.ImportPolicy.load(policy_path), self.policy)

        summary = provider_import._summary(
            packages,
            dataclasses.replace(
                self.policy,
                state_formats={
                    "state_format": {
                        "read_versions": [99],
                        "write_version": 99,
                    }
                },
            ),
            self.commit,
            repeated_bytes,
        )
        self.assertEqual(
            summary["state_formats"],
            {
                "state_format": {
                    "read_versions": [1, 2],
                    "write_version": 2,
                }
            },
        )
        evidence_schema = json.loads(
            (
                ROOT / "contracts/schema/release/provider_package_import.v1.schema.json"
            ).read_text(encoding="utf-8")
        )
        jsonschema.Draft202012Validator(evidence_schema).validate(summary)

    def test_refuses_stale_manual_release_surface(self) -> None:
        current = provider_import.load_release_inputs(self.index)
        build = provider_import._row(
            current["build_manifest.v1.toml"]["component"],
            "universal_launcher",
            "build",
        )
        build["version"] = "9.9.9"
        with self.assertRaisesRegex(provider_import.ImportFailure, "manually stale"):
            provider_import.project_release_inputs(
                current,
                self._accepted(),
                self.policy,
                self.commit,
            )

    def test_accepts_multiple_named_provider_state_formats(self) -> None:
        expected = {
            "installed_state": {"read_versions": [1], "write_version": 1},
            "transaction_journal": {
                "read_versions": [1],
                "write_version": 1,
            },
        }
        for manifest, _ in self.packages:
            value = json.loads(manifest.read_text(encoding="utf-8"))
            value["provider"].pop("state_format")
            value["provider"]["state_formats"] = expected
            manifest.write_bytes(provider_import.canonical_json_bytes(value))
        policy = dataclasses.replace(self.policy, state_formats=expected)
        accepted = provider_import.accept_matrix(
            [path for path, _ in self.packages],
            [root for _, root in self.packages],
            policy,
            self.source,
            "refs/heads/main",
        )
        self.assertTrue(all(package.state_formats == expected for package in accepted))

    def test_native_schema_rejects_future_and_duplicate_members(self) -> None:
        manifest, root = self.packages[0]
        original = manifest.read_bytes()
        value = json.loads(original)
        value["future_member"] = True
        manifest.write_bytes(provider_import.canonical_json_bytes(value))
        with self.assertRaisesRegex(
            provider_import.ImportFailure, "provider-native schema rejected"
        ):
            provider_import.accept_package(
                manifest, root, self.policy, self.source, "refs/heads/main"
            )
        text = original.decode("utf-8")
        manifest.write_text(
            text.replace(
                '"schema":',
                '"schema":"fixture.provider_package_manifest.v1","schema":',
                1,
            ),
            encoding="utf-8",
        )
        with self.assertRaisesRegex(provider_import.ImportFailure, "duplicate JSON member"):
            provider_import.accept_package(
                manifest, root, self.policy, self.source, "refs/heads/main"
            )
        manifest.write_bytes(original)

    def test_refuses_unbound_selected_contract_set(self) -> None:
        fake = (("share/provider/contracts/not-installed.json", 1, "b" * 64),)
        policy = dataclasses.replace(self.policy, contract_set=fake)
        manifest, root = self.packages[0]
        with self.assertRaisesRegex(
            provider_import.ImportFailure, "selected contract set differs"
        ):
            provider_import.accept_package(
                manifest, root, policy, self.source, "refs/heads/main"
            )

    def test_refuses_changed_or_missing_artifact(self) -> None:
        manifest, root = self.packages[0]
        artifact = (
            root
            / "lib"
            / f"linux-{json.loads(manifest.read_text())['package']['linkage']}.bin"
        )
        artifact.write_text("changed\n", encoding="utf-8")
        with self.assertRaisesRegex(
            provider_import.ImportFailure, "(size|bytes) changed"
        ):
            provider_import.accept_package(
                manifest,
                root,
                self.policy,
                self.source,
                "refs/heads/main",
            )

    def test_refuses_wrong_source_ref_commit_tree_and_version(self) -> None:
        manifest, root = self.packages[0]
        original = json.loads(manifest.read_text(encoding="utf-8"))
        cases = (
            (("source", "ref"), "refs/heads/task/not-main", "source ref"),
            (("source", "commit"), "b" * 40, "protected-main tip"),
            (("source", "tree"), "b" * 40, "tree differs"),
            (("provider", "package_version"), "1.9.0", "version differs"),
        )
        for path, value, message in cases:
            with self.subTest(path=path):
                changed = copy.deepcopy(original)
                changed[path[0]][path[1]] = value
                manifest.write_bytes(provider_import.canonical_json_bytes(changed))
                with self.assertRaisesRegex(provider_import.ImportFailure, message):
                    provider_import.accept_package(
                        manifest,
                        root,
                        self.policy,
                        self.source,
                        "refs/heads/main",
                    )
        manifest.write_bytes(provider_import.canonical_json_bytes(original))
        with self.assertRaisesRegex(provider_import.ImportFailure, "policy-owned"):
            provider_import.accept_package(
                manifest,
                root,
                self.policy,
                self.source,
                "refs/heads/task/not-main",
            )

    def test_policy_must_be_owned_by_exact_facman_context(self) -> None:
        facman = self.root / "facman"
        facman.mkdir()
        subprocess.run(
            ["git", "init", "--initial-branch=main"],
            cwd=facman,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        subprocess.run(
            ["git", "config", "user.email", "facman-fixture@example.invalid"],
            cwd=facman,
            check=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "FacMan Fixture"],
            cwd=facman,
            check=True,
        )
        policy = (
            facman
            / "release"
            / "policies"
            / "provider-package-import"
            / "universal_launcher.v1.json"
        )
        policy.parent.mkdir(parents=True)
        policy.write_text('{"reviewed":true}\n', encoding="utf-8")
        subprocess.run(["git", "add", "--", policy.relative_to(facman)], cwd=facman, check=True)
        subprocess.run(["git", "commit", "-m", "fixture policy"], cwd=facman, check=True)
        revision = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=facman,
            check=True,
            text=True,
            stdout=subprocess.PIPE,
        ).stdout.strip()
        provider_import.verify_policy_custody(policy, revision, facman)
        if os.name == "nt":
            buffer = ctypes.create_unicode_buffer(32768)
            length = ctypes.windll.kernel32.GetShortPathNameW(
                str(policy), buffer, len(buffer)
            )
            if length and length < len(buffer) and buffer.value != str(policy):
                provider_import.verify_policy_custody(
                    Path(buffer.value), revision, facman.resolve()
                )
        policy.write_text('{"reviewed":false}\n', encoding="utf-8")
        with self.assertRaisesRegex(provider_import.ImportFailure, "not owned"):
            provider_import.verify_policy_custody(policy, revision, facman)
        outside = facman / "unreviewed.json"
        outside.write_text('{"reviewed":true}\n', encoding="utf-8")
        with self.assertRaisesRegex(provider_import.ImportFailure, "policy root"):
            provider_import.verify_policy_custody(outside, revision, facman)

    def test_multi_file_apply_rolls_back_and_supports_crash_recovery(self) -> None:
        current = provider_import.load_release_inputs(self.index)
        projected = provider_import.project_release_inputs(
            current,
            self._accepted(),
            self.policy,
            self.commit,
        )
        rendered = provider_import.render_release_inputs(projected)
        original = {
            filename: (self.index / filename).read_bytes()
            for filename in provider_import.INDEX_FILENAMES
        }
        changed_target = self.index / provider_import.INDEX_FILENAMES[0]
        changed_target.write_bytes(original[provider_import.INDEX_FILENAMES[0]] + b"# changed\n")
        with self.assertRaisesRegex(provider_import.ImportFailure, "changed after projection"):
            provider_import.verify_or_apply(
                self.index,
                rendered,
                apply=True,
                expected_original=original,
            )
        changed_target.write_bytes(original[provider_import.INDEX_FILENAMES[0]])
        self.assertFalse((self.index / provider_import.TRANSACTION_DIRECTORY).exists())
        calls = 0

        def failed_replace(source: Path, target: Path) -> None:
            nonlocal calls
            calls += 1
            if calls == 3:
                raise OSError("fixture replacement failure")
            source.replace(target)

        with self.assertRaisesRegex(provider_import.ImportFailure, "rolled back"):
            provider_import.verify_or_apply(
                self.index,
                rendered,
                apply=True,
                replace_target=failed_replace,
            )
        self.assertEqual(
            original,
            {
                filename: (self.index / filename).read_bytes()
                for filename in provider_import.INDEX_FILENAMES
            },
        )
        self.assertFalse((self.index / provider_import.TRANSACTION_DIRECTORY).exists())

        calls = 0

        def interrupted_replace(source: Path, target: Path) -> None:
            nonlocal calls
            calls += 1
            if calls == 3:
                raise KeyboardInterrupt("fixture abrupt interruption")
            source.replace(target)

        with self.assertRaises(KeyboardInterrupt):
            provider_import.verify_or_apply(
                self.index,
                rendered,
                apply=True,
                replace_target=interrupted_replace,
            )
        self.assertTrue((self.index / provider_import.TRANSACTION_DIRECTORY).is_dir())
        journal_path = (
            self.index
            / provider_import.TRANSACTION_DIRECTORY
            / "journal.v1.json"
        )
        journal = json.loads(journal_path.read_text(encoding="utf-8"))
        transaction_schema = json.loads(
            (
                ROOT
                / "contracts/schema/release/provider_package_import_transaction.v1.schema.json"
            ).read_text(encoding="utf-8")
        )
        jsonschema.Draft202012Validator(transaction_schema).validate(journal)
        mutated_journal = dict(journal)
        mutated_journal["future_field"] = True
        journal_path.write_bytes(provider_import.canonical_json_bytes(mutated_journal))
        with self.assertRaisesRegex(provider_import.ImportFailure, "shape is invalid"):
            provider_import.recover_release_transaction(self.index)
        journal_path.write_bytes(provider_import.canonical_json_bytes(journal))
        with self.assertRaisesRegex(provider_import.ImportFailure, "recovery is required"):
            provider_import.verify_or_apply(self.index, rendered, apply=False)
        provider_import.recover_release_transaction(self.index)
        self.assertEqual(
            original,
            {
                filename: (self.index / filename).read_bytes()
                for filename in provider_import.INDEX_FILENAMES
            },
        )
        self.assertFalse((self.index / provider_import.TRANSACTION_DIRECTORY).exists())

    def test_refuses_wrong_abi_state_contract_header_and_profile(self) -> None:
        manifest, root = self.packages[0]
        original = json.loads(manifest.read_text(encoding="utf-8"))
        mutations = (
            (lambda value: value["provider"]["c_abi"].update(minor=8), "ABI identity"),
            (
                lambda value: value["provider"]["state_format"].update(write_version=1),
                "state writer",
            ),
            (
                lambda value: value["inventories"].update(contracts_sha256="b" * 64),
                "contracts inventory digest",
            ),
            (
                lambda value: value["inventories"].update(
                    public_headers_sha256="b" * 64
                ),
                "public_headers inventory digest",
            ),
            (
                lambda value: value["package"].update(configuration="Debug"),
                "configuration",
            ),
            (lambda value: value["package"].update(architecture="x86"), "architecture"),
            (
                lambda value: value["package"].update(linkage="combined"),
                "static or shared",
            ),
        )
        for mutate, message in mutations:
            with self.subTest(message=message):
                changed = copy.deepcopy(original)
                mutate(changed)
                manifest.write_bytes(provider_import.canonical_json_bytes(changed))
                with self.assertRaisesRegex(provider_import.ImportFailure, message):
                    provider_import.accept_package(
                        manifest,
                        root,
                        self.policy,
                        self.source,
                        "refs/heads/main",
                    )
        manifest.write_bytes(provider_import.canonical_json_bytes(original))

    def test_refuses_incomplete_or_mixed_matrix(self) -> None:
        with self.assertRaisesRegex(provider_import.ImportFailure, "three systems"):
            provider_import.accept_matrix(
                [path for path, _ in self.packages[:-1]],
                [root for _, root in self.packages[:-1]],
                self.policy,
                self.source,
                "refs/heads/main",
            )
        manifest, _ = self.packages[-1]
        value = json.loads(manifest.read_text(encoding="utf-8"))
        value["provider"]["maturity"] = "different"
        manifest.write_bytes(provider_import.canonical_json_bytes(value))
        with self.assertRaisesRegex(provider_import.ImportFailure, "mixes provider"):
            self._accepted()


if __name__ == "__main__":
    unittest.main()
