# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import json
import os
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path
from unittest.mock import patch

from tools import instance_isolated_verdict_coordinator as COORDINATOR
from tools import gate4c_verdict_preflight as PREFLIGHT
from tools.play_verdict_route import (
    INSTANCE_ISOLATED_REVALIDATION as ROUTE,
    QUALIFICATION_SCHEMA,
    RouteBindingError,
    digest_value,
    load_qualification_binding,
)


def qualification_value() -> dict[str, object]:
    core: dict[str, object] = {
        "schema": QUALIFICATION_SCHEMA,
        "canonicalization_version": "facman.sorted-json.v1",
        "route_id": ROUTE.route_id,
        "work_unit": ROUTE.work_unit,
        "source_binding": {
            "factorio_launcher": {
                "revision": "1" * 40,
                "required_ref": "origin/dev",
            },
            "universal_launcher": {
                "revision": "2" * 40,
                "required_ref": "origin/main",
            },
            "universal_setup": {
                "revision": "3" * 40,
                "required_ref": "origin/main",
            },
        },
        "artifacts": {
            name: {
                "relative_path": relative,
                "size": index + 1,
                "sha256": str(index + 1) * 64,
            }
            for index, (name, relative) in enumerate(
                (
                    ("facman", "Debug/facman.exe"),
                    (
                        "candidate_smoke",
                        "Debug/facman_hermetic_play_candidate_smoke.exe",
                    ),
                    (
                        "verdict_harness",
                        "Debug/facman_gate4c_verdict_harness.exe",
                    ),
                    ("cmake_cache", "CMakeCache.txt"),
                )
            )
        },
        "factorio": {
            "version": "2.0.77",
            "sha256": "a" * 64,
            "signer": "Wube Software Ltd",
        },
        "instance": {
            "instance_id": ROUTE.instance_id,
            "spec_digest": "b" * 64,
            "binding_digest": "c" * 64,
            "readiness_digest": "d" * 64,
        },
    }
    return {**core, "qualification_digest": digest_value(core)}


