# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import json
import os
import tempfile
import threading
import time
import unittest
from pathlib import Path

import jsonschema

from native_cli import ROOT, invoke_machine
from test_profiles_templates import create_instance, invoke_json


def workspace_bytes(workspace: Path) -> dict[str, bytes]:
    return {p.relative_to(workspace).as_posix(): p.read_bytes()
            for p in workspace.rglob("*") if p.is_file()}


class PresentationProfilePreparationTests(unittest.TestCase):
    def query(self, workspace: Path, scope: str, search: str = "") -> dict:
        args = ["--workspace", str(workspace), "presentation", "query", scope,
                "--instance", "main"]
        if search:
            args.extend(["--search", search])
        code, stdout, stderr = invoke_machine([*args, "--json"])
        self.assertEqual((code, stderr), (0, ""), stdout)
        snapshot = json.loads(stdout)["payload"]
        schema = json.loads((ROOT / "contracts/schema/presentation/presentation_snapshot.v1.schema.json")
                            .read_text(encoding="utf-8"))
        jsonschema.Draft202012Validator(schema).validate(snapshot)
        return snapshot

    def select(self, workspace: Path, snapshot: dict, profile: str, identity: str,
               env: dict[str, str] | None = None) -> tuple[int, str, str]:
        return invoke_machine([
            "--workspace", str(workspace), "presentation", "action", "profile.select",
            "--scope", snapshot["page"]["scope"], "--instance", "main", "--profile", profile,
            "--expected-revision", snapshot["revision"], "--request-id", f"request-{identity}",
            "--idempotency-key", f"idempotency-{identity}", "--operation-id", f"operation-{identity}",
            "--attempt-id", f"attempt-{identity}", "--confirmation", "explicit", "--json",
        ], env=env)

    def test_replaced_unselected_profile_invalidates_both_ordinary_scopes(self) -> None:
        for scope in ("instances", "content"):
            with self.subTest(scope=scope), tempfile.TemporaryDirectory(prefix="facman-profile-snapshot-") as value:
                workspace = Path(value)
                instance = create_instance(workspace)
                invoke_json(workspace, "profiles", "create", "quiet", "--audio", "disabled")
                old = self.query(workspace, scope)
                profile = workspace / "profiles/quiet/profile.v1.json"
                changed = json.loads(profile.read_text(encoding="utf-8"))
                changed["settings"]["audio"] = "enabled"
                profile.write_text(json.dumps(changed) + "\n", encoding="utf-8")
                before = workspace_bytes(workspace)
                fresh = self.query(workspace, scope)
                self.assertNotEqual(old["revision"], fresh["revision"])
                self.assertEqual(before, workspace_bytes(workspace))
                code, stdout, stderr = self.select(workspace, old, "quiet", "stale")
                self.assertEqual((code, stderr), (1, ""), stdout)
                self.assertEqual("stale_snapshot_revision", json.loads(stdout)["error"]["code"])
                self.assertEqual(before, workspace_bytes(workspace))
                plans = fresh["dependency_identities"]["profile_preparation"]
                self.assertEqual(["gui", "quiet"], [p["profile_id"] for p in plans])
                expected = invoke_json(workspace, "profiles", "plan", "main", "quiet")["plan_sha256"]
                self.assertEqual(expected, plans[1]["plan_sha256"])
                code, stdout, stderr = self.select(workspace, fresh, "quiet", "fresh")
                self.assertEqual((code, stderr), (0, ""), stdout)
                self.assertEqual("completed", json.loads(stdout)["payload"]["outcome"])
                self.assertEqual("quiet", json.loads((instance / "instance.v1.json").read_text())["profile"])
                code, replay, stderr = self.select(workspace, fresh, "quiet", "fresh")
                self.assertEqual((code, stderr, replay), (0, "", stdout))

    def test_failed_profile_is_explicit_and_usable_siblings_remain_bound(self) -> None:
        with tempfile.TemporaryDirectory(prefix="facman-profile-refusal-") as value:
            workspace = Path(value)
            create_instance(workspace)
            invoke_json(workspace, "profiles", "create", "broken")
            (workspace / "profiles/broken/profile.v1.json").write_text("{}\n", encoding="utf-8")
            before = workspace_bytes(workspace)
            snapshot = self.query(workspace, "instances")
            plans = snapshot["dependency_identities"]["profile_preparation"]
            failed = next(p for p in plans if p["profile_id"] == "broken")
            self.assertIsNone(failed["plan_sha256"])
            self.assertTrue(failed["refusal"]["code"])
            self.assertEqual(before, workspace_bytes(workspace))
            code, stdout, stderr = self.select(workspace, snapshot, "broken", "failed")
            self.assertEqual((code, stderr), (1, ""), stdout)
            self.assertEqual(failed["refusal"]["code"], json.loads(stdout)["error"]["code"])
            self.assertEqual(before, workspace_bytes(workspace))
            code, stdout, stderr = self.select(workspace, snapshot, "gui", "sibling")
            self.assertEqual((code, stderr), (0, ""), stdout)
            self.query(workspace, "activity_recovery")

    def test_search_does_not_omit_selectable_profile_dependencies(self) -> None:
        with tempfile.TemporaryDirectory(prefix="facman-profile-search-") as value:
            workspace = Path(value)
            create_instance(workspace)
            invoke_json(workspace, "profiles", "create", "zzz")
            invoke_json(workspace, "profiles", "create", "aaa")
            before = workspace_bytes(workspace)
            first = self.query(workspace, "content", "gui")
            second = self.query(workspace, "content", "gui")
            self.assertEqual(first["revision"], second["revision"])
            self.assertEqual(["aaa", "gui", "zzz"], [p["profile_id"] for p in
                             first["dependency_identities"]["profile_preparation"]])
            self.assertEqual(before, workspace_bytes(workspace))

    def test_late_owner_change_is_recovery_required_and_replayable(self) -> None:
        with tempfile.TemporaryDirectory(prefix="facman-profile-semantic-recovery-") as value:
            workspace = Path(value)
            instance = create_instance(workspace)
            initial = invoke_json(workspace, "profiles", "apply", "main", "gui", "--audio", "disabled")
            invoke_json(workspace, "profiles", "create", "quiet", "--audio", "disabled")
            snapshot = self.query(workspace, "instances")
            originals = {name: (instance / name).read_bytes() for name in
                         ("instance.v1.json", "instance-overrides.v1.json")}
            environment = os.environ.copy()
            environment["FACMAN_TEST_PROFILE_BEFORE_PUBLICATION_PAUSE"] = "1"
            outcomes: list[tuple[int, str, str]] = []
            worker = threading.Thread(target=lambda: outcomes.append(
                self.select(workspace, snapshot, "quiet", "late", environment)))
            marker = instance / ".facman-test-profile-before-publication"
            release = instance / ".facman-test-profile-publication-release"
            worker.start()
            try:
                for _ in range(100):
                    if marker.is_file():
                        break
                    time.sleep(0.05)
                self.assertTrue(marker.is_file(), "owner did not reach publication boundary")
                profile = workspace / "profiles/quiet/profile.v1.json"
                changed = json.loads(profile.read_text(encoding="utf-8"))
                changed["settings"]["audio"] = "enabled"
                profile.write_text(json.dumps(changed) + "\n", encoding="utf-8")
                retained_profile = profile.read_bytes()
            finally:
                release.write_text("continue\n", encoding="utf-8")
                worker.join(timeout=10)
            self.assertFalse(worker.is_alive())
            self.assertEqual(1, len(outcomes))
            code, stdout, stderr = outcomes[0]
            self.assertEqual((code, stderr), (3, ""), stdout)
            payload = json.loads(stdout)["payload"]
            self.assertEqual("recovery_required", payload["outcome"])
            self.assertEqual("profile_transaction_recovery_required", payload["problems"][0]["code"])
            self.assertIn("inputs changed before publication", payload["problems"][0]["summary"])
            self.assertEqual(originals, {name: (instance / name).read_bytes() for name in originals})
            self.assertEqual(retained_profile, profile.read_bytes())
            journals = invoke_json(workspace, "workspace", "recovery", "inspect")["transactions"]
            self.assertEqual("complete", next(j["state"] for j in journals
                                             if j["transaction_id"] == initial["transaction_id"]))
            pending = [j for j in journals if j["command_id"] == "profiles.apply"
                       and j["transaction_id"] != initial["transaction_id"]]
            self.assertEqual(1, len(pending))
            self.assertEqual("recovery_required", pending[0]["state"])
            stages = list(instance.glob(f".profile*-{pending[0]['transaction_id']}.json"))
            self.assertEqual(2, len(stages))
            self.query(workspace, "activity_recovery")
            self.assertEqual(outcomes[0], self.select(workspace, snapshot, "quiet", "late"))
            recovered = invoke_json(workspace, "workspace", "recovery", "apply", pending[0]["transaction_id"])
            self.assertEqual("rolled_back", recovered["transactions"][0]["state"])
            self.assertEqual(originals, {name: (instance / name).read_bytes() for name in originals})
            self.assertEqual(retained_profile, profile.read_bytes())
            self.assertTrue(all(not stage.exists() for stage in stages))
            fresh = self.query(workspace, "instances")
            code, stdout, stderr = self.select(workspace, fresh, "quiet", "recovered")
            self.assertEqual((code, stderr), (0, ""), stdout)
            self.assertEqual("completed", json.loads(stdout)["payload"]["outcome"])


if __name__ == "__main__":
    unittest.main()
