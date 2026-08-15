# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import argparse
import tempfile
import unittest
from pathlib import Path

from tools import json_contract, preview_obligation_factory as factory


class PreviewObligationFactoryTests(unittest.TestCase):
    CANARY_ULK = "7" * 40

    def _args(self, root: Path, **overrides: object) -> argparse.Namespace:
        values: dict[str, object] = {
            "build_root": None,
            "package_root": None,
            "artifact": None,
            "resolution": None,
            "configuration": "Debug",
            "provider_class": "repaired_provider_canary",
            "expected_ulk_revision": self.CANARY_ULK,
            "execute": False,
            "evidence_dir": root / "evidence",
        }
        values.update(overrides)
        return argparse.Namespace(**values)

    def _write_build_identity(
        self,
        build_root: Path,
        *,
        facman: str,
        universal_launcher: str,
        universal_setup: str,
        source_dirty: bool,
    ) -> None:
        build_root.mkdir()
        fields = {
            "facman": facman,
            "universal_launcher": universal_launcher,
            "universal_setup": universal_setup,
            "provider_mode": "source",
            "provider_source_linkage": "static",
            "provider_lock_kind": "sdk_candidate",
            "provider_conformance_only": "false",
            "provider_sdk_consumption_candidate": "true",
            "provider_candidate_differs_from_tracked": "true",
            "provider_consumption_classification": "sdk_candidate_source",
            "provider_release_identity_coherent": "false",
            "ulk_session_consumer_canary": "false",
            "source_dirty": str(source_dirty).lower(),
        }
        (build_root / "facman-build-identity.v1.txt").write_text(
            ";".join(f"{key}={value}" for key, value in fields.items()) + "\n",
            encoding="utf-8",
        )

    def test_registry_exactly_matches_release_compiler(self) -> None:
        self.assertEqual(factory.validate_registry(), [])
        self.assertEqual(len(factory.resolved_obligations()), 23)
        self.assertEqual(set(factory.resolved_obligations()), set(factory.SPECS))

    def test_canary_plan_separates_package_evidence_from_canonical_resolution(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            args = self._args(root)
            report = factory.run_factory(args)
        by_id = {item["id"]: item for item in report["obligations"]}
        self.assertEqual(len(by_id), 23)
        self.assertEqual(by_id["schema_validate"]["status"], "planned")
        self.assertEqual(by_id["package_runtime_smoke"]["status"], "blocked")
        self.assertEqual(
            by_id["package_runtime_smoke"]["classification"],
            "missing_input",
        )
        self.assertEqual(
            by_id["package_adapter_round_trip"]["classification"],
            "canonical_release_resolution_pending",
        )
        self.assertFalse(report["authority"]["release_authorized"])
        self.assertEqual(
            report["qualification_plan"]["schema"],
            "facman.resolved_qualification_plan.v1",
        )
        self.assertFalse(report["qualification_plan"]["qualified"])
        self.assertEqual(
            report["source"]["provider_revisions"]["universal_launcher"],
            self.CANARY_ULK,
        )
        self.assertRegex(report["qualification_plan"]["resolution_digest"], r"^[0-9a-f]{64}$")
        schema = json_contract.load_schema(
            factory.SCHEMA
        )
        self.assertEqual(json_contract.validate(report, schema), [])

    def test_every_obligation_has_commands_and_invalidation_law(self) -> None:
        for obligation, spec in factory.SPECS.items():
            with self.subTest(obligation=obligation):
                self.assertTrue(spec.commands)
                self.assertTrue(spec.invalidation_paths)

    def test_build_root_must_match_exact_facman_head(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            build_root = root / "build"
            providers = factory._provider_revisions(
                "repaired_provider_canary", self.CANARY_ULK
            )
            self._write_build_identity(
                build_root,
                facman="0" * 40,
                universal_launcher=providers["universal_launcher"],
                universal_setup=providers["universal_setup"],
                source_dirty=bool(factory._git("status", "--porcelain")),
            )
            with self.assertRaisesRegex(
                ValueError, "build identity facman differs from obligation source custody"
            ):
                factory.run_factory(self._args(root, build_root=build_root))

    def test_canary_build_root_must_match_declared_provider(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            build_root = root / "build"
            providers = factory._provider_revisions(
                "repaired_provider_canary", self.CANARY_ULK
            )
            self._write_build_identity(
                build_root,
                facman=factory._git("rev-parse", "HEAD"),
                universal_launcher="8" * 40,
                universal_setup=providers["universal_setup"],
                source_dirty=bool(factory._git("status", "--porcelain")),
            )
            with self.assertRaisesRegex(
                ValueError, "build identity universal_launcher differs"
            ):
                factory.run_factory(self._args(root, build_root=build_root))

    def test_exact_canary_build_root_is_accepted_for_planning(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            build_root = root / "build"
            providers = factory._provider_revisions(
                "repaired_provider_canary", self.CANARY_ULK
            )
            self._write_build_identity(
                build_root,
                facman=factory._git("rev-parse", "HEAD"),
                universal_launcher=providers["universal_launcher"],
                universal_setup=providers["universal_setup"],
                source_dirty=bool(factory._git("status", "--porcelain")),
            )
            report = factory.run_factory(self._args(root, build_root=build_root))
        self.assertEqual(report["source"]["commit"], factory._git("rev-parse", "HEAD"))
        self.assertRegex(report["source"]["build_identity_sha256"], r"^[0-9a-f]{64}$")
        self.assertEqual(report["counts"], {
            "pass": 0,
            "fail": 0,
            "blocked": 7,
            "planned": 16,
        })

    def test_canary_package_plan_uses_explicit_noncanonical_custody(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            build_root = root / "build"
            package_root = root / "package"
            artifact = root / "candidate.zip"
            providers = factory._provider_revisions(
                "repaired_provider_canary", self.CANARY_ULK
            )
            self._write_build_identity(
                build_root,
                facman=factory._git("rev-parse", "HEAD"),
                universal_launcher=providers["universal_launcher"],
                universal_setup=providers["universal_setup"],
                source_dirty=bool(factory._git("status", "--porcelain")),
            )
            package_root.mkdir()
            artifact.touch()
            report = factory.run_factory(
                self._args(
                    root,
                    build_root=build_root,
                    package_root=package_root,
                    artifact=artifact,
                )
            )
        by_id = {item["id"]: item for item in report["obligations"]}
        self.assertEqual(report["counts"], {
            "pass": 0,
            "fail": 0,
            "blocked": 1,
            "planned": 22,
        })
        self.assertEqual(
            by_id["package_adapter_round_trip"]["classification"],
            "canonical_release_resolution_pending",
        )
        self.assertIn(
            "--repaired-provider-canary-ulk",
            by_id["package_reproducibility_proof"]["commands"][0],
        )
        self.assertIn(
            self.CANARY_ULK,
            by_id["package_reproducibility_proof"]["commands"][0],
        )

    def test_canary_requires_an_exact_noncanonical_provider_revision(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            with self.assertRaisesRegex(ValueError, "require --expected-ulk-revision"):
                factory.run_factory(self._args(root, expected_ulk_revision=None))
            tracked = factory._provider_revisions("canonical", None)
            with self.assertRaisesRegex(ValueError, "must differ from tracked canonical ULK"):
                factory.run_factory(
                    self._args(
                        root,
                        expected_ulk_revision=tracked["universal_launcher"],
                    )
                )


if __name__ == "__main__":
    unittest.main()
