# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import tomllib
import unittest
from dataclasses import replace
from pathlib import Path

from tools import provider_conformance as conformance


class ProviderConformanceTests(unittest.TestCase):
    @staticmethod
    def _git(root: Path, *arguments: str) -> str:
        return subprocess.run(
            ["git", "-C", str(root), *arguments],
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        ).stdout.strip()

    def _provider_git_fixture(
        self, root: Path
    ) -> tuple[Path, conformance.ProviderSpec, str, str]:
        source = root / "provider"
        source.mkdir()
        self._git(source, "init")
        self._git(source, "config", "user.name", "FacMan Test")
        self._git(source, "config", "user.email", "facman-test@example.invalid")
        self._git(source, "remote", "add", "origin", conformance.PROVIDERS[0].remote)
        payload = source / "provider.txt"
        payload.write_text("tracked\n", encoding="utf-8")
        self._git(source, "add", "provider.txt")
        self._git(source, "commit", "-m", "tracked provider")
        tracked = self._git(source, "rev-parse", "HEAD")
        payload.write_text("promoted\n", encoding="utf-8")
        self._git(source, "commit", "-am", "promoted provider")
        promoted = self._git(source, "rev-parse", "HEAD")
        self._git(source, "update-ref", "refs/remotes/origin/main", promoted)
        self._git(source, "checkout", "--detach", tracked)
        spec = replace(conformance.PROVIDERS[0], canonical_commit=tracked)
        return source, spec, tracked, promoted

    @staticmethod
    def _toolchain() -> dict[str, object]:
        return {
            "cmake": "cmake version 4.1.0",
            "generator": "Ninja",
            "generator_platform": "none",
            "generator_toolset": "none",
            "system": "FixtureOS",
            "processor": "x86_64",
            "pointer_bits": 64,
            "configuration": "Release",
            "c_compiler_id": "FixtureC",
            "c_compiler_version": "1.2.3",
            "c_compiler_target": "none",
            "cxx_compiler_id": "FixtureCXX",
            "cxx_compiler_version": "4.5.6",
            "cxx_compiler_target": "none",
            "sysroot": "none",
            "msvc_runtime_library": "none",
        }

    @staticmethod
    def _tracked_consumed() -> dict[str, dict[str, str]]:
        return {
            "universal_launcher": {"pin": "1cafe4054297cc11e02458b83d230db0cd064471"},
            "universal_setup": {"pin": "32488fc13bd2439f9f6e52e83a97f6da345a7650"},
        }

    def _provider_fixture(
        self,
        root: Path,
        spec: conformance.ProviderSpec,
    ) -> tuple[conformance.ProviderSource, Path]:
        source = root / "source"
        prefix = root / "prefix"
        (source / "release" / "index").mkdir(parents=True)
        (source / "contracts" / "abi").mkdir(parents=True)
        (source / "contracts" / "schema" / "nested").mkdir(parents=True)
        package = "\n".join(
            [
                f'package_version = "{spec.package_version}"',
                "exported_targets = [",
                *(f'  "{target}",' for target in spec.exported_targets),
                "]",
                "",
            ]
        )
        (source / "release" / "index" / "sdk_package_workunit.v1.toml").write_text(
            package, encoding="utf-8"
        )
        abi_name = Path(spec.abi_relative_path).name
        abi = (
            "abi_major = 1\nabi_minor = 8\n"
            if spec.provider_id == "universal_launcher"
            else "abi_major = 1\nabi_minor = 0\n"
        )
        (source / "contracts" / "abi" / abi_name).write_text(abi, encoding="utf-8")
        contract = '{"schema":"fixture.v1"}\n'
        (source / "contracts" / "schema" / "nested" / "fixture.json").write_text(
            contract, encoding="utf-8"
        )
        (source / "contracts" / "schema" / "nested" / "README.md").write_text(
            "Source-only contract documentation.\n", encoding="utf-8"
        )
        installed_contract = (
            prefix
            / "share"
            / spec.installed_data_name
            / "contracts"
            / "schema"
            / "nested"
        )
        installed_contract.mkdir(parents=True)
        (installed_contract / "fixture.json").write_text(contract, encoding="utf-8")
        installed_abi = (
            prefix / "share" / spec.installed_data_name / "contracts" / "abi" / abi_name
        )
        installed_abi.parent.mkdir(parents=True)
        installed_abi.write_text(abi, encoding="utf-8")
        (prefix / "include").mkdir()
        (prefix / "include" / "provider.h").write_text(
            "/* public */\n", encoding="utf-8"
        )
        package_config = prefix / "lib" / "cmake" / spec.package_name
        package_config.mkdir(parents=True)
        (package_config / f"{spec.package_name}Config.cmake").write_text(
            "# relocatable fixture\n", encoding="utf-8"
        )
        (package_config / f"{spec.package_name}Targets.cmake").write_text(
            "# exact target inventory fixture\n", encoding="utf-8"
        )
        (prefix / "lib" / "provider.bin").write_bytes(b"provider-binary-fixture\n")
        provider = conformance.ProviderSource(
            spec=spec,
            root=source,
            commit=spec.canonical_commit,
            tree="a" * 40,
        )
        return provider, prefix

    def _runtime_fixture(
        self, root: Path
    ) -> tuple[dict[str, Path], dict[str, dict[str, object]], set[Path]]:
        prefixes: dict[str, Path] = {}
        identities: dict[str, dict[str, object]] = {}
        runtimes: set[Path] = set()
        for spec in conformance.PROVIDERS:
            prefix = root / "sdk" / spec.provider_id
            metadata_dir = prefix / "lib" / "cmake" / spec.package_name
            runtime = prefix / "bin" / f"{spec.source_name}.dll"
            metadata_dir.mkdir(parents=True)
            runtime.parent.mkdir(parents=True)
            runtime.write_bytes(b"declared-runtime\n")
            config = metadata_dir / f"{spec.package_name}Config.cmake"
            config.write_text("# fixture\n", encoding="utf-8")
            (metadata_dir / f"{spec.package_name}Targets-release.cmake").write_text(
                "set_target_properties("
                f"{spec.package_name}::CoreShared PROPERTIES\n"
                "  IMPORTED_LOCATION_RELEASE "
                f'"${{_IMPORT_PREFIX}}/bin/{runtime.name}"\n'
                ")\n",
                encoding="utf-8",
            )
            prefixes[spec.provider_id] = prefix
            identities[spec.provider_id] = {
                "package": {
                    "metadata_relative_path": config.relative_to(prefix).as_posix(),
                    "exported_targets": list(spec.exported_targets),
                },
                "toolchain": {"configuration": "Release"},
            }
            runtimes.add(runtime.resolve())
        return prefixes, identities, runtimes

    def test_inventory_identity_is_relocation_stable(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = root / "one"
            second = root / "unrelated" / "two"
            first.mkdir()
            second.mkdir(parents=True)
            (first / "value.txt").write_text("same\n", encoding="utf-8")
            (second / "value.txt").write_text("same\n", encoding="utf-8")

            self.assertEqual(
                conformance.inventory_identity(first),
                conformance.inventory_identity(second),
            )

    def test_identity_is_path_independent_and_binds_canonical_source(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            source, prefix = self._provider_fixture(
                Path(temporary), conformance.PROVIDERS[0]
            )
            conformance.create_sdk_inventory_manifest(
                prefix, source.spec, "installed_static"
            )
            identity = conformance.build_provider_identity(
                source,
                prefix,
                "installed_static",
                self._toolchain(),
            )

            conformance.assert_path_independent_json(identity)
            self.assertEqual(conformance.IDENTITY_SCHEMA, identity["schema"])
            self.assertEqual(".", identity["install"]["root"])
            self.assertEqual(source.commit, identity["source"]["commit"])
            self.assertEqual(source.tree, identity["source"]["tree"])
            self.assertEqual(source.spec.repository, identity["repository"])
            self.assertEqual(source.spec.remote, identity["source"]["remote"])
            self.assertEqual("refs/heads/main", identity["canonical_main_ref"])
            self.assertEqual("installed_static", identity["consumption"]["mode"])
            self.assertEqual("static", identity["consumption"]["linkage"])
            self.assertTrue(
                all(value is False for value in identity["authority"].values())
            )
            serialized = json.dumps(identity)
            self.assertNotIn(str(source.root), serialized)
            self.assertNotIn(str(prefix), serialized)

    def test_exact_provider_input_may_precede_current_main(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source, spec, tracked, promoted = self._provider_git_fixture(root)
            runner = conformance.CommandRunner(root / "evidence")

            observed = conformance.observe_provider(spec, source, runner)

            self.assertEqual(observed.commit, tracked)
            self.assertNotEqual(observed.commit, promoted)
            self.assertEqual(
                self._git(source, "rev-parse", "refs/remotes/origin/main"), promoted
            )

    def test_exact_provider_input_must_remain_reachable_from_main(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source, spec, tracked, _ = self._provider_git_fixture(root)
            self._git(source, "checkout", "--orphan", "unrelated")
            (source / "provider.txt").write_text("unrelated\n", encoding="utf-8")
            self._git(source, "add", "provider.txt")
            self._git(source, "commit", "-m", "unrelated provider")
            unrelated = self._git(source, "rev-parse", "HEAD")
            self._git(source, "update-ref", "refs/remotes/origin/main", unrelated)
            self._git(source, "checkout", "--detach", tracked)
            runner = conformance.CommandRunner(root / "evidence")

            with self.assertRaisesRegex(ValueError, "not reachable from origin/main"):
                conformance.observe_provider(spec, source, runner)

    def test_sdk_inventory_binds_every_installed_artifact_and_exact_sidecars(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            source, prefix = self._provider_fixture(
                Path(temporary), conformance.PROVIDERS[0]
            )
            manifest_path, manifest = conformance.create_sdk_inventory_manifest(
                prefix, source.spec, "installed_static"
            )
            identity = conformance.build_provider_identity(
                source,
                prefix,
                "installed_static",
                self._toolchain(),
            )
            identity_path = prefix / conformance._identity_relative_path(
                source.spec, "installed_static"
            )
            conformance.write_identity(identity_path, identity)

            self.assertEqual(conformance.INVENTORY_SCHEMA, manifest["schema"])
            self.assertEqual(
                sorted(
                    [
                        manifest_path.relative_to(prefix).as_posix(),
                        identity_path.relative_to(prefix).as_posix(),
                    ]
                ),
                manifest["excludes"],
            )
            self.assertEqual(
                conformance.sha256_bytes(
                    conformance.canonical_json_bytes(manifest["files"])
                ),
                manifest["files_sha256"],
            )
            self.assertEqual(
                manifest["files_sha256"], identity["install"]["inventory_sha256"]
            )
            self.assertTrue(
                all(
                    set(record) == {"path", "bytes", "sha256"}
                    for record in manifest["files"]
                )
            )

            mutation_paths = [
                prefix / "lib" / "provider.bin",
                prefix
                / "lib"
                / "cmake"
                / source.spec.package_name
                / f"{source.spec.package_name}Targets.cmake",
                prefix
                / "lib"
                / "cmake"
                / source.spec.package_name
                / f"{source.spec.package_name}Config.cmake",
                next(
                    (
                        prefix
                        / "share"
                        / source.spec.installed_data_name
                        / "contracts"
                        / "schema"
                    ).rglob("*.json")
                ),
            ]
            for path in mutation_paths:
                with self.subTest(path=path.name):
                    original = path.read_bytes()
                    path.write_bytes(original + b"substitution")
                    with self.assertRaisesRegex(
                        ValueError, "live install inventory differs"
                    ):
                        conformance.validate_sdk_inventory_manifest(prefix, identity)
                    path.write_bytes(original)
                    conformance.validate_sdk_inventory_manifest(prefix, identity)

    def test_stale_relocation_metadata_is_refused_by_inventory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source, prefix = self._provider_fixture(
                root / "original", conformance.PROVIDERS[0]
            )
            conformance.create_sdk_inventory_manifest(
                prefix, source.spec, "installed_static"
            )
            identity = conformance.build_provider_identity(
                source, prefix, "installed_static", self._toolchain()
            )
            identity_path = prefix / conformance._identity_relative_path(
                source.spec, "installed_static"
            )
            conformance.write_identity(identity_path, identity)
            relocated = root / "relocated" / "sdk"
            shutil.copytree(prefix, relocated)
            metadata = relocated / identity["package"]["metadata_relative_path"]
            metadata.write_text(
                metadata.read_text(encoding="utf-8")
                + f'\nset(STALE_ORIGINAL_PREFIX "{prefix.as_posix()}")\n',
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "live install inventory differs"):
                conformance.validate_sdk_inventory_manifest(relocated, identity)

    def test_authority_requires_exact_false_key_set(self) -> None:
        conformance.validate_authority(dict(conformance.AUTHORITY))
        missing = dict(conformance.AUTHORITY)
        del missing["publication"]
        unknown = dict(conformance.AUTHORITY, unknown_authority=False)
        escalated = dict(conformance.AUTHORITY, product_execution=True)
        for value in (missing, unknown, escalated):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, "authority"):
                    conformance.validate_authority(value)

    def test_toolchain_is_derived_from_exact_provider_build_caches(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)

            def build_fixture(name: str, include_cxx: bool) -> Path:
                build = root / name
                generated = build / "CMakeFiles" / "4.1.0"
                generated.mkdir(parents=True)
                (build / "CMakeCache.txt").write_text(
                    "CMAKE_BUILD_TYPE:STRING=Release\nCMAKE_GENERATOR:INTERNAL=Ninja\n",
                    encoding="utf-8",
                )
                (generated / "CMakeSystem.cmake").write_text(
                    'set(CMAKE_SYSTEM_NAME "FixtureOS")\n'
                    'set(CMAKE_SYSTEM_PROCESSOR "fixture64")\n',
                    encoding="utf-8",
                )
                (generated / "CMakeCCompiler.cmake").write_text(
                    'set(CMAKE_C_SIZEOF_DATA_PTR "8")\n'
                    'set(CMAKE_C_COMPILER_ID "FixtureC")\n'
                    'set(CMAKE_C_COMPILER_VERSION "1.2.3")\n',
                    encoding="utf-8",
                )
                if include_cxx:
                    (generated / "CMakeCXXCompiler.cmake").write_text(
                        'set(CMAKE_CXX_COMPILER_ID "FixtureCXX")\n'
                        'set(CMAKE_CXX_COMPILER_VERSION "4.5.6")\n',
                        encoding="utf-8",
                    )
                return build

            class Runner:
                @staticmethod
                def run(*_args: object, **_kwargs: object) -> object:
                    return type("Result", (), {"output": "cmake version 4.1.0\n"})()

            toolchain = conformance.cmake_toolchain(
                "cmake",
                "Release",
                {
                    "universal_launcher": build_fixture("ulk", False),
                    "universal_setup": build_fixture("usk", True),
                },
                Runner(),  # type: ignore[arg-type]
            )

            self.assertEqual(conformance.TOOLCHAIN_KEYS, set(toolchain))
            self.assertEqual(64, toolchain["pointer_bits"])
            self.assertIs(type(toolchain["pointer_bits"]), int)
            self.assertEqual("FixtureCXX", toolchain["cxx_compiler_id"])
            for field in (
                "generator_platform",
                "generator_toolset",
                "c_compiler_target",
                "cxx_compiler_target",
                "sysroot",
                "msvc_runtime_library",
            ):
                self.assertEqual("none", toolchain[field])
            conformance.validate_toolchain(toolchain)
            missing = dict(toolchain)
            missing.pop("generator_toolset")
            unknown = dict(toolchain, unknown_toolchain_field="none")
            wrong_pointer_type = dict(toolchain, pointer_bits="64")
            for invalid in (missing, unknown, wrong_pointer_type):
                with self.subTest(invalid=invalid):
                    with self.assertRaisesRegex(ValueError, "toolchain"):
                        conformance.validate_toolchain(invalid)

    def test_private_runtime_uses_declared_shared_targets_and_refuses_extras(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            prefixes, identities, expected = self._runtime_fixture(root)
            declared = conformance._declared_shared_runtime_files(prefixes, identities)

            self.assertEqual(expected, set(declared))
            self.assertEqual(len(expected), len(declared))
            self.assertEqual(
                "refused",
                conformance.run_undeclared_runtime_dependency_control(
                    prefixes, identities, root / "work"
                ),
            )

    def test_private_runtime_preserves_distinct_symlink_aliases(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            prefixes, identities, runtimes = self._runtime_fixture(root)
            aliases: set[Path] = set()
            for runtime in runtimes:
                alias = runtime.with_name(f"zz-{runtime.name}")
                try:
                    alias.symlink_to(runtime.name)
                except (NotImplementedError, OSError) as error:
                    self.skipTest(f"unsupported: runtime symlink unavailable: {error}")
                aliases.add(alias.absolute())

            declared = conformance._declared_shared_runtime_files(prefixes, identities)
            expected = runtimes | aliases
            self.assertEqual(len(expected), len(declared))
            self.assertEqual(
                {path.name for path in expected},
                {path.name for path in declared},
            )
            for expected_path in expected:
                matching = [
                    path for path in declared if path.name == expected_path.name
                ]
                self.assertEqual(1, len(matching))
                self.assertTrue(expected_path.samefile(matching[0]))

            private_runtime, original_runtime = conformance._copy_private_runtime(
                prefixes, identities, root / "work"
            )
            self.assertEqual(
                {path.name for path in expected},
                {path.name for path in private_runtime.iterdir()},
            )
            with conformance._hidden_runtime_files(original_runtime):
                self.assertTrue(
                    all(not path.exists() and not path.is_symlink() for path in expected)
                )
            self.assertTrue(all(path.exists() for path in runtimes))
            self.assertTrue(all(path.is_symlink() for path in aliases))

    def test_richer_semantic_equivalence_remains_explicitly_pending(self) -> None:
        self.assertEqual(
            {
                "operation_outcome_equivalence",
                "structured_refusal_equivalence",
                "interrupted_recovery_projection_equivalence",
                "release_resolution_root_equivalence",
            },
            set(conformance.PENDING_SEMANTIC_EQUIVALENCE),
        )
        self.assertEqual(
            {"pending_not_fabricated"},
            set(conformance.PENDING_SEMANTIC_EQUIVALENCE.values()),
        )

    def test_result_classification_is_bounded_even_for_canonical_inputs(self) -> None:
        hosted = conformance._bounded_success_classification(False)
        rehearsal = conformance._bounded_success_classification(True)

        self.assertEqual("bounded_provider_input_conformance_pass", hosted["result"])
        self.assertEqual(
            "bounded_provider_input_development_rehearsal", rehearsal["result"]
        )
        for classification in (hosted, rehearsal):
            self.assertTrue(classification["canonical_inputs"])
            self.assertFalse(classification["full_semantic_conformance"])

        markdown = conformance._markdown(
            {
                **hosted,
                "candidate_differs_from_tracked": False,
                "modes": {},
                "negative_controls": {},
            }
        )
        self.assertIn("# Bounded canonical provider-input", markdown)
        self.assertIn("Canonical provider inputs: `true`", markdown)
        self.assertIn("Full semantic conformance: `false`", markdown)
        self.assertIn("Candidate differs from tracked pins: `false`", markdown)

    def test_identity_refuses_contract_bundle_substitution(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            source, prefix = self._provider_fixture(
                Path(temporary), conformance.PROVIDERS[1]
            )
            installed_contract = next(
                (
                    prefix
                    / "share"
                    / source.spec.installed_data_name
                    / "contracts"
                    / "schema"
                ).rglob("*.json")
            )
            installed_contract.write_text(
                '{"schema":"substituted.v1"}\n', encoding="utf-8"
            )

            with self.assertRaisesRegex(ValueError, "contract bundle differs"):
                conformance.create_sdk_inventory_manifest(
                    prefix, source.spec, "installed_shared"
                )
                conformance.build_provider_identity(
                    source,
                    prefix,
                    "installed_shared",
                    self._toolchain(),
                )

    def test_identity_refuses_non_schema_file_in_installed_contract_bundle(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            source, prefix = self._provider_fixture(
                Path(temporary), conformance.PROVIDERS[1]
            )
            installed_contracts = (
                prefix
                / "share"
                / source.spec.installed_data_name
                / "contracts"
                / "schema"
            )
            (installed_contracts / "README.md").write_text(
                "Unexpected installed documentation.\n", encoding="utf-8"
            )

            with self.assertRaisesRegex(ValueError, "contains non-schema files"):
                conformance.create_sdk_inventory_manifest(
                    prefix, source.spec, "installed_shared"
                )
                conformance.build_provider_identity(
                    source,
                    prefix,
                    "installed_shared",
                    self._toolchain(),
                )

    def test_candidate_lock_has_exact_two_components_and_no_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            sources = [
                self._provider_fixture(root / str(index), spec)[0]
                for index, spec in enumerate(conformance.PROVIDERS)
            ]
            text = conformance.candidate_lock_text(sources, self._tracked_consumed())
            parsed = tomllib.loads(text)

            self.assertEqual(conformance.LOCK_SCHEMA, parsed["schema"])
            self.assertTrue(parsed["conformance_only"])
            self.assertTrue(parsed["candidate_not_adopted"])
            self.assertFalse(parsed["release_eligible"])
            self.assertFalse(parsed["tracked_lock_mutated"])
            self.assertFalse(parsed["candidate_differs_from_tracked"])
            self.assertEqual(2, len(parsed["component"]))
            self.assertEqual(
                {spec.canonical_commit for spec in conformance.PROVIDERS},
                {item["pin"] for item in parsed["component"]},
            )
            self.assertTrue(all("path" not in item for item in parsed["component"]))
            self.assertTrue(
                all(value is False for value in parsed["authority"].values())
            )

    def test_candidate_lock_refuses_incomplete_provider_set(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            source, _ = self._provider_fixture(
                Path(temporary), conformance.PROVIDERS[0]
            )
            with self.assertRaisesRegex(ValueError, "exactly the two"):
                conformance.candidate_lock_text([source], self._tracked_consumed())

    def test_success_source_records_use_exact_https_remotes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            sources = {
                spec.provider_id: self._provider_fixture(root / spec.provider_id, spec)[
                    0
                ]
                for spec in conformance.PROVIDERS
            }
            records = conformance.canonical_provider_source_records(sources)

            for spec in conformance.PROVIDERS:
                self.assertEqual(spec.remote, records[spec.provider_id]["remote"])
                self.assertEqual(
                    spec.canonical_commit, records[spec.provider_id]["commit"]
                )
                self.assertEqual(
                    "refs/heads/main",
                    records[spec.provider_id]["canonical_main_ref"],
                )

    def test_truth_sets_record_tracked_authored_and_canonical_identities(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            sources = {
                spec.provider_id: self._provider_fixture(root / spec.provider_id, spec)[
                    0
                ]
                for spec in conformance.PROVIDERS
            }
            truth, digests = conformance.provider_truth_sets(conformance.ROOT, sources)

            self.assertEqual(
                {
                    "tracked_consumed",
                    "authored_release_provider",
                    "canonical_candidate",
                },
                set(truth),
            )
            self.assertEqual(
                "1cafe4054297cc11e02458b83d230db0cd064471",
                truth["tracked_consumed"]["universal_launcher"]["pin"],
            )
            self.assertEqual(
                "1cafe4054297cc11e02458b83d230db0cd064471",
                truth["authored_release_provider"]["universal_launcher"][
                    "source_revision"
                ],
            )
            self.assertEqual(
                conformance.PROVIDERS[0].canonical_commit,
                truth["canonical_candidate"]["universal_launcher"]["commit"],
            )
            self.assertEqual(
                {
                    provider_id: record["pin"]
                    for provider_id, record in truth["tracked_consumed"].items()
                },
                {
                    provider_id: record["commit"]
                    for provider_id, record in truth["canonical_candidate"].items()
                },
            )
            self.assertEqual(
                {"workspace_lock_sha256", "release_provider_lock_sha256"},
                set(digests),
            )

    def test_candidate_lock_truthfully_allows_candidate_equal_to_tracked_set(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            sources = [
                self._provider_fixture(root / str(index), spec)[0]
                for index, spec in enumerate(conformance.PROVIDERS)
            ]
            tracked = {
                source.spec.provider_id: {"pin": source.commit} for source in sources
            }
            parsed = tomllib.loads(conformance.candidate_lock_text(sources, tracked))
            self.assertFalse(parsed["candidate_differs_from_tracked"])
            self.assertTrue(parsed["conformance_only"])
            self.assertTrue(parsed["candidate_not_adopted"])
            self.assertFalse(parsed["release_eligible"])
            self.assertFalse(parsed["tracked_lock_mutated"])

    def test_negative_variants_cover_required_identity_refusals(self) -> None:
        base = {
            "provider_id": "universal_launcher",
            "source": {"commit": "a" * 40, "tree": "b" * 40},
            "package": {"version": "1.0", "metadata_sha256": "c" * 64},
            "abi": {"version": "1.0", "manifest_sha256": "d" * 64},
            "contracts": {"bundle_sha256": "e" * 64},
            "toolchain": self._toolchain(),
            "install": {"root": "."},
            "authority": dict(conformance.AUTHORITY),
        }
        usk = json.loads(json.dumps(base))
        usk["provider_id"] = "universal_setup"
        variants = conformance.negative_identity_variants(base, usk)
        names = {name for name, _, _ in variants}

        self.assertTrue(
            {
                "wrong_ulk_source_commit",
                "wrong_usk_source_commit",
                "wrong_package_version",
                "wrong_abi_version",
                "wrong_contract_bundle",
                "wrong_processor",
                "stale_relative_install_root",
                "injected_absolute_install_root",
                "authority_escalation",
                "missing_authority_key",
                "unknown_authority_key",
                "swapped_provider_identities",
            }.issubset(names)
        )
        self.assertEqual("a" * 40, base["source"]["commit"])
        self.assertTrue(all(value is False for value in base["authority"].values()))

    def test_semantic_normalization_changes_only_exact_mode_dependent_segments(
        self,
    ) -> None:
        ulk = "1" * 40
        usk = "2" * 40
        prefix = f"facman={'3' * 40};universal_launcher={ulk};universal_setup={usk};"

        def identity(mode: str, classification: str) -> str:
            return (
                prefix + f"provider_mode={mode};"
                "provider_lock_kind=conformance;"
                "provider_conformance_only=true;"
                "provider_sdk_consumption_candidate=false;"
                "provider_candidate_differs_from_tracked=true;"
                f"provider_consumption_classification={classification};"
                "provider_release_identity_coherent=false;"
                "source_dirty=true"
            )

        def product(build_identity: str) -> dict[str, object]:
            return {
                "schema": "factorio.product.v1",
                "backend_identity": {
                    "build": {"build_identity": build_identity},
                },
                "result": {"status": "valid", "code": "authority_not_granted"},
            }

        raw_identities = {
            "source": identity("source", "conformance_source"),
            "installed_static": identity(
                "installed_static", "conformance_rehearsal_installed_static"
            ),
            "installed_shared": identity(
                "installed_shared", "conformance_rehearsal_installed_shared"
            ),
        }
        raw_products = {
            mode: product(build_identity)
            for mode, build_identity in raw_identities.items()
        }
        raw_snapshot = json.loads(json.dumps(raw_products))
        normalized = {
            mode: conformance.normalize_semantic_value(payload, {})
            for mode, payload in raw_products.items()
        }
        self.assertEqual(1, len({json.dumps(value) for value in normalized.values()}))
        self.assertEqual(raw_snapshot, raw_products)
        first = raw_products["source"]

        for changed in (
            raw_identities["installed_static"].replace(ulk, "4" * 40),
            raw_identities["installed_static"].replace(
                "lock_kind=conformance", "lock_kind=tracked"
            ),
            raw_identities["installed_static"].replace(
                "conformance_only=true", "conformance_only=false"
            ),
            raw_identities["installed_static"].replace(
                "source_dirty=true", "source_dirty=false"
            ),
        ):
            with self.subTest(changed=changed):
                altered = product(changed)
                self.assertNotEqual(
                    conformance.normalize_semantic_value(first, {}),
                    conformance.normalize_semantic_value(altered, {}),
                )

        self.assertNotEqual(
            conformance.normalize_semantic_value({"provider_mode": "source"}, {}),
            conformance.normalize_semantic_value(
                {"provider_mode": "installed_static"}, {}
            ),
        )

    def test_build_identity_refuses_mismatched_mode_classification_pair(self) -> None:
        def identity(mode: str, classification: str) -> str:
            return (
                "facman="
                + "1" * 40
                + ";universal_launcher="
                + "2" * 40
                + ";universal_setup="
                + "3" * 40
                + f";provider_mode={mode}"
                ";provider_lock_kind=conformance"
                ";provider_conformance_only=true"
                ";provider_sdk_consumption_candidate=false"
                ";provider_candidate_differs_from_tracked=true"
                f";provider_consumption_classification={classification}"
                ";provider_release_identity_coherent=false"
                ";source_dirty=true"
            )

        mismatches = (
            ("source", "conformance_rehearsal_installed_static"),
            ("installed_static", "conformance_source"),
            ("installed_shared", "conformance_rehearsal_installed_static"),
        )
        for mode, classification in mismatches:
            with self.subTest(mode=mode, classification=classification):
                with self.assertRaisesRegex(ValueError, "pair is inconsistent"):
                    conformance.normalize_build_identity(identity(mode, classification))

    def test_transport_envelope_normalizes_contract_ids_and_nested_identity(
        self,
    ) -> None:
        def envelope(
            marker: str, mode: str, classification: str
        ) -> dict[str, object]:
            build_identity = (
                f"facman={'1' * 40};universal_launcher={'2' * 40};"
                f"universal_setup={'3' * 40};provider_mode={mode};"
                "provider_source_linkage=static;provider_lock_kind=conformance;"
                "provider_conformance_only=true;"
                "provider_sdk_consumption_candidate=false;"
                "provider_candidate_differs_from_tracked=false;"
                f"provider_consumption_classification={classification};"
                "provider_release_identity_coherent=true;source_dirty=false"
            )
            return {
                "schema": "facman.transport_response.v2",
                "request_id": f"request-{marker * 32}",
                "payload": {
                    "backend_identity": {
                        "build": {"build_identity": build_identity},
                    },
                },
                "operation": {
                    "operation_id": f"op-{marker * 32}",
                    "attempt_id": f"attempt-{marker * 32}",
                },
            }

        source = envelope("a", "source", "conformance_source")
        installed = envelope(
            "b", "installed_static", "conformance_rehearsal_installed_static"
        )
        self.assertEqual(
            conformance.normalize_semantic_value(source, {}),
            conformance.normalize_semantic_value(installed, {}),
        )

        malformed = envelope("c", "source", "conformance_source")
        malformed["request_id"] = "request-not-a-contract-id"
        with self.assertRaisesRegex(ValueError, "request_id is malformed"):
            conformance.normalize_semantic_value(malformed, {})

    def test_semantic_normalization_is_schema_scoped_and_rejects_unknown_paths(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)

            def observation(
                mode: str, mode_root: Path, address: str
            ) -> dict[str, object]:
                canonical_mode_root = mode_root.resolve()
                return {
                    "schema": "facman.provider_conformance_comparison.v1",
                    "provider_mode": mode,
                    "build_root": str(canonical_mode_root),
                    "loader": {
                        "runtime_path": str(canonical_mode_root / "runtime"),
                        "loaded_address": address,
                    },
                    "generated_at_utc": "2026-08-05T00:00:00Z",
                    "process_id": 123,
                }

            first = observation("source", root / "source", "0xDEADBEEF")
            second = observation("installed_shared", root / "installed", "0x12345678")
            normalized_first = conformance.normalize_semantic_value(
                first, {"mode-root": root / "source"}
            )
            normalized_second = conformance.normalize_semantic_value(
                second, {"mode-root": root / "installed"}
            )
            self.assertEqual(normalized_first, normalized_second)
            self.assertEqual(
                "2026-08-05T00:00:00Z", normalized_first["generated_at_utc"]
            )
            self.assertEqual(123, normalized_first["process_id"])
            changed_time = dict(first, generated_at_utc="2026-08-05T00:00:01Z")
            self.assertNotEqual(
                normalized_first,
                conformance.normalize_semantic_value(
                    changed_time, {"mode-root": root / "source"}
                ),
            )
            self.assertNotEqual(
                conformance.normalize_semantic_value({"address": "0xDEADBEEF"}, {}),
                conformance.normalize_semantic_value({"address": "0x12345678"}, {}),
            )
            self.assertEqual(
                {"url": "https://example.invalid/provider"},
                conformance.normalize_semantic_value(
                    {"url": "https://example.invalid/provider"}, {}
                ),
            )

            unknown = dict(first, detail=f"unexpected {root / 'leak'}")
            with self.assertRaisesRegex(ValueError, "unknown absolute path"):
                conformance.normalize_semantic_value(
                    unknown, {"mode-root": root / "source"}
                )

            wrong_schema = dict(first, schema="unknown.schema.v1")
            with self.assertRaisesRegex(ValueError, "unknown absolute path"):
                conformance.normalize_semantic_value(
                    wrong_schema, {"mode-root": root / "source"}
                )

    def test_declared_posix_path_requires_exact_approved_root_anchoring(self) -> None:
        replacements = [("/approved/mode", "<mode-root>")]
        self.assertEqual(
            "<mode-root>/runtime",
            conformance._normalize_declared_path(
                "/approved/mode/runtime", replacements
            ),
        )
        for value in (
            "<mode-root>/runtime",
            "/approved/mode-other/runtime",
            "/approved/mode/../../escape",
            "/other/root/runtime",
        ):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, "tokens|outside|non-canonical"):
                    conformance._normalize_declared_path(value, replacements)

    def test_absolute_path_detection_rejects_posix_windows_and_unc(self) -> None:
        for value in ("/tmp/sdk", "C:\\sdk\\root", "\\\\server\\share"):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, "absolute path"):
                    conformance.assert_path_independent_json({"value": value})

    def test_extract_last_json_object_ignores_build_output(self) -> None:
        output = 'configure\nbuild\n{"phase":"full","result":"pass"}\n'
        self.assertEqual(
            {"phase": "full", "result": "pass"},
            conformance.extract_last_json_object(output),
        )

    def test_facman_commands_use_explicit_modes_and_candidate_lock(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            sources = {
                spec.provider_id: self._provider_fixture(root / spec.provider_id, spec)[
                    0
                ]
                for spec in conformance.PROVIDERS
            }
            source_command = conformance._facman_configure_command(
                root / "facman",
                root / "build-source",
                root / "candidate.toml",
                "source",
                "cmake",
                "Release",
                None,
                sources,
            )
            prefixes = {
                "universal_launcher": root / "ulk-prefix",
                "universal_setup": root / "usk-prefix",
            }
            identities = {
                provider_id: prefix / "share" / "facman" / "identity.json"
                for provider_id, prefix in prefixes.items()
            }
            installed_command = conformance._facman_configure_command(
                root / "facman",
                root / "build-sdk",
                root / "candidate.toml",
                "installed_shared",
                "cmake",
                "Release",
                None,
                sources,
                prefixes,
                identities,
            )

            self.assertIn("-DFACMAN_PROVIDER_MODE=source", source_command)
            self.assertIn("-DFACMAN_PROVIDER_CONFORMANCE_ONLY=ON", source_command)
            self.assertTrue(
                any(
                    item.startswith("-DFLAUNCH_UNIVERSAL_LAUNCHER_ROOT=")
                    for item in source_command
                )
            )
            self.assertIn("-DFACMAN_PROVIDER_MODE=installed_shared", installed_command)
            self.assertTrue(
                any(
                    item.startswith("-DFACMAN_UNIVERSAL_SETUP_IDENTITY_FILE=")
                    for item in installed_command
                )
            )

    def test_installed_identity_must_pair_with_selected_sdk_root(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            prefixes = {
                "universal_launcher": root / "installed" / "ulk",
                "universal_setup": root / "installed" / "usk",
            }
            matching = {
                provider_id: prefix / "share" / "facman" / "identity.json"
                for provider_id, prefix in prefixes.items()
            }
            conformance._validate_identity_pairing(prefixes, matching)

            relocated = {
                provider_id: root / "relocated" / provider_id
                for provider_id in prefixes
            }
            with self.assertRaisesRegex(ValueError, "inside its selected SDK root"):
                conformance._validate_identity_pairing(relocated, matching)

    def test_hosted_workflow_binds_exact_canonical_commits_and_no_skip(self) -> None:
        workflow = (
            Path(__file__).resolve().parents[1]
            / ".github"
            / "workflows"
            / "provider-conformance.yml"
        ).read_text(encoding="utf-8")
        self.assertIn(
            "FACMAN_EXACT_HEAD: ${{ github.event.pull_request.head.sha || github.sha }}",
            workflow,
        )
        self.assertIn("ref: ${{ env.FACMAN_EXACT_HEAD }}", workflow)
        self.assertIn('test "$(git rev-parse HEAD)" = "$FACMAN_EXACT_HEAD"', workflow)
        self.assertIn(
            "${{ env.FACMAN_EXACT_HEAD }}",
            workflow,
        )
        for spec in conformance.PROVIDERS:
            self.assertIn(spec.canonical_commit, workflow)
        self.assertIn("tools/provider_conformance.py", workflow)
        self.assertNotIn("--skip-provider-self-conformance", workflow)
        self.assertIn("windows-2022", workflow)
        self.assertIn("ubuntu-24.04", workflow)
        self.assertIn("name: bounded-provider-input-conformance", workflow)
        self.assertIn("bounded canonical provider inputs", workflow)
        self.assertNotIn("canonical-source-and-sdk-equivalence", workflow)
        self.assertNotIn("private-runtime proof", workflow)
        self.assertEqual(2, workflow.count("release/index/workspace_lock.v1.toml"))
        self.assertEqual(2, workflow.count("release/index/providers.lock.v2.toml"))
        self.assertEqual(2, workflow.count("tests/native/facman_abi_layout_smoke.cpp"))


if __name__ == "__main__":
    unittest.main()
