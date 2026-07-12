# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import json
import os
import tempfile
import unittest
import zipfile
from pathlib import Path

from native_cli import invoke
from tools import json_contract


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_INSTALL = ROOT / "tests" / "fixtures" / "fake_factorio_install"
SCHEMA_ROOT = ROOT / "contracts" / "schema" / "factorio"


def call(workspace: Path, *args: str, success: bool = True, env: dict[str, str] | None = None) -> dict:
    code, stdout, stderr = invoke(["--workspace", str(workspace), *args, "--json"], env=env)
    if success and code != 0:
        raise AssertionError(stderr or stdout)
    if not success and code == 0:
        raise AssertionError(f"command unexpectedly succeeded: {stdout}")
    return json.loads(stdout or stderr)


def setup(workspace: Path) -> Path:
    call(workspace, "installs", "import", str(FIXTURE_INSTALL), "--id", "fixture")
    call(workspace, "instances", "create", "Solver", "--id", "solver", "--install", "fixture")
    return workspace / "instances" / "solver"


def write_mod(path: Path, name: str, version: str, dependencies: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    info = {
        "name": name,
        "title": name,
        "version": version,
        "factorio_version": "2.0",
        "dependencies": dependencies or ["base >= 2.0"],
    }
    entry = zipfile.ZipInfo(f"{name}_{version}/info.json", (2026, 7, 12, 0, 0, 0))
    entry.external_attr = 0o644 << 16
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_STORED) as archive:
        archive.writestr(entry, json.dumps(info, sort_keys=True) + "\n")


def lock_text(instance: str, mods: list[tuple[str, str]]) -> str:
    return json.dumps(
        {
            "lockfile_version": 1,
            "schema": "factorio.modset_lock.v1",
            "instance_id": instance,
            "factorio_version": "2.0.77",
            "mods": [{"name": name, "version": version, "enabled": True} for name, version in mods],
        },
        separators=(",", ":"),
    ) + "\n"


