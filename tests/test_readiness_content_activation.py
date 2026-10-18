# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT
"""Activation readiness uses the existing content owner without changing lock verification."""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

import test_make_ready_joined as joined
from native_cli import invoke_machine
from test_local_modset_solver import call, snapshot, write_mod
from tests.windows_junction import create_junction


class ContentActivationReadinessTests(unittest.TestCase):
    query = joined.JoinedMakeReadyTests.query
    arguments = joined.JoinedMakeReadyTests.arguments
    result = joined.JoinedMakeReadyTests.result

    def prepare(self, workspace: Path) -> Path:
        return joined.missing.ConfigurationPreparationTests.prepare(self, workspace, "load_save", True)[0]

    def assert_blocked(self, workspace: Path, pending_joined: bool = False) -> dict:
        before = snapshot(workspace)
        observation = self.query(workspace, "instances", "load_save")
        self.assertEqual("verification_failed", observation["readiness"]["preparation_preview"]["modset"]["status"])
        descriptor = next(a for a in observation["available_semantic_actions"] if a["action_id"] == "readiness.prepare_joined")
        self.assertEqual("available" if pending_joined else "refused", descriptor["availability"])
        plan = observation["dependency_identities"]["joined_preparation"]["plan"]
        if pending_joined:
            self.assertEqual("factorio.make_ready_joined_plan.v2", plan["schema"])
        else:
            self.assertIsNone(plan)
        self.assertEqual(before, snapshot(workspace))
        return observation

    def test_activation_drift_refuses_readiness_but_preserves_package_only_verify(self) -> None:
        for kind in ("missing", "disabled", "base-disabled", "unexpected", "duplicate", "missing-flag",
                     "nonbool", "unsafe-name", "invalid-json", "nonobject", "empty", "oversized", "hardlink"):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory(prefix="activation-refusal-") as value:
                workspace = Path(value)
                instance = self.prepare(workspace)
                path = instance / "mods/mod-list.json"
                document = json.loads(path.read_bytes())
                if kind == "missing":
                    path.unlink()
                elif kind in ("disabled", "base-disabled"):
                    next(m for m in document["mods"] if m["name"] == ("simple" if kind == "disabled" else "base"))["enabled"] = False
                elif kind == "unexpected":
                    document["mods"].append(dict(name="unlocked", enabled=True))
                elif kind == "duplicate":
                    document["mods"].append(dict(name="simple", enabled=False))
                elif kind == "missing-flag":
                    document["mods"][0].pop("enabled")
                elif kind == "nonbool":
                    document["mods"][0]["enabled"] = "true"
                elif kind == "unsafe-name":
                    document["mods"].append(dict(name="../foreign", enabled=False))
                elif kind == "invalid-json":
                    path.write_bytes(b"foreign malformed content\n")
                elif kind == "nonobject":
                    document["mods"].append("base")
                elif kind == "empty":
                    document["mods"] = []
                elif kind == "oversized":
                    path.write_bytes(b" " * (16 * 1024 * 1024 + 1))
                elif kind == "hardlink":
                    os.link(path, workspace / "mod-list-alias.json")
                if kind not in ("missing", "invalid-json", "oversized", "hardlink"):
                    path.write_text(json.dumps(document) + "\n", encoding="utf-8")
                self.assertEqual([], call(workspace, "modsets", "verify", "main")["problems"])
                self.assert_blocked(workspace, kind in ("missing", "disabled", "base-disabled", "empty"))

    def test_confirmed_content_apply_restores_locked_selection_then_joined_prepares(self) -> None:
        for kind in ("missing", "disabled"):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory(prefix="activation-apply-") as value:
                workspace = Path(value)
                instance = self.prepare(workspace)
                # A newer unselected local artifact must not replace the lock's version.
                write_mod(instance / "mods/simple_2.0.0.zip", "simple", "2.0.0")
                path = instance / "mods/mod-list.json"
                expected = path.read_bytes()
                if kind == "missing":
                    path.unlink()
                else:
                    path.write_text('{"mods":[{"name":"base","enabled":true},{"name":"simple","enabled":false}]}\n', encoding="utf-8")
                locks = {p: p.read_bytes() for p in (instance / "mods/modset-lock.v1.json", workspace / "modsets/main.modset-lock.v1.json")}
                preserved = {p: p.read_bytes() for p in instance.rglob("*") if p.is_file() and
                             (p.suffix == ".zip" or p.name in ("instance-overrides.v1.json", "mod-settings.dat"))}
                self.assert_blocked(workspace, True)
                content = self.query(workspace, "content", "load_save")
                args = ["--workspace", str(workspace), "presentation", "action", "modsets.apply",
                        "--scope", "content", "--instance", "main", "--intent", "load_save", "--mod", "simple",
                        "--expected-revision", content["revision"], "--request-id", "activate",
                        "--idempotency-key", "activate", "--operation-id", "activate", "--attempt-id", "activate", "--json"]
                before = snapshot(workspace)
                code, output, error = invoke_machine(args)
                self.assertEqual((1, ""), (code, error), output)
                self.assertEqual(before, snapshot(workspace))
                args.extend(["--confirmation", "explicit"])
                response = invoke_machine(args)
                self.assertEqual((0, ""), (response[0], response[2]), response[1])
                result = json.loads(response[1])["payload"]
                self.assertEqual("completed", result["outcome"])
                self.assertEqual("applied", result["action_payload"]["status"])
                self.assertEqual(expected, path.read_bytes())
                self.assertEqual(locks, {p: p.read_bytes() for p in locks})
                self.assertEqual(preserved, {p: p.read_bytes() for p in preserved})
                before = snapshot(workspace)
                self.assertEqual(response, invoke_machine(args))
                self.assertEqual(before, snapshot(workspace))
                observation = self.query(workspace, "instances", "load_save")
                self.assertEqual("locked_verified", observation["readiness"]["preparation_preview"]["modset"]["status"])
                prepared = self.result(invoke_machine(self.arguments(workspace, observation, "joined-after-content")))
                self.assertEqual("completed", prepared["outcome"])
                self.assertEqual(["readiness.prepare_configuration", "readiness.prepare_selected_save"],
                                 [c["owner_command"] for c in prepared["action_payload"]["completed_components"]])
                self.assertFalse(prepared["action_payload"]["execution_started"])
                self.assertFalse(prepared["action_payload"]["permit_issued"])

    def test_semantic_equivalence_still_binds_exact_activation_bytes_for_stale_requests(self) -> None:
        with tempfile.TemporaryDirectory(prefix="activation-stale-") as value:
            workspace = Path(value)
            instance = self.prepare(workspace)
            initial = self.query(workspace, "instances", "load_save")
            path = instance / "mods/mod-list.json"
            document = json.loads(path.read_bytes())
            document["mods"].reverse()
            document["mods"].append(dict(name="unused", enabled=False, version="1.0.0"))
            document["unknown_factorio_metadata"] = "preserved"
            path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
            before = snapshot(workspace)
            current = self.query(workspace, "instances", "load_save")
            self.assertEqual("locked_verified", current["readiness"]["preparation_preview"]["modset"]["status"])
            self.assertNotEqual(initial["revision"], current["revision"])
            identities = current["readiness"]["preparation_preview"]["modset"]["artifact_identities"]
            self.assertTrue(any("mod-list.json:" in identity for identity in identities))
            dependency = next(d for d in current["readiness"]["dependency_identities"]
                              if d["kind"] == "modset_artifact" and d["identity"].startswith("mod-list.json:"))
            self.assertEqual("observed", dependency["state"])
            code, output, error = invoke_machine(self.arguments(workspace, initial, "activation-stale"))
            self.assertEqual((1, ""), (code, error), output)
            self.assertEqual("stale_snapshot_revision", json.loads(output)["error"]["code"])
            self.assertEqual(before, snapshot(workspace))

    def test_large_valid_activation_still_binds_exact_bytes(self) -> None:
        with tempfile.TemporaryDirectory(prefix="activation-large-") as value:
            workspace = Path(value)
            instance = self.prepare(workspace)
            path = instance / "mods/mod-list.json"
            original = path.read_bytes()
            path.write_bytes(original + b" " * (9 * 1024 * 1024))
            initial = self.query(workspace, "instances", "load_save")
            self.assertEqual("locked_verified", initial["readiness"]["preparation_preview"]["modset"]["status"])
            path.write_bytes(original + b"\n" + b" " * (9 * 1024 * 1024 - 1))
            before = snapshot(workspace)
            current = self.query(workspace, "instances", "load_save")
            self.assertEqual("locked_verified", current["readiness"]["preparation_preview"]["modset"]["status"])
            self.assertNotEqual(initial["revision"], current["revision"])
            code, output, error = invoke_machine(["--workspace", str(workspace), "presentation", "action",
                "readiness.refresh", "--scope", "instances", "--instance", "main", "--intent", "load_save",
                "--expected-revision", initial["revision"], "--request-id", "activation-large-stale",
                "--idempotency-key", "activation-large-stale", "--json"])
            self.assertEqual((1, ""), (code, error), output)
            self.assertEqual("stale_snapshot_revision", json.loads(output)["error"]["code"])
            self.assertEqual(before, snapshot(workspace))

    def test_shared_lock_disagreement_and_linked_mod_list_are_observed_without_adoption(self) -> None:
        for kind in ("shared-lock", "linked-file", "linked-directory"):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory(prefix="activation-unsafe-") as value:
                workspace = Path(value)
                instance = self.prepare(workspace)
                path = instance / "mods/mod-list.json"
                if kind == "shared-lock":
                    shared = workspace / "modsets/main.modset-lock.v1.json"
                    shared.write_bytes(shared.read_bytes() + b"\n")
                    self.assert_blocked(workspace)
                else:
                    target = workspace / "foreign-activation"
                    if kind == "linked-file":
                        target.write_bytes(path.read_bytes())
                        path.unlink()
                        try:
                            path.symlink_to(target)
                        except OSError as error:
                            self.skipTest(f"unsupported: file symlink unavailable: {error}")
                    else:
                        (instance / "mods").rename(target)
                        if os.name == "nt":
                            create_junction(instance / "mods", target)
                        else:
                            (instance / "mods").symlink_to(target, target_is_directory=True)
                    before = snapshot(workspace)
                    code, output, error = invoke_machine(["--workspace", str(workspace), "presentation", "query", "instances", "--instance", "main", "--intent", "load_save", "--json"])
                    self.assertEqual("", error, output)
                    if code == 0:
                        observation = json.loads(output)["payload"]
                        if observation["readiness"] is None:
                            report = observation["dependency_identities"]["joined_preparation"]
                            self.assertIsNone(report["plan"])
                            self.assertEqual("instance_selected_save_path_unsafe", report["refusal"]["code"])
                        else:
                            self.assertEqual("verification_failed", observation["readiness"]["preparation_preview"]["modset"]["status"])
                    else:
                        self.assertIn("unsafe", json.loads(output)["error"]["code"])
                    self.assertEqual(before, snapshot(workspace))

    def test_builtin_only_activation_and_linked_ancestor_fail_closed(self) -> None:
        for kind in ("missing", "base-disabled", "linked-directory"):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory(prefix="activation-builtin-") as value:
                workspace = Path(value)
                instance, _ = joined.missing.fixtures.ReadinessBuiltinContentTests.prepare(self, workspace)
                healthy = self.query(workspace, "instances", "menu")
                self.assertEqual("locked_verified", healthy["readiness"]["preparation_preview"]["modset"]["status"])
                path = instance / "mods/mod-list.json"
                if kind == "missing":
                    path.unlink()
                elif kind == "base-disabled":
                    path.write_text('{"mods":[{"name":"base","enabled":false}]}\n', encoding="utf-8")
                else:
                    target = workspace / "foreign-mods"
                    (instance / "mods").rename(target)
                    if os.name == "nt":
                        create_junction(instance / "mods", target)
                    else:
                        (instance / "mods").symlink_to(target, target_is_directory=True)
                before = snapshot(workspace)
                observation = self.query(workspace, "instances", "menu")
                self.assertEqual("verification_failed", observation["readiness"]["preparation_preview"]["modset"]["status"])
                descriptor = next(a for a in observation["available_semantic_actions"] if a["action_id"] == "readiness.prepare_joined")
                self.assertEqual("refused" if kind == "linked-directory" else "available", descriptor["availability"])
                self.assertEqual(before, snapshot(workspace))


if __name__ == "__main__":
    unittest.main()
