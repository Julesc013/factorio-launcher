# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT
"""Existing-instance version maintenance through ordinary Content actions."""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path

import test_make_ready_joined as joined
import test_readiness_content_activation as activation
from native_cli import ROOT, facman_executable, invoke_machine
from test_local_modset_solver import call, snapshot, write_mod


class ContentMaintenanceTests(unittest.TestCase):
    query = joined.JoinedMakeReadyTests.query

    def prepare(self, workspace: Path) -> Path:
        instance = activation.ContentActivationReadinessTests.prepare(self, workspace)
        write_mod(instance / "mods/other_1.0.0.zip", "other", "1.0.0")
        call(workspace, "modsets", "apply", "main", "--enable", "simple", "--enable", "other")
        observation = self.query(workspace, "instances", "load_save")
        args = joined.JoinedMakeReadyTests.arguments(self, workspace, observation, "maintenance-initial-ready")
        code, output, error = invoke_machine(args)
        self.assertEqual((0, ""), (code, error), output)
        self.assertEqual("completed", json.loads(output)["payload"]["outcome"])
        write_mod(instance / "mods/simple_2.0.0.zip", "simple", "2.0.0")
        (instance / "mods/foreign-user-data.txt").write_bytes(b"preserve unrelated content\x00\xff\n")
        (instance / "mods/mod-settings.dat").write_bytes(b"\x00\xffbinary startup settings\r\n")
        return instance

    def args(self, workspace: Path, action: str, identity: str, *inputs: str,
             observation: dict | None = None, confirm: bool = True) -> list[str]:
        observed = observation or self.query(workspace, "content", "load_save")
        args = ["--workspace", str(workspace), "presentation", "action", action,
                "--scope", "content", "--instance", "main", "--intent", "load_save",
                "--expected-revision", observed["revision"], "--request-id", identity, *inputs, "--json"]
        if action != "modsets.plan":
            args += ["--idempotency-key", identity, "--operation-id", identity, "--attempt-id", identity]
            if confirm:
                args += ["--confirmation", "explicit"]
        return args

    def result(self, args: list[str], code: int = 0) -> dict:
        actual, output, error = invoke_machine(args)
        self.assertEqual((code, ""), (actual, error), output)
        return json.loads(output)["payload"]

    @staticmethod
    def managed(workspace: Path) -> dict[str, bytes]:
        return {str(p.relative_to(workspace)): p.read_bytes() for p in (
            workspace / "instances/main/mods/mod-list.json",
            workspace / "instances/main/mods/modset-lock.v1.json",
            workspace / "modsets/main.modset-lock.v1.json")}

    @staticmethod
    def protected(instance: Path) -> dict[str, tuple[bytes, str]]:
        return {p.relative_to(instance).as_posix(): (p.read_bytes(), joined.file_identity(p))
                for p in instance.rglob("*") if p.is_file() and
                p.relative_to(instance).as_posix() not in ("mods/mod-list.json", "mods/modset-lock.v1.json") and
                not any(part.startswith((".facman-modset-", ".facman-configuration-")) for part in p.parts) and
                "locks" not in p.relative_to(instance).parts}

    @staticmethod
    def choices(observation: dict, action: str, field: str) -> list[str]:
        descriptor = next(a for a in observation["available_semantic_actions"] if a["action_id"] == action)
        return next(f["choices"] for f in descriptor["input_fields"] if f["field_id"] == field)

    def assert_selection(self, payload: dict, version: str) -> None:
        self.assertEqual({"base", "other", "simple"}, {m["name"] for m in payload["desired_mods"]})
        self.assertEqual([version], [m["version"] for m in payload["desired_mods"] if m["name"] == "simple"])

    def test_exact_version_preview_apply_replay_history_rollback_preserves_original(self) -> None:
        with tempfile.TemporaryDirectory(prefix="content-maintenance-") as value:
            workspace = Path(value)
            instance = self.prepare(workspace)
            original, protected = self.managed(workspace), self.protected(instance)
            observed = self.query(workspace, "content", "load_save")
            choices = self.choices(observed, "modsets.plan", "mod_identity")
            self.assertEqual(choices, self.choices(observed, "modsets.apply", "mod_identity"))
            self.assertIn("simple", choices)
            self.assertIn("simple@1.0.0", choices)
            self.assertIn("simple@2.0.0", choices)
            self.assertNotIn("base@2.0.77", choices)
            frozen = snapshot(workspace)
            preview = self.result(self.args(workspace, "modsets.plan", "preview-v2", "--mod", "simple@2.0.0"))
            self.assert_selection(preview["action_payload"], "2.0.0")
            self.assertEqual([dict(action="change_version", name="simple", from_version="1.0.0", to_version="2.0.0")],
                             preview["action_payload"]["changes"])
            self.assertEqual(frozen, snapshot(workspace))
            legacy = self.result(self.args(workspace, "modsets.plan", "preview-name", "--mod", "simple"))
            self.assertEqual(["1.0.0"], [m["version"] for m in legacy["action_payload"]["desired_mods"] if m["name"] == "simple"])
            soft = call(workspace, "modsets", "plan", "main", "--enable", "simple", "--enable", "other", "--prefer", "simple=2.0.0")
            self.assert_selection(soft, "1.0.0")
            args = self.args(workspace, "modsets.apply", "apply-v2", "--mod", "simple@2.0.0", confirm=False)
            code, output, error = invoke_machine(args)
            self.assertEqual((1, ""), (code, error), output)
            self.assertEqual("semantic_action_effect_confirmation_required", json.loads(output)["error"]["code"])
            self.assertEqual(frozen, snapshot(workspace))
            args += ["--confirmation", "explicit"]
            applied = self.result(args)
            self.assertEqual("completed", applied["outcome"])
            self.assert_selection(applied["action_payload"], "2.0.0")
            self.assertEqual(preview["action_payload"]["plan_id"], applied["action_payload"]["plan_id"])
            self.assertEqual([], call(workspace, "modsets", "verify", "main")["problems"])
            self.assertEqual(protected, self.protected(instance))
            frozen = snapshot(workspace)
            self.assertEqual(applied, self.result(args))
            self.assertEqual(frozen, snapshot(workspace))
            conflict = args.copy()
            conflict[conflict.index("--mod") + 1] = "simple@1.0.0"
            refused = self.result(conflict, code=1)
            self.assertEqual("idempotency_key_conflict", refused["problems"][0]["code"])
            self.assertEqual(frozen, snapshot(workspace))
            transaction = applied["action_payload"]["transaction_id"]
            history = instance / "mods/.facman-modset-history" / transaction
            retained = snapshot(history)
            rollback = self.query(workspace, "content", "load_save")
            self.assertIn(transaction, self.choices(rollback, "modsets.rollback", "transaction_id"))
            rollback_args = self.args(workspace, "modsets.rollback", "rollback-v2", "--transaction", transaction, confirm=False)
            self.result(rollback_args, code=1)
            self.assertEqual(frozen, snapshot(workspace))
            rolled = self.result(rollback_args + ["--confirmation", "explicit"])
            self.assertEqual("rolled_back", rolled["action_payload"]["status"])
            self.assertEqual(original, self.managed(workspace))
            self.assertEqual(protected, self.protected(instance))
            self.assertEqual(retained, {name: (history / name).read_bytes() for name in retained})
            self.assertEqual(frozen["instances/main/mods/modset-lock.v1.json"],
                             (history / "local-lock.applied").read_bytes())
            self.assertEqual([], call(workspace, "modsets", "verify", "main")["problems"])
            self.assertTrue((instance / "mods/simple_2.0.0.zip").exists())
            exported = workspace / "after-rollback.zip"
            call(workspace, "modsets", "export", "main", str(exported))
            with zipfile.ZipFile(exported) as archive:
                self.assertEqual(original[str(Path("instances/main/mods/modset-lock.v1.json"))], archive.read("modset-lock.v1.json"))
                self.assertEqual(original[str(Path("instances/main/mods/mod-list.json"))], archive.read("mods/mod-list.json"))
                self.assertEqual((instance / "mods/mod-settings.dat").read_bytes(), archive.read("mods/mod-settings.dat"))
                self.assertIn("mods/simple_1.0.0.zip", archive.namelist())
                self.assertIn("mods/other_1.0.0.zip", archive.namelist())
                self.assertNotIn("mods/simple_2.0.0.zip", archive.namelist())

    def test_exact_version_refuses_stale_conflicting_and_other_instance_material(self) -> None:
        for kind in ("stale", "dependency", "other-instance"):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory(prefix="content-maintenance-refusal-") as value:
                workspace = Path(value)
                instance = self.prepare(workspace)
                observed = self.query(workspace, "content", "load_save")
                if kind == "stale":
                    with zipfile.ZipFile(instance / "mods/simple_2.0.0.zip", "a") as archive:
                        archive.comment = b"same metadata, replaced artifact"
                elif kind == "dependency":
                    write_mod(instance / "mods/simple_2.0.0.zip", "simple", "2.0.0", ["base >= 2.0", "! other"])
                else:
                    call(workspace, "instances", "create", "Elsewhere", "--id", "elsewhere", "--install", "fixture")
                    (instance / "mods/simple_2.0.0.zip").rename(workspace / "instances/elsewhere/mods/simple_2.0.0.zip")
                current = self.query(workspace, "content", "load_save")
                if kind == "other-instance":
                    self.assertNotIn("simple@2.0.0", self.choices(current, "modsets.apply", "mod_identity"))
                args = self.args(workspace, "modsets.apply", "refuse-" + kind, "--mod", "simple@2.0.0",
                                 observation=observed if kind == "stale" else current)
                managed, protected = self.managed(workspace), self.protected(instance)
                code, output, error = invoke_machine(args)
                self.assertEqual("", error, output)
                document = json.loads(output)
                if kind == "stale":
                    self.assertEqual(1, code, output)
                    self.assertEqual("stale_snapshot_revision", document["error"]["code"])
                else:
                    self.assertEqual(1, code, output)
                    self.assertEqual("refused_before_effects", document["payload"]["outcome"])
                    self.assertEqual("local_dependency_unavailable" if kind == "dependency" else "modset_exact_selection_unavailable",
                                     document["payload"]["problems"][0]["code"])
                self.assertEqual(managed, self.managed(workspace))
                self.assertEqual(protected, self.protected(instance))

    def test_other_instance_archives_never_replace_selected_physical_identity(self) -> None:
        for kind in ("identical", "invalid-filename", "same-instance-invalid", "different-bytes"):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory(prefix="content-maintenance-duplicate-") as value:
                workspace = Path(value)
                instance = self.prepare(workspace)
                call(workspace, "instances", "create", "Earlier", "--id", "aaa", "--install", "fixture")
                if kind == "same-instance-invalid":
                    shutil.copyfile(instance / "mods/simple_2.0.0.zip", instance / "mods/invalid_2.0.0.zip")
                for name in ("simple_1.0.0.zip", "simple_2.0.0.zip", "other_1.0.0.zip"):
                    destination = workspace / "instances/aaa/mods" / ("invalid_2.0.0.zip" if kind == "invalid-filename" and name == "simple_2.0.0.zip" else name)
                    shutil.copyfile(instance / "mods" / name, destination)
                    if kind == "different-bytes" and name == "simple_2.0.0.zip":
                        with zipfile.ZipFile(destination, "a") as archive:
                            archive.comment = b"same name and version; different source archive"
                observation = self.query(workspace, "content", "load_save")
                self.assertIn("simple@2.0.0", self.choices(observation, "modsets.apply", "mod_identity"))
                before = snapshot(workspace / "instances/aaa")
                applied = self.result(self.args(workspace, "modsets.apply", "duplicate-apply", "--mod", "simple@2.0.0"))
                self.assert_selection(applied["action_payload"], "2.0.0")
                selected = next(m for m in applied["action_payload"]["desired_mods"] if m["name"] == "simple")
                self.assertEqual(hashlib.sha256((instance / "mods/simple_2.0.0.zip").read_bytes()).hexdigest(), selected["sha256"])
                self.assertEqual([], call(workspace, "modsets", "verify", "main")["problems"])
                self.assertEqual(before, snapshot(workspace / "instances/aaa"))

    def test_foreign_applied_state_refuses_rollback_and_retains_both_versions(self) -> None:
        with tempfile.TemporaryDirectory(prefix="content-maintenance-current-state-") as value:
            workspace = Path(value)
            instance = self.prepare(workspace)
            original, protected = self.managed(workspace), self.protected(instance)
            applied = self.result(self.args(workspace, "modsets.apply", "before-foreign-edit", "--mod", "simple@2.0.0"))
            transaction = applied["action_payload"]["transaction_id"]
            history = instance / "mods/.facman-modset-history" / transaction
            retained = snapshot(history)
            activation = instance / "mods/mod-list.json"
            after = activation.read_bytes()
            activation.write_bytes(after + b"\n")
            foreign = self.managed(workspace)
            refusal = self.result(self.args(workspace, "modsets.rollback", "foreign-rollback", "--transaction", transaction), code=1)
            self.assertEqual("modset_external_drift", refusal["problems"][0]["code"])
            self.assertEqual(foreign, self.managed(workspace))
            self.assertEqual(retained, snapshot(history))
            self.assertEqual(protected, self.protected(instance))
            activation.write_bytes(after)
            self.result(self.args(workspace, "modsets.rollback", "corrected-rollback", "--transaction", transaction))
            self.assertEqual(original, self.managed(workspace))
            self.assertEqual(protected, self.protected(instance))
            self.assertEqual([], call(workspace, "modsets", "verify", "main")["problems"])

    def tui(self, workspace: Path, action: str, tail: str) -> subprocess.CompletedProcess[str]:
        observation = self.query(workspace, "content", "load_save")
        index = next(i for i, a in enumerate(observation["available_semantic_actions"]) if a["action_id"] == action)
        run = subprocess.run([str(facman_executable()), "tui", "--transport", "process", "--cli-path", str(facman_executable()),
            "--workspace", str(workspace), "--ordinary", "--plain"],
            input="s\n4\n" + "tab\n" * index + tail + "q\n", cwd=ROOT, capture_output=True, text=True, timeout=45)
        self.assertEqual((0, ""), (run.returncode, run.stderr), run.stdout)
        return run

    def test_ordinary_tui_selects_previews_cancels_updates_and_rolls_back_exact_history(self) -> None:
        with tempfile.TemporaryDirectory(prefix="content-maintenance-tui-") as value:
            workspace = Path(value)
            instance = self.prepare(workspace)
            original, protected = self.managed(workspace), self.protected(instance)
            frozen = snapshot(workspace)
            preview = self.tui(workspace, "modsets.plan", "space\nmod_identity=simple@2.0.0\nspace\n")
            self.assertIn("simple@2.0.0", preview.stdout)
            self.assertIn("simple: 1.0.0 -> 2.0.0", preview.stdout)
            self.assertIn("completed", preview.stdout.lower())
            self.assertEqual(frozen, snapshot(workspace))
            cancelled = self.tui(workspace, "modsets.apply", "space\nmod_identity=simple@2.0.0\nspace\nesc\n")
            self.assertIn("Confirm Apply instance modset", cancelled.stdout)
            self.assertIn("Cancellation requested", cancelled.stdout)
            self.assertEqual(frozen, snapshot(workspace))
            applied = self.tui(workspace, "modsets.apply", "space\nmod_identity=simple@2.0.0\nspace\nspace\n")
            self.assertIn("completed", applied.stdout.lower())
            receipts = [json.loads(p.read_bytes()) for p in (workspace / ".facman/action-receipts-v2").glob("*.v2.json")]
            result = next(json.loads(r["result_json"]) for r in receipts if r["action_id"] == "modsets.apply")
            self.assert_selection(result["action_payload"], "2.0.0")
            self.assertEqual([], call(workspace, "modsets", "verify", "main")["problems"])
            transaction = result["action_payload"]["transaction_id"]
            frozen = snapshot(workspace)
            observed = self.query(workspace, "content", "load_save")
            rollback = next(a for a in observed["available_semantic_actions"] if a["action_id"] == "modsets.rollback")
            default = next(f["default"] for f in rollback["input_fields"] if f["field_id"] == "transaction_id")
            # A valid default already arms confirmation; changing it requires a fresh review.
            reviewed = "space\ntransaction_id=" + transaction + "\n" + ("space\n" if default != transaction else "")
            cancelled = self.tui(workspace, "modsets.rollback", reviewed + "esc\n")
            self.assertIn("Confirm Roll back instance modset", cancelled.stdout)
            self.assertIn("Cancellation requested", cancelled.stdout)
            self.assertEqual(frozen, snapshot(workspace))
            rolled = self.tui(workspace, "modsets.rollback", reviewed + "space\n")
            self.assertIn("Confirm Roll back instance modset", rolled.stdout)
            self.assertIn("completed", rolled.stdout.lower())
            self.assertEqual(original, self.managed(workspace))
            self.assertEqual(protected, self.protected(instance))
            self.assertEqual([], call(workspace, "modsets", "verify", "main")["problems"])


if __name__ == "__main__":
    unittest.main()