class InstanceIsolatedVerdictCoordinatorTests(unittest.TestCase):
    def test_instance_preflight_cannot_bypass_qualification(self) -> None:
        with self.assertRaises(PREFLIGHT.PreflightError):
            PREFLIGHT.build_preflight(
                Namespace(),
                route=ROUTE,
                qualification=None,
            )

    def test_qualification_binding_is_closed_and_hash_bound(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "qualification.json"
            value = qualification_value()
            path.write_text(json.dumps(value), encoding="utf-8")
            binding = load_qualification_binding(path, ROUTE)
            self.assertEqual(binding.work_unit, ROUTE.work_unit)
            self.assertEqual(
                set(binding.artifact_mapping()),
                {
                    "facman",
                    "candidate_smoke",
                    "verdict_harness",
                    "cmake_cache",
                },
            )

            value["factorio"]["version"] = "2.0.78"  # type: ignore[index]
            path.write_text(json.dumps(value), encoding="utf-8")
            with self.assertRaises(RouteBindingError):
                load_qualification_binding(path, ROUTE)

    def test_configuration_and_plan_approval_are_non_executing(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            task_root = root / ROUTE.work_unit
            operator = task_root / "operator"
            workspace = task_root / "workspace"
            repository = root / "facman"
            launcher = root / "launcher"
            setup = root / "setup"
            for directory in (
                operator,
                workspace,
                repository,
                launcher,
                setup,
            ):
                directory.mkdir(parents=True)
            files = {
                "qualification_binding": task_root
                / "qualification-binding.json",
                "artifact_manifest": task_root / "manifest.json",
                "facman_artifact": task_root / "facman.exe",
                "factorio_executable": task_root / "factorio.exe",
                "source_artifact": task_root / "source.zip",
                "source_member_executable": task_root / "source-factorio.exe",
            }
            qualification = qualification_value()
            files["qualification_binding"].write_text(
                json.dumps(qualification), encoding="utf-8"
            )
            for key, path in files.items():
                if key != "qualification_binding":
                    path.write_bytes(key.encode("utf-8"))
            first = ROUTE.operation_prefix + "launch1"
            second = ROUTE.operation_prefix + "launch2"
            config = {
                "schema": COORDINATOR.CONFIG_SCHEMA,
                "task_root": str(task_root),
                "repository_root": str(repository),
                "launcher_repository": str(launcher),
                "setup_repository": str(setup),
                "qualification_binding": str(
                    files["qualification_binding"]
                ),
                "qualification_digest": qualification[
                    "qualification_digest"
                ],
                "artifact_manifest": str(files["artifact_manifest"]),
                "facman_artifact": str(files["facman_artifact"]),
                "workspace": str(workspace),
                "instance_id": ROUTE.instance_id,
                "factorio_executable": str(files["factorio_executable"]),
                "source_artifact": str(files["source_artifact"]),
                "source_member_executable": str(
                    files["source_member_executable"]
                ),
                "reviewer_id": f"windows:{os.environ.get('USERNAME', '')}",
                "first_operation_id": first,
                "second_operation_id": second,
            }
            config_path = operator / "instance-isolated-config.json"
            config_path.write_text(json.dumps(config), encoding="utf-8")
            loaded, binding = COORDINATOR.validate_config(config_path)
            self.assertEqual(loaded["instance_id"], ROUTE.instance_id)
            self.assertEqual(
                binding.qualification_digest,
                qualification["qualification_digest"],
            )

            plan = {
                "schema": ROUTE.plan_schema,
                "canonicalization_version": "facman.sorted-json.v1",
                "plan_core": {
                    "operation": "instance.play",
                    "instance_id": ROUTE.instance_id,
                    "launch_intent": "menu",
                    "isolation_mode": ROUTE.isolation_mode,
                    "policy_digest": ROUTE.policy_digest,
                },
                "plan_digest": "e" * 64,
                "public_command_available": False,
                "human_verdict_recorded": False,
            }
            plan_path = task_root / "plan.json"
            plan_path.write_text(json.dumps(plan), encoding="utf-8")
            out = (
                operator
                / "approvals"
                / f"{first}-plan-approval.json"
            )
            result = COORDINATOR.approve_plan(
                Namespace(
                    config=config_path,
                    operation_id=first,
                    plan=plan_path,
                    out=out,
                )
            )
            approval = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(result["plan_digest"], "e" * 64)
            self.assertFalse(approval["permit_issued"])
            self.assertFalse(approval["process_started"])

    def test_stage_reuses_only_an_exact_prequalified_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            task_root = root / ROUTE.work_unit
            workspace = task_root / "workspace"
            source_member = (
                task_root
                / "source"
                / "portable-package-inspection"
                / "factorio.exe"
            )
            workspace.mkdir(parents=True)
            source_member.parent.mkdir(parents=True)
            source_member.write_bytes(b"factorio")
            candidate_build = root / "build"
            candidate_build.mkdir()
            facman = candidate_build / "facman.exe"
            facman.write_bytes(b"facman")
            factorio = root / "factorio.exe"
            factorio.write_bytes(b"factorio")
            source_artifact = root / "factorio.zip"
            source_artifact.write_bytes(b"source")
            repositories = [root / name for name in ("repo", "launcher", "setup")]
            for repository in repositories:
                repository.mkdir()
            qualification_path = root / "qualification.json"
            qualification_path.write_text(
                json.dumps(qualification_value()),
                encoding="utf-8",
            )

            def copy_artifacts(
                _source: Path,
                destination: Path,
                _qualification: object,
            ):
                destination.mkdir(parents=True)
                paths = {}
                records = []
                for logical_name, name in (
                    ("facman", "facman.exe"),
                    (
                        "candidate_smoke",
                        "facman_hermetic_play_candidate_smoke.exe",
                    ),
                    (
                        "verdict_harness",
                        "facman_gate4c_verdict_harness.exe",
                    ),
                    ("cmake_cache", "CMakeCache.txt"),
                ):
                    path = destination / name
                    path.write_bytes(logical_name.encode("utf-8"))
                    paths[logical_name] = path
                    records.append(
                        {
                            "name": name,
                            "bytes": path.stat().st_size,
                            "sha256": PREFLIGHT.sha256_file(path),
                            "logical_name": logical_name,
                        }
                    )
                return records, paths

            with (
                patch.object(
                    COORDINATOR,
                    "_qualified_source_paths",
                    return_value={"facman": facman},
                ),
                patch.object(COORDINATOR, "_exact_repository_inputs"),
                patch.object(
                    COORDINATOR,
                    "_validate_staged_candidate",
                ) as validate,
                patch.object(
                    COORDINATOR,
                    "_copy_qualified_artifacts",
                    side_effect=copy_artifacts,
                ),
                patch.object(
                    COORDINATOR,
                    "_extract_authenticated_executable",
                ) as extract,
                patch.object(COORDINATOR, "_stage_workspace") as create_workspace,
            ):
                result = COORDINATOR.stage(
                    Namespace(
                        task_root=task_root,
                        candidate_build=candidate_build,
                        qualification_binding=qualification_path,
                        repository_root=repositories[0],
                        launcher_repository=repositories[1],
                        setup_repository=repositories[2],
                        factorio_executable=factorio,
                        source_artifact=source_artifact,
                        first_operation_id=ROUTE.operation_prefix + "launch1",
                        second_operation_id=ROUTE.operation_prefix + "launch2",
                    )
                )

            validate.assert_called_once()
            extract.assert_not_called()
            create_workspace.assert_not_called()
            self.assertEqual(result["workspace"], str(workspace))
            self.assertTrue(Path(result["config"]).is_file())


if __name__ == "__main__":
    unittest.main()
