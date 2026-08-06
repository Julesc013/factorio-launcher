# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import copy
import json
import tempfile
import tomllib
import unittest
from pathlib import Path
from unittest import mock

from tools import (
    integration_source_observation,
    release_coherence_negative_control,
)
from tools.package import pipeline


ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_LOCK = ROOT / "release" / "index" / "workspace_lock.v1.toml"
PROVIDER_LOCK = ROOT / "release" / "index" / "providers.lock.v2.toml"


class IntegrationSourceObservationTests(unittest.TestCase):
    def setUp(self) -> None:
        with WORKSPACE_LOCK.open("rb") as handle:
            lock = tomllib.load(handle)
        self.workspace = {
            item["id"]: item
            for item in lock["component"]
            if item["id"] in {"universal_launcher", "universal_setup"}
        }
        self.current = self._current_observation()

    def _current_observation(self) -> dict[str, object]:
        providers = []
        for index, provider_id in enumerate(sorted(self.workspace), start=2):
            locked = self.workspace[provider_id]
            providers.append(
                {
                    "id": provider_id,
                    "pin": locked["pin"],
                    "origin_remote": locked["remote"],
                    "required_ref": locked["required_ref"],
                    "local_tracking_ref": "refs/remotes/origin/main",
                    "checkout": {
                        "head": locked["pin"],
                        "tree": str(index) * 40,
                        "dirty": False,
                    },
                    "abi_versions": [],
                    "status": "pass",
                }
            )
        return {
            "schema": "facman.current_checkout_observation.v2",
            "result": {"status": "pass", "problem_count": 0, "problems": []},
            "source": {
                "head": "a" * 40,
                "tree": "b" * 40,
                "dirty": False,
                "branch": "task/provider-input",
                "origin_remote": "https://github.com/Julesc013/factorio-launcher.git",
                "expected_ci_sha": "a" * 40,
                "expected_ci_sha_match": True,
            },
            "observation_policy": {
                "sha256": "c" * 64,
                "line_ending_profile": {"id": "lf_checkout"},
            },
            "providers": providers,
        }

    def _build_root(self, root: Path, *, compiler_in_cache: bool = True) -> Path:
        build = root / "build"
        build.mkdir()
        compiler = root / "compiler"
        compiler.write_bytes(b"fixture compiler\n")
        identity = ";".join(
            [
                "facman=" + "a" * 40,
                "universal_launcher=" + self.workspace["universal_launcher"]["pin"],
                "universal_setup=" + self.workspace["universal_setup"]["pin"],
                "provider_mode=source",
                "provider_lock_kind=tracked",
                "provider_conformance_only=false",
                "provider_sdk_consumption_candidate=false",
                "provider_candidate_differs_from_tracked=false",
                "provider_consumption_classification=tracked_source",
                "provider_release_identity_coherent=false",
                "source_dirty=false",
            ]
        )
        (build / "facman-build-identity.v1.txt").write_text(
            identity + "\n", encoding="utf-8"
        )
        cache_lines = ["CMAKE_GENERATOR:INTERNAL=Ninja"]
        if compiler_in_cache:
            cache_lines.append(f"CMAKE_CXX_COMPILER:FILEPATH={compiler}")
        cache_lines.append("FACMAN_PROVIDER_MODE:STRING=source")
        (build / "CMakeCache.txt").write_text(
            "\n".join(cache_lines) + "\n", encoding="utf-8"
        )
        if not compiler_in_cache:
            cmake_record = build / "CMakeFiles" / "4.2.3" / "CMakeCXXCompiler.cmake"
            cmake_record.parent.mkdir(parents=True)
            cmake_record.write_text(
                f'set(CMAKE_CXX_COMPILER "{compiler.as_posix()}")\n',
                encoding="utf-8",
            )
        return build

    def test_checkout_projection_contains_facts_without_lock_interpretation(self) -> None:
        observation = integration_source_observation.checkout_source_observation(
            self.current
        )
        self.assertEqual(observation["schema"], "facman.checkout_source_observation.v1")
        self.assertNotIn("workspace_lock", observation)
        self.assertFalse(observation["source_closure_proven"])
        self.assertFalse(any(observation["authority"].values()))
        self.assertEqual(
            integration_source_observation.normalize_checkout_source_observation(
                observation
            ),
            observation,
        )

    def test_integration_projection_binds_workspace_build_target_and_authority(self) -> None:
        checkout = integration_source_observation.checkout_source_observation(
            self.current
        )
        with tempfile.TemporaryDirectory() as temporary:
            build_root = self._build_root(Path(temporary))
            observation = integration_source_observation.integration_source_observation(
                checkout,
                WORKSPACE_LOCK,
                build_root,
                "windows_portable_cli_x64",
            )
            path = Path(temporary) / "integration.json"
            path.write_text(json.dumps(observation), encoding="utf-8")
            with mock.patch.object(
                pipeline,
                "pinned_source_revisions",
                return_value={
                    "factorio_launcher": "a" * 40,
                    "factorio_binding": "d" * 40,
                    "universal_launcher": self.workspace["universal_launcher"]["pin"],
                    "universal_setup": self.workspace["universal_setup"]["pin"],
                },
            ):
                loaded = pipeline.package_integration_source_observation(
                    "windows_portable_cli_x64",
                    path,
                )
        self.assertIsNotNone(loaded)
        self.assertTrue(observation["integration_coherent"])
        self.assertFalse(observation["release_eligible"])
        self.assertFalse(observation["provider_adoption"])
        self.assertFalse(observation["signing"])
        self.assertFalse(observation["publication"])
        self.assertEqual(
            observation["artifact_class"], "unpublished_integration_test_package"
        )

    def test_visual_studio_compiler_identity_uses_generated_cmake_record(self) -> None:
        checkout = integration_source_observation.checkout_source_observation(
            self.current
        )
        with tempfile.TemporaryDirectory() as temporary:
            build_root = self._build_root(Path(temporary), compiler_in_cache=False)
            observation = integration_source_observation.integration_source_observation(
                checkout,
                WORKSPACE_LOCK,
                build_root,
                "windows_portable_cli_x64",
            )
        self.assertRegex(
            observation["toolchain"]["cxx_compiler_sha256"],
            r"^[0-9a-f]{64}$",
        )

    def test_integration_projection_refuses_provider_or_compiled_identity_drift(self) -> None:
        checkout = integration_source_observation.checkout_source_observation(
            self.current
        )
        changed = copy.deepcopy(checkout)
        changed["providers"][0]["commit"] = "f" * 40
        core = dict(changed)
        core.pop("observation_digest")
        changed["observation_digest"] = integration_source_observation.domain_digest_value(
            integration_source_observation.CHECKOUT_DOMAIN,
            core,
        )
        with tempfile.TemporaryDirectory() as temporary:
            build_root = self._build_root(Path(temporary))
            with self.assertRaisesRegex(ValueError, "differs from workspace lock"):
                integration_source_observation.integration_source_observation(
                    changed,
                    WORKSPACE_LOCK,
                    build_root,
                    "windows_portable_cli_x64",
                )

    def test_normalizer_refuses_rehashed_provider_drift(self) -> None:
        checkout = integration_source_observation.checkout_source_observation(
            self.current
        )
        with tempfile.TemporaryDirectory() as temporary:
            build_root = self._build_root(Path(temporary))
            observation = integration_source_observation.integration_source_observation(
                checkout,
                WORKSPACE_LOCK,
                build_root,
                "windows_portable_cli_x64",
            )
            observation["providers"][0]["commit"] = "f" * 40
            core = dict(observation)
            core.pop("observation_digest")
            observation["observation_digest"] = (
                integration_source_observation.domain_digest_value(
                    integration_source_observation.INTEGRATION_DOMAIN,
                    core,
                )
            )
            with self.assertRaisesRegex(ValueError, "differs from workspace lock"):
                integration_source_observation.normalize_integration_source_observation(
                    observation,
                    workspace_lock_path=WORKSPACE_LOCK,
                    expected_profile="windows_portable_cli_x64",
                )

    def test_package_refuses_integration_observation_for_another_source(self) -> None:
        checkout = integration_source_observation.checkout_source_observation(
            self.current
        )
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            observation = integration_source_observation.integration_source_observation(
                checkout,
                WORKSPACE_LOCK,
                self._build_root(root),
                "windows_portable_cli_x64",
            )
            path = root / "integration.json"
            path.write_text(json.dumps(observation), encoding="utf-8")
            with mock.patch.object(
                pipeline,
                "pinned_source_revisions",
                return_value={
                    "factorio_launcher": "e" * 40,
                    "factorio_binding": "d" * 40,
                    "universal_launcher": self.workspace["universal_launcher"]["pin"],
                    "universal_setup": self.workspace["universal_setup"]["pin"],
                },
            ):
                with self.assertRaisesRegex(ValueError, "FacMan commit differs"):
                    pipeline.package_integration_source_observation(
                        "windows_portable_cli_x64",
                        path,
                    )

    def test_release_negative_control_requires_exact_two_provider_refusals(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            proof_root = Path(temporary)
            report = release_coherence_negative_control.prove(
                self.current,
                WORKSPACE_LOCK,
                PROVIDER_LOCK,
                proof_root / "source.json",
                proof_root / "release-package",
            )
        self.assertEqual(report["result"], "pass_exact_release_refusal")
        self.assertEqual(
            report["expected_provider_mismatches"],
            ["universal_launcher", "universal_setup"],
        )
        self.assertFalse(report["release_source_observation_created"])
        self.assertFalse(report["release_package_created"])
        self.assertFalse(report["tracked_lock_mutated"])
        self.assertFalse(report["authority_promoted"])

    def test_release_negative_control_expires_after_reconciliation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            workspace = root / "workspace.toml"
            workspace.write_bytes(WORKSPACE_LOCK.read_bytes())
            release = PROVIDER_LOCK.read_text(encoding="utf-8")
            release = release.replace(
                "719a3ec240831547071d69098e1fe8c76f327fb7",
                self.workspace["universal_launcher"]["pin"],
            )
            provider = root / "providers.toml"
            provider.write_text(release, encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "negative control is stale"):
                release_coherence_negative_control.prove(
                    self.current,
                    workspace,
                    provider,
                    root / "source.json",
                    root / "package",
                )


if __name__ == "__main__":
    unittest.main()
