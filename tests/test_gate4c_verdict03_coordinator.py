# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools import gate4c_verdict03_coordinator as COORDINATOR


class Gate4CVerdict03CoordinatorTests(unittest.TestCase):
    def configured_fixture(self, root: Path) -> Path:
        task_root = root / COORDINATOR.WORK_UNIT
        operator = task_root / "operator"
        workspace = task_root / "workspace"
        repository = root / "factorio-launcher"
        launcher = root / "universal-launcher"
        setup = root / "universal-setup"
        for directory in (
            operator,
            workspace,
            repository,
            launcher,
            setup,
        ):
            directory.mkdir(parents=True, exist_ok=True)
        files = {
            "artifact_manifest": task_root / "artifacts" / "binding.json",
            "facman_artifact": task_root / "artifacts" / "facman.exe",
            "factorio_executable": root / "Factorio" / "factorio.exe",
            "source_artifact": root / "Inbox" / "factorio.zip",
            "source_member_executable": task_root / "source" / "factorio.exe",
        }
        for path in files.values():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"fixture")
        config = {
            "schema": COORDINATOR.CONFIG_SCHEMA,
            "task_root": str(task_root),
            "repository_root": str(repository),
            "launcher_repository": str(launcher),
            "setup_repository": str(setup),
            **{key: str(path) for key, path in files.items()},
            "workspace": str(workspace),
            "instance_id": COORDINATOR.PREFLIGHT.EXPECTED_INSTANCE_ID,
            "reviewer_id": f"windows:{os.environ.get('USERNAME', '')}",
            "first_operation_id": "gate4c-verdict03-launch1-test",
            "second_operation_id": "gate4c-verdict03-launch2-test",
        }
        config_path = operator / "verdict03-config.json"
        config_path.write_text(json.dumps(config), encoding="utf-8")
        return config_path

    def test_exact_config_is_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            config_path = self.configured_fixture(Path(temporary))
            value = COORDINATOR.validate_config(config_path)
            self.assertEqual(value["schema"], COORDINATOR.CONFIG_SCHEMA)

    def test_prior_verdict_root_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            config_path = self.configured_fixture(Path(temporary))
            value = json.loads(config_path.read_text(encoding="utf-8"))
            value["task_root"] = str(
                Path(temporary)
                / "FACMAN-HERMETIC-STANDALONE-PLAY-VERDICT-01"
            )
            config_path.write_text(json.dumps(value), encoding="utf-8")
            with self.assertRaises(COORDINATOR.CoordinatorError):
                COORDINATOR.validate_config(config_path)

    def test_prepare_does_not_require_an_elevated_coordinator(self) -> None:
        source = Path(COORDINATOR.EVIDENCE.__file__).read_text(encoding="utf-8")
        function = source[
            source.index("def prepare_session(") : source.index(
                "\ndef finish_comparison(", source.index("def prepare_session(")
            )
        ]
        self.assertNotIn("is_elevated", function)
        preflight_source = Path(
            COORDINATOR.PREFLIGHT.__file__
        ).read_text(encoding="utf-8")
        self.assertNotIn(
            'add_blocker(blockers, "observer_elevation_required"',
            preflight_source,
        )

    def test_human_pass_sets_every_frozen_check(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config_path = self.configured_fixture(root)
            session = {
                "operation_id": "gate4c-verdict03-launch1-test",
                "session_digest": "1" * 64,
            }
            packet = {"packet_digest": "2" * 64}
            out = root / "human.json"
            args = mock.Mock(
                config=config_path,
                session=root / "session.json",
                packet=root / "packet.json",
                launch=1,
                disposition="Pass",
                false_check=[],
                notes="reviewed",
                out=out,
            )
            with (
                mock.patch.object(
                    COORDINATOR.EVIDENCE,
                    "validate_session_record",
                    return_value=session,
                ),
                mock.patch.object(
                    COORDINATOR.EVIDENCE,
                    "validate_native_packet",
                    return_value=packet,
                ),
            ):
                COORDINATOR.human(args)
            record = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(
                set(record["checks"]),
                COORDINATOR.EVIDENCE.FIRST_LAUNCH_CHECKS,
            )
            self.assertTrue(all(record["checks"].values()))

    def test_plan_approval_is_exact_and_digest_bound(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config_path = self.configured_fixture(root)
            config = json.loads(config_path.read_text(encoding="utf-8"))
            operation_id = config["first_operation_id"]
            plan = {
                "schema": COORDINATOR.PLAN_SCHEMA,
                "canonicalization_version": "facman.sorted-json.v1",
                "plan_digest": "a" * 64,
                "plan_core": {
                    "operation": "instance.play",
                    "instance_id": config["instance_id"],
                    "launch_intent": "menu",
                    "isolation_mode": "hermetic",
                    "policy_digest": (
                        COORDINATOR.PREFLIGHT.POLICY_DIGEST
                    ),
                },
                "public_command_available": False,
                "human_verdict_recorded": False,
            }
            plan_path = root / "plan.json"
            plan_path.write_text(json.dumps(plan), encoding="utf-8")
            out = (
                Path(config["task_root"])
                / "operator"
                / "approvals"
                / f"{operation_id}-plan-approval.json"
            )
            result = COORDINATOR.approve_plan(
                mock.Mock(
                    config=config_path,
                    operation_id=operation_id,
                    plan=plan_path,
                    out=out,
                )
            )
            record = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(record["plan_digest"], plan["plan_digest"])
            self.assertEqual(result["digest"], record["approval_digest"])

    def test_plan_approval_refuses_alternate_intent(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config_path = self.configured_fixture(root)
            config = json.loads(config_path.read_text(encoding="utf-8"))
            operation_id = config["first_operation_id"]
            plan = {
                "schema": COORDINATOR.PLAN_SCHEMA,
                "canonicalization_version": "facman.sorted-json.v1",
                "plan_digest": "b" * 64,
                "plan_core": {
                    "operation": "instance.play",
                    "instance_id": config["instance_id"],
                    "launch_intent": "load_save",
                    "isolation_mode": "hermetic",
                    "policy_digest": (
                        COORDINATOR.PREFLIGHT.POLICY_DIGEST
                    ),
                },
                "public_command_available": False,
                "human_verdict_recorded": False,
            }
            plan_path = root / "plan.json"
            plan_path.write_text(json.dumps(plan), encoding="utf-8")
            with self.assertRaises(COORDINATOR.CoordinatorError):
                COORDINATOR.approve_plan(
                    mock.Mock(
                        config=config_path,
                        operation_id=operation_id,
                        plan=plan_path,
                        out=(
                            Path(config["task_root"])
                            / "operator"
                            / "approvals"
                            / f"{operation_id}-plan-approval.json"
                        ),
                    )
                )


if __name__ == "__main__":
    unittest.main()