class LocalModsetSolverTests(unittest.TestCase):
    def test_dependency_plan_is_byte_deterministic_and_honors_tie_breaks(self) -> None:
        with tempfile.TemporaryDirectory(prefix="facman solver ") as value:
            workspace = Path(value)
            instance = setup(workspace)
            mods = instance / "mods"
            write_mod(mods / "library_2.0.0.zip", "library", "2.0.0")
            write_mod(mods / "application_1.0.0.zip", "application", "1.0.0", ["base >= 2.0", "library >= 1.0"])
            write_mod(mods / "library_1.0.0.zip", "library", "1.0.0")
            write_mod(mods / "addon_1.0.0.zip", "addon", "1.0.0")

            first = call(
                workspace, "modsets", "plan", "solver", "--enable", "application", "--enable", "addon"
            )
            second = call(
                workspace, "modsets", "plan", "solver", "--enable", "addon", "--enable", "application"
            )
            self.assertEqual(first, second)
            self.assertEqual("2.0.0", next(item["version"] for item in first["desired_mods"] if item["name"] == "library"))
            self.assertTrue(next(item["virtual_package"] for item in first["desired_mods"] if item["name"] == "base"))
            self.assertTrue(first["local_artifacts_only"])
            self.assertFalse(first["portal_access"])
            self.assertEqual([], json_contract.validate(first, json_contract.load_schema(
                SCHEMA_ROOT / "factorio_modset_plan.v1.schema.json")))

            current = lock_text("solver", [("library", "1.0.0")])
            (mods / "modset-lock.v1.json").write_text(current, encoding="utf-8")
            shared = workspace / "modsets" / "solver.modset-lock.v1.json"
            shared.parent.mkdir(parents=True, exist_ok=True)
            shared.write_text(current, encoding="utf-8")
            locked = call(workspace, "modsets", "plan", "solver", "--enable", "application")
            self.assertEqual("1.0.0", next(item["version"] for item in locked["desired_mods"] if item["name"] == "library"))

    def test_missing_dependencies_and_all_budgets_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory(prefix="facman solver refusal ") as value:
            workspace = Path(value)
            instance = setup(workspace)
            write_mod(instance / "mods" / "needs_missing_1.0.0.zip", "needs_missing", "1.0.0", ["missing >= 1.0"])
            missing = call(workspace, "modsets", "plan", "solver", "--enable", "needs_missing", success=False)
            self.assertEqual("local_dependency_unavailable", missing["refusal"]["code"])
            budget = call(
                workspace, "modsets", "plan", "solver", "--enable", "needs_missing",
                "--max-packages", "1", success=False,
            )
            self.assertEqual("solver_budget_exceeded", budget["refusal"]["code"])

    def test_required_and_optional_cycles_terminate_and_incompatibilities_refuse(self) -> None:
        with tempfile.TemporaryDirectory(prefix="facman solver graph ") as value:
            workspace = Path(value)
            instance = setup(workspace)
            mods = instance / "mods"
            write_mod(mods / "cycle_a_1.0.0.zip", "cycle_a", "1.0.0", ["cycle_b >= 1.0"])
            write_mod(mods / "cycle_b_1.0.0.zip", "cycle_b", "1.0.0", ["cycle_a >= 1.0"])
            cycle = call(workspace, "modsets", "plan", "solver", "--enable", "cycle_a")
            self.assertEqual({"cycle_a", "cycle_b"}, {item["name"] for item in cycle["desired_mods"]})

            write_mod(mods / "optional_a_1.0.0.zip", "optional_a", "1.0.0", ["? optional_b >= 1.0"])
            write_mod(mods / "optional_b_1.0.0.zip", "optional_b", "1.0.0", ["? optional_a >= 1.0"])
            optional = call(
                workspace, "modsets", "plan", "solver", "--enable", "optional_a", "--enable", "optional_b"
            )
            self.assertIn("optional_a", {item["name"] for item in optional["desired_mods"]})
            self.assertIn("optional_b", {item["name"] for item in optional["desired_mods"]})

            write_mod(mods / "conflict_a_1.0.0.zip", "conflict_a", "1.0.0", ["! conflict_b"])
            write_mod(mods / "conflict_b_1.0.0.zip", "conflict_b", "1.0.0")
            conflict = call(
                workspace, "modsets", "plan", "solver", "--enable", "conflict_a", "--enable", "conflict_b",
                success=False,
            )
            self.assertEqual("local_dependency_unavailable", conflict["refusal"]["code"])

    def test_apply_and_rollback_restore_exact_state(self) -> None:
        with tempfile.TemporaryDirectory(prefix="facman solver apply ") as value:
            workspace = Path(value)
            instance = setup(workspace)
            mods = instance / "mods"
            write_mod(mods / "simple_1.0.0.zip", "simple", "1.0.0")
            original_mod_list = '{"mods":[{"name":"base","enabled":true}]}\n'
            (mods / "mod-list.json").write_text(original_mod_list, encoding="utf-8")

            applied = call(workspace, "modsets", "apply", "solver", "--enable", "simple")
            self.assertEqual("applied", applied["status"])
            self.assertIn("simple", (mods / "mod-list.json").read_text(encoding="utf-8"))
            self.assertTrue((mods / "modset-lock.v1.json").is_file())
            transaction_id = applied["plan_id"]
            rolled_back = call(workspace, "modsets", "rollback", "solver", transaction_id)
            self.assertEqual("rolled_back", rolled_back["status"])
            self.assertEqual(original_mod_list, (mods / "mod-list.json").read_text(encoding="utf-8"))
            self.assertFalse((mods / "modset-lock.v1.json").exists())
            self.assertFalse((workspace / "modsets" / "solver.modset-lock.v1.json").exists())
            self.assertEqual([], json_contract.validate(rolled_back, json_contract.load_schema(
                SCHEMA_ROOT / "factorio_modset_rollback.v1.schema.json")))

    def test_fault_after_first_commit_restores_original_state(self) -> None:
        with tempfile.TemporaryDirectory(prefix="facman solver fault ") as value:
            workspace = Path(value)
            instance = setup(workspace)
            mods = instance / "mods"
            write_mod(mods / "simple_1.0.0.zip", "simple", "1.0.0")
            original = '{"mods":[{"name":"base","enabled":true}]}\n'
            (mods / "mod-list.json").write_text(original, encoding="utf-8")
            environment = dict(os.environ)
            environment["FACMAN_MODSET_FAULT"] = "after_first_commit"
            refused = call(
                workspace, "modsets", "apply", "solver", "--enable", "simple", success=False, env=environment
            )
            self.assertEqual("modset_fault_injected", refused["refusal"]["code"])
            self.assertEqual(original, (mods / "mod-list.json").read_text(encoding="utf-8"))
            self.assertFalse((mods / "modset-lock.v1.json").exists())
            self.assertFalse((workspace / "modsets" / "solver.modset-lock.v1.json").exists())

    def test_rollback_fault_restores_applied_state_before_retry(self) -> None:
        with tempfile.TemporaryDirectory(prefix="facman solver rollback fault ") as value:
            workspace = Path(value)
            instance = setup(workspace)
            mods = instance / "mods"
            write_mod(mods / "simple_1.0.0.zip", "simple", "1.0.0")
            original = '{"mods":[{"name":"base","enabled":true}]}\n'
            (mods / "mod-list.json").write_text(original, encoding="utf-8")
            applied = call(workspace, "modsets", "apply", "solver", "--enable", "simple")
            applied_state = (mods / "mod-list.json").read_text(encoding="utf-8")
            environment = dict(os.environ)
            environment["FACMAN_MODSET_FAULT"] = "rollback_after_first_restore"
            refused = call(
                workspace, "modsets", "rollback", "solver", applied["plan_id"], success=False, env=environment
            )
            self.assertEqual("modset_fault_injected", refused["refusal"]["code"])
            self.assertEqual(applied_state, (mods / "mod-list.json").read_text(encoding="utf-8"))
            call(workspace, "modsets", "rollback", "solver", applied["plan_id"])
            self.assertEqual(original, (mods / "mod-list.json").read_text(encoding="utf-8"))

    def test_rollback_history_cannot_redirect_managed_targets(self) -> None:
        with tempfile.TemporaryDirectory(prefix="facman solver redirect ") as value:
            workspace = Path(value)
            instance = setup(workspace)
            mods = instance / "mods"
            write_mod(mods / "simple_1.0.0.zip", "simple", "1.0.0")
            applied = call(workspace, "modsets", "apply", "solver", "--enable", "simple")
            history = mods / ".facman-modset-history" / applied["plan_id"] / "activation.v1.json"
            document = json.loads(history.read_text(encoding="utf-8"))
            outside = workspace.parent / "redirected-mod-list.json"
            document["files"][0]["target"] = str(outside)
            history.write_text(json.dumps(document, separators=(",", ":")) + "\n", encoding="utf-8")
            refused = call(
                workspace, "modsets", "rollback", "solver", applied["plan_id"], success=False
            )
            self.assertEqual("modset_history_invalid", refused["refusal"]["code"])
            self.assertFalse(outside.exists())


if __name__ == "__main__":
    unittest.main()
