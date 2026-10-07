# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import json
import hashlib
import os
import tempfile
import threading
import time
import unittest
from pathlib import Path

import jsonschema
from referencing import Registry, Resource

from native_cli import ROOT, invoke_machine, invoke
from test_profiles_templates import create_instance, invoke_json, assert_schema
from test_save_index_retention import write_save
from tests.windows_junction import create_junction
from test_cli import canonical_json_digest


def workspace_bytes(workspace: Path) -> dict[str, bytes]:
    return {p.relative_to(workspace).as_posix(): p.read_bytes()
            for p in workspace.rglob("*") if p.is_file()}


def factorio_validator(name: str) -> jsonschema.Draft202012Validator:
    schemas = ROOT / "contracts/schema/factorio"
    resources = []
    for path in schemas.glob("*.schema.json"):
        schema = json.loads(path.read_text(encoding="utf-8"))
        resources.append((schema["$id"], Resource.from_contents(schema)))
    return jsonschema.Draft202012Validator(
        json.loads((schemas / name).read_text(encoding="utf-8")),
        registry=Registry().with_resources(resources))


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

    def test_preparation_preview_embeds_exact_owner_plans_without_effects(self) -> None:
        with tempfile.TemporaryDirectory(prefix="facman-preview-owner-") as value:
            workspace = Path(value)
            instance = create_instance(workspace)
            options = ("--audio", "disabled", "--window-mode", "fullscreen", "--arg", "--low-vram")
            invoke_json(workspace, "profiles", "apply", "main", "gui", *options)
            before = workspace_bytes(workspace)
            install_before = workspace_bytes(ROOT / "tests/fixtures/fake_factorio_install")
            readiness = invoke_json(workspace, "instances", "readiness", "main")
            preview = readiness["preparation_preview"]
            assert_schema(self, readiness, "factorio_instance_readiness.v1.schema.json")
            factorio_validator("factorio_instance_readiness.v1.schema.json").validate(readiness)
            validator = factorio_validator("factorio_preparation_preview.v1.schema.json")
            validator.validate(preview)
            with self.assertRaises(jsonschema.ValidationError):
                validator.validate({**preview, "apply": True})
            direct_profile = invoke_json(workspace, "profiles", "plan", "main", "gui", *options)
            self.assertEqual(direct_profile, preview["profile"]["report"])
            self.assertEqual(json.loads((instance / "instance-overrides.v1.json").read_text())["values"],
                             preview["profile"]["request"]["overrides"])
            self.assertEqual(hashlib.sha256((instance / "instance-overrides.v1.json").read_bytes()).hexdigest(),
                             preview["profile"]["overrides_sha256"])
            self.assertEqual(hashlib.sha256((instance / "instance.v1.json").read_bytes()).hexdigest(),
                             preview["manifest_sha256"])
            installation = preview["installation"]["report"]
            # Preserve exact current root/source and owner policy defaults.
            direct_install = invoke_json(workspace, "installs", "reconcile", "plan", "fixture",
                "--version", preview["required_version"], "--target", str(ROOT / "tests/fixtures/fake_factorio_install"))
            self.assertEqual(direct_install, installation)
            self.assertEqual("unavailable", preview["installation"]["provider_plan"])
            digest_core = dict(preview)
            digest = digest_core.pop("plan_digest")
            self.assertEqual(canonical_json_digest(digest_core), digest)
            self.assertEqual(readiness, invoke_json(workspace, "instances", "readiness", "main"))
            described = invoke_json(workspace, "instances", "describe", "main")
            self.assertEqual(readiness, described["instance_readiness"])
            factorio_validator("factorio_instance_view.v1.schema.json").validate(described)
            self.assertEqual(preview, self.query(workspace, "instances")["readiness"]["preparation_preview"])
            self.assertEqual([], preview["executed_effects"])
            self.assertIsNone(preview["expires_at"])
            self.assertEqual("query_only_point_in_time", preview["observation_scope"])
            self.assertFalse(preview["preparation_available"])
            self.assertFalse(preview["execution_available"])
            self.assertTrue(all(flag is False for flag in preview["operation_guarantees"].values()))
            for command in ("readiness", "describe"):
                code, stdout, stderr = invoke(["--workspace", str(workspace), "instances", command, "main"])
                self.assertEqual((code, stderr), (0, ""), stdout)
                self.assertIn("Preparation preview: partial; apply unavailable", stdout)
            self.assertEqual(before, workspace_bytes(workspace))
            self.assertEqual(install_before, workspace_bytes(ROOT / "tests/fixtures/fake_factorio_install"))

    def test_preparation_preview_preserves_selected_world_and_menu_never_inspects_it(self) -> None:
        with tempfile.TemporaryDirectory(prefix="facman-preview-world-") as value:
            workspace = Path(value)
            instance = create_instance(workspace)
            selected = instance / "saves/selected.zip"
            write_save(selected, b"selected world")
            options = ("--selection-mode", "load-save", "--selection", "selected.zip", "--arg", "--low-vram")
            invoke_json(workspace, "profiles", "apply", "main", "gui", *options)
            before = workspace_bytes(workspace)
            ready = invoke_json(workspace, "instances", "readiness", "main", "--intent", "load_save")
            preview = ready["preparation_preview"]
            factorio_validator("factorio_instance_readiness.v1.schema.json").validate(ready)
            factorio_validator("factorio_preparation_preview.v1.schema.json").validate(preview)
            described = invoke_json(workspace, "instances", "describe", "main", "--intent", "load_save")
            self.assertEqual(ready, described["instance_readiness"])
            factorio_validator("factorio_instance_view.v1.schema.json").validate(described)
            self.assertEqual(invoke_json(workspace, "profiles", "plan", "main", "gui", *options),
                             preview["profile"]["report"])
            self.assertEqual("selected.zip", preview["profile"]["report"]["settings"]["selection"])
            self.assertEqual(ready["selected_save"]["record"], preview["selected_world"]["record"])
            self.assertEqual(ready["selected_save"]["inspection_identity"], preview["selected_world"]["inspection_identity"])
            self.assertEqual("unclaimed", preview["selected_world"]["gameplay_compatibility"])
            self.assertEqual("observation_only", preview["selected_world"]["disposition"])
            self.assertEqual(before, workspace_bytes(workspace))
            old_menu = invoke_json(workspace, "instances", "readiness", "main")
            self.assertEqual("not_required", old_menu["preparation_preview"]["selected_world"]["disposition"])
            self.assertIsNone(old_menu["preparation_preview"]["selected_world"]["record"])
            selected.write_bytes(b"invalid archive")
            self.assertEqual(old_menu, invoke_json(workspace, "instances", "readiness", "main"))
            changed = invoke_json(workspace, "instances", "readiness", "main", "--intent", "load_save")
            self.assertNotEqual(preview["plan_digest"], changed["preparation_preview"]["plan_digest"])
            self.assertEqual("blocked", changed["preparation_preview"]["composition_state"])
            self.assertEqual("plan_unavailable", changed["preparation_preview"]["selected_world"]["disposition"])
            self.assertFalse(changed["execution_available"])

    def test_preparation_preview_absent_present_and_malformed_overrides_do_not_fallback(self) -> None:
        with tempfile.TemporaryDirectory(prefix="facman-preview-overrides-") as value:
            workspace = Path(value)
            instance = create_instance(workspace)
            absent = invoke_json(workspace, "instances", "readiness", "main")["preparation_preview"]
            self.assertFalse(absent["profile"]["overrides_present"])
            self.assertIsNone(absent["profile"]["overrides_sha256"])
            path = instance / "instance-overrides.v1.json"
            stored = {"schema": "factorio.instance_overrides.v1", "instance_id": "main", "profile_id": "gui", "values": {}}
            path.write_text(json.dumps(stored), encoding="utf-8")
            present = invoke_json(workspace, "instances", "readiness", "main")["preparation_preview"]
            self.assertTrue(present["profile"]["overrides_present"])
            self.assertNotEqual(absent["plan_digest"], present["plan_digest"])
            for malformed in ("{", json.dumps({**stored, "profile_id": "other"}),
                              json.dumps({**stored, "values": {"audio": False}}),
                              json.dumps({**stored, "values": {"unknown": "value"}}),
                              json.dumps({**stored, "values": {"additional_arguments": [1]}})):
                path.write_text(malformed, encoding="utf-8")
                before = workspace_bytes(workspace)
                preview = invoke_json(workspace, "instances", "readiness", "main")["preparation_preview"]
                self.assertEqual("refusal", preview["profile"]["disposition"])
                self.assertEqual("profile_overrides_invalid", preview["profile"]["refusal"])
                self.assertIsNone(preview["profile"]["report"])
                self.assertEqual("blocked", preview["composition_state"])
                self.assertEqual(before, workspace_bytes(workspace))
            path.unlink()
            manifest = instance / "instance.v1.json"
            document = json.loads(manifest.read_text())
            document["profile"] = "missing"
            manifest.write_text(json.dumps(document), encoding="utf-8")
            failed = invoke_json(workspace, "instances", "readiness", "main")["preparation_preview"]
            self.assertEqual("missing", failed["profile_id"])
            self.assertEqual("refusal", failed["profile"]["disposition"])
            self.assertIsNone(failed["profile"]["report"])

    def test_preparation_preview_dependency_changes_and_pending_recovery(self) -> None:
        with tempfile.TemporaryDirectory(prefix="facman-preview-dependencies-") as value:
            workspace = Path(value)
            instance = create_instance(workspace)
            invoke_json(workspace, "profiles", "create", "current")
            invoke_json(workspace, "profiles", "apply", "main", "current")
            for path in (instance / "instance.v1.json", workspace / "profiles/current/profile.v1.json",
                         instance / "instance-overrides.v1.json", workspace / "installs/refs/fixture.json"):
                old = invoke_json(workspace, "instances", "readiness", "main")
                path.write_bytes(path.read_bytes() + b"\n")
                before = workspace_bytes(workspace)
                changed = invoke_json(workspace, "instances", "readiness", "main")
                self.assertNotEqual(old["preparation_preview"]["plan_digest"], changed["preparation_preview"]["plan_digest"], str(path))
                self.assertNotEqual(old["readiness_digest"], changed["readiness_digest"])
                self.assertEqual(before, workspace_bytes(workspace))
            old = invoke_json(workspace, "instances", "readiness", "main")
            config = instance / "config/config.ini"
            config.write_bytes(config.read_bytes() + b"\n; changed observation\n")
            before = workspace_bytes(workspace)
            fresh = invoke_json(workspace, "instances", "readiness", "main")
            self.assertNotEqual(old["preparation_preview"]["plan_digest"], fresh["preparation_preview"]["plan_digest"])
            self.assertNotEqual(old["readiness_digest"], fresh["readiness_digest"])
            self.assertEqual(before, workspace_bytes(workspace))
            environment = os.environ.copy()
            environment["FACMAN_TEST_PROFILE_APPLY_EXIT_AFTER_JOURNAL"] = "1"
            code, _, _ = invoke(["--workspace", str(workspace), "profiles", "apply", "main", "current", "--json"], env=environment)
            self.assertEqual(85, code)
            before = workspace_bytes(workspace)
            for intent in ("menu", "load_save"):
                pending = invoke_json(workspace, "instances", "readiness", "main", "--intent", intent)
                self.assertEqual("pending", pending["preparation_preview"]["recovery_state"])
                self.assertEqual("blocked", pending["preparation_preview"]["composition_state"])
                self.assertEqual("recovery_required", pending["overall_state"])
                self.assertFalse(pending["preparation_available"])
            self.assertEqual(before, workspace_bytes(workspace))

    def test_preparation_preview_modset_and_association_are_observations(self) -> None:
        with tempfile.TemporaryDirectory(prefix="facman-preview-observations-") as value:
            workspace = Path(value)
            instance = create_instance(workspace)
            source = ROOT / "tests/fixtures/factorio_mods/valid_simple/simple_mod_1.0.0.zip"
            invoke_json(workspace, "mods", "import", str(source), "--instance", "main")
            invoke_json(workspace, "modsets", "lock", "main")
            old = invoke_json(workspace, "instances", "readiness", "main")
            mods = old["preparation_preview"]["modset"]
            self.assertEqual("observation_only", mods["disposition"])
            self.assertEqual(invoke_json(workspace, "modsets", "verify", "main"), mods["verification"])
            self.assertTrue(mods["artifact_identities"])
            artifact = instance / "mods/simple_mod_1.0.0.zip"
            self.assertTrue(any(hashlib.sha256(artifact.read_bytes()).hexdigest() in identity
                                for identity in mods["artifact_identities"]))
            artifact.write_bytes(artifact.read_bytes() + b"changed artifact")
            before = workspace_bytes(workspace)
            changed = invoke_json(workspace, "instances", "readiness", "main")
            self.assertEqual("plan_unavailable", changed["preparation_preview"]["modset"]["disposition"])
            self.assertNotEqual(old["preparation_preview"]["plan_digest"], changed["preparation_preview"]["plan_digest"])
            self.assertEqual(before, workspace_bytes(workspace))
            # Shared projection and local verifier consume distinct raw inputs.
            # Exercise each independently while the actual verifier remains refused.
            locked = changed
            for identity_key, lock_path in (
                ("local_lock_identity", instance / "mods/modset-lock.v1.json"),
                ("shared_lock_identity", workspace / "modsets/main.modset-lock.v1.json"),
            ):
                self.assertIn(hashlib.sha256(lock_path.read_bytes()).hexdigest(),
                              locked["preparation_preview"]["modset"][identity_key])
                previous = locked
                lock_path.write_bytes(lock_path.read_bytes() + b"\n")
                before = workspace_bytes(workspace)
                locked = invoke_json(workspace, "instances", "readiness", "main")
                self.assertNotEqual(previous["preparation_preview"]["plan_digest"], locked["preparation_preview"]["plan_digest"])
                self.assertIn(hashlib.sha256(lock_path.read_bytes()).hexdigest(),
                              locked["preparation_preview"]["modset"][identity_key])
                self.assertEqual(previous["preparation_preview"]["modset"]["verification"],
                                 locked["preparation_preview"]["modset"]["verification"])
                self.assertEqual(before, workspace_bytes(workspace))
            # This target stays inside the owned temporary tree but outside the
            # selected instance. A final-entry no-follow open alone is insufficient.
            outside = workspace / "outside-instance-mods"
            outside.mkdir()
            external_artifact = outside / "simple_mod_1.0.0.zip"
            external_artifact.write_bytes(b"external regular artifact must never be hashed by preview")
            external_sha = hashlib.sha256(external_artifact.read_bytes()).hexdigest()
            mods_root = instance / "mods"
            retained = workspace / "retained-instance-mods"
            owned_root = workspace.resolve(strict=True)
            self.assertTrue(all(path.resolve(strict=False).is_relative_to(owned_root)
                                for path in (mods_root, retained, outside)))
            self.assertFalse(retained.exists())
            mods_root.rename(retained)
            linked = False
            try:
                try:
                    mods_root.symlink_to(outside, target_is_directory=True)
                except OSError:
                    if os.name != "nt":
                        raise
                    create_junction(mods_root, outside)
                linked = True
            except OSError as error:
                self.skipTest(f"required_blocked: owned temporary linked-directory fixture unavailable: {error}")
            try:
                before = workspace_bytes(workspace)
                external_before = workspace_bytes(outside)
                unsafe_menu = invoke_json(workspace, "instances", "readiness", "main")
                unsafe_mods = unsafe_menu["preparation_preview"]["modset"]
                self.assertEqual("plan_unavailable", unsafe_mods["disposition"])
                self.assertTrue(any("unavailable:unsafe_artifact" in identity
                                    for identity in unsafe_mods["artifact_identities"]))
                self.assertNotIn(external_sha, json.dumps(unsafe_menu))
                refused_load = invoke_json(workspace, "instances", "readiness", "main",
                                           "--intent", "load_save", success=False)
                self.assertEqual("instance_selected_save_path_unsafe", refused_load["refusal"]["code"])
                self.assertNotIn(external_sha, json.dumps(refused_load))
                self.assertEqual(before, workspace_bytes(workspace))
                self.assertEqual(external_before, workspace_bytes(outside))
            finally:
                if linked:
                    if os.name == "nt":
                        mods_root.rmdir()
                    else:
                        mods_root.unlink()


        with tempfile.TemporaryDirectory(prefix="facman-preview-association-") as value:
            workspace = Path(value)
            instance = create_instance(workspace)
            write_save(instance / "saves/selected.zip", b"selected world")
            invoke_json(workspace, "profiles", "apply", "main", "gui", "--selection-mode", "load-save", "--selection", "selected.zip")
            invoke_json(workspace, "saves", "associate", "selected.zip", "--instance", "main")
            old = invoke_json(workspace, "instances", "readiness", "main", "--intent", "load_save")
            association = instance / "metadata/save-refs/selected.zip.save-ref.v1.json"
            association.write_bytes(association.read_bytes() + b"\n")
            before = workspace_bytes(workspace)
            changed = invoke_json(workspace, "instances", "readiness", "main", "--intent", "load_save")
            self.assertNotEqual(old["preparation_preview"]["plan_digest"], changed["preparation_preview"]["plan_digest"])
            self.assertEqual("unclaimed", changed["preparation_preview"]["selected_world"]["gameplay_compatibility"])
            self.assertEqual(before, workspace_bytes(workspace))

    def test_preparation_preview_refuses_concurrent_exact_override_changes_for_both_intents(self) -> None:
        # Public calls and an external atomic writer exercise the real stable reads.
        # No query-side pause, mutation hook or authority is introduced.
        for intent in ("menu", "load_save"):
            with self.subTest(intent=intent), tempfile.TemporaryDirectory(prefix="facman-preview-race-") as value:
                workspace = Path(value)
                instance = create_instance(workspace)
                path = instance / "instance-overrides.v1.json"
                stored = {"schema": "factorio.instance_overrides.v1", "instance_id": "main", "profile_id": "gui"}
                initial = {"selection_mode": "none", "audio": "enabled"}
                if intent == "load_save":
                    write_save(instance / "saves/selected.zip", b"selected world")
                    initial.update(selection_mode="load-save", selection="selected.zip")
                path.write_text(json.dumps({**stored, "values": initial}), encoding="utf-8")
                stop = threading.Event()
                active = threading.Event()
                failures: list[BaseException] = []
                def change_inputs() -> None:
                    stage = instance / "override-race.stage"
                    try:
                        index = 0
                        while not stop.is_set():
                            patch = {**initial, "audio": "disabled" if index % 2 else "enabled"}
                            stage.write_text(json.dumps({**stored, "values": patch}), encoding="utf-8")
                            try:
                                os.replace(stage, path)
                                active.set()
                            except PermissionError:
                                # Windows can momentarily deny replacing an open stable input.
                                pass
                            index += 1
                    except BaseException as error:
                        failures.append(error)
                    finally:
                        stage.unlink(missing_ok=True)
                worker = threading.Thread(target=change_inputs)
                worker.start()
                refused = False
                try:
                    self.assertTrue(active.wait(5), "external writer did not start")
                    for _ in range(24):
                        code, stdout, stderr = invoke(["--workspace", str(workspace), "instances", "readiness", "main",
                                                       "--intent", intent, "--json"])
                        document = json.loads(stdout or stderr)
                        if code:
                            self.assertEqual("instance_projection_inputs_changed", document["refusal"]["code"])
                            refused = True
                            break
                        self.assertFalse(document["execution_available"])
                        report = document["preparation_preview"]["profile"]["report"]
                        if report is not None:
                            self.assertEqual("selected.zip" if intent == "load_save" else None, report["settings"]["selection"])
                        else:
                            self.assertEqual("blocked", document["preparation_preview"]["composition_state"])
                finally:
                    stop.set()
                    worker.join(5)
                self.assertFalse(worker.is_alive())
                self.assertEqual([], failures)
                self.assertTrue(refused, "repeated concurrent changes were never detected")
                before = workspace_bytes(workspace)
                settled = invoke_json(workspace, "instances", "readiness", "main", "--intent", intent)
                self.assertEqual(settled, invoke_json(workspace, "instances", "readiness", "main", "--intent", intent))
                self.assertEqual(before, workspace_bytes(workspace))


if __name__ == "__main__":
    unittest.main()
