# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import time
import unittest
import zipfile
from pathlib import Path

from native_cli import facman_executable, invoke
from test_instance_lifecycle import hold_configuration_lock
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


def snapshot(root: Path, excluded: Path | None = None) -> dict[str, bytes]:
    return {path.relative_to(root).as_posix(): path.read_bytes() for path in root.rglob("*")
            if path.is_file() and path != excluded}


def managed_state(workspace: Path) -> list[bytes | None]:
    return [path.read_bytes() if path.exists() else None for path in (
        workspace / "instances/solver/mods/mod-list.json",
        workspace / "instances/solver/mods/modset-lock.v1.json",
        workspace / "modsets/solver.modset-lock.v1.json",
    )]


class LocalModsetSolverTests(unittest.TestCase):
    def test_apply_refuses_selected_archive_change_at_publication_boundary(self) -> None:
        self.assert_publication_drift_refused("archive")

    def test_apply_preserves_external_managed_state_change_at_publication_boundary(self) -> None:
        for change in ("managed", "managed_remove", "shared_lock"):
            with self.subTest(change=change): self.assert_publication_drift_refused(change)

    def test_apply_preserves_unverified_publication_staging_and_history(self) -> None:
        for change in ("marker", "staged_payload", "unknown_child", "history_manifest", "history_backup"):
            with self.subTest(change=change): self.assert_publication_drift_refused(change)

    def test_apply_refuses_redirected_publication_stage_where_supported(self) -> None:
        for change in ("staged_symlink", "stage_redirect"):
            with self.subTest(change=change): self.assert_publication_drift_refused(change)

    def assert_publication_drift_refused(self, change: str) -> None:
        with tempfile.TemporaryDirectory(prefix="facman publication drift ") as value:
            workspace = Path(value)
            mods = setup(workspace) / "mods"
            archive = mods / "simple_1.0.0.zip"
            write_mod(archive, "simple", "1.0.0")
            if change in ("managed_remove", "history_backup"):
                (mods / "mod-list.json").write_bytes(b'{"mods":[]}\n')
            before = managed_state(workspace)
            environment = dict(os.environ, FACMAN_TEST_MODSET_APPLY_BEFORE_PUBLICATION_PAUSE="1")
            process = subprocess.Popen(
                [str(facman_executable()), "--workspace", str(workspace), "modsets", "apply",
                 "solver", "--enable", "simple", "--json"],
                cwd=ROOT, env=environment, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )
            try:
                deadline = time.monotonic() + 10
                stage = None
                while process.poll() is None and stage is None and time.monotonic() < deadline:
                    stage = next((path for path in mods.glob(".facman-modset-stage-*")
                                  if (path / ".facman-modset-apply-paused").is_file()), None)
                    time.sleep(0.01)
                self.assertIsNotNone(stage, "apply did not reach the publication boundary")
                history = mods / ".facman-modset-history"
                attempt = next(history.iterdir())
                unsafe = change in {"marker", "staged_payload", "unknown_child", "history_manifest", "history_backup", "staged_symlink", "stage_redirect"}
                if change == "archive": write_mod(archive, "simple", "1.0.0", ["base >= 2.0.0"])
                elif change == "managed": (mods / "mod-list.json").write_bytes(b'{"mods":[],"external_edit":"preserve"}\n')
                elif change == "managed_remove": (mods / "mod-list.json").unlink()
                elif change == "shared_lock":
                    external_lock = json.loads(lock_text("solver", []))
                    external_lock["external_edit"] = "preserve"
                    (workspace / "modsets/solver.modset-lock.v1.json").write_bytes((json.dumps(external_lock) + "\n").encode())
                elif change == "marker": (stage / ".facman-transaction-staging.v2.json").write_bytes(b"foreign marker\n")
                elif change == "staged_payload": (stage / "local-lock.json").write_bytes(b"external staged bytes\n")
                elif change == "unknown_child": (stage / "external.txt").write_bytes(b"preserve unknown content\n")
                elif change == "history_manifest": (attempt / "activation.v1.json").write_bytes(b"changed history\n")
                elif change == "history_backup": (attempt / "mod-list.before").write_bytes(b"changed backup\n")
                elif change in {"staged_symlink", "stage_redirect"}:
                    if change == "staged_symlink":
                        foreign = workspace / "external_staged_bytes.json"
                        foreign.write_bytes(b"preserve linked bytes\n")
                        link = stage / "local-lock.json"
                        link.unlink()
                    else:
                        foreign = stage.with_name(stage.name + "-retained")
                        stage.rename(foreign)
                        link = stage
                    try: link.symlink_to(foreign, target_is_directory=change == "stage_redirect")
                    except OSError as error:
                        if getattr(error, "winerror", None) == 1314 or error.errno in {1, 13, 95}:
                            self.skipTest("not_applicable: publication symlink creation unavailable on this host")
                        raise
                external_state = managed_state(workspace)
                external_archive = archive.read_bytes()
                staged_before = snapshot(stage)
                staged_before[".facman-modset-apply-release"] = b""
                history_before = snapshot(history)
                (stage / ".facman-modset-apply-release").touch()
                stdout, stderr = process.communicate(timeout=20)
                self.assertNotEqual(0, process.returncode, stdout + stderr)
                envelope = json.loads(stdout)
                refusal = envelope["payload"]["refusal"]
                expected = "transaction_recovery_required" if unsafe else "modset_archive_changed" if change == "archive" else "modset_external_drift"
                self.assertEqual(expected, refusal["code"])
                self.assertEqual(external_state, managed_state(workspace))
                self.assertEqual(external_archive, archive.read_bytes())
                if change == "archive": self.assertEqual(before, managed_state(workspace))
                if unsafe:
                    self.assertEqual(staged_before, snapshot(stage))
                    self.assertEqual(history_before, snapshot(history))
                    if change in {"staged_symlink", "stage_redirect"}: self.assertTrue(link.is_symlink())
                    if change == "staged_symlink": self.assertEqual(b"preserve linked bytes\n", foreign.read_bytes())
                    return
                retained = snapshot(history)
                journals = snapshot(workspace / "transactions")
                retained_stage = snapshot(stage)
                applied = call(workspace, "modsets", "apply", "solver", "--enable", "simple")
                call(workspace, "modsets", "verify", "solver")
                call(workspace, "modsets", "rollback", "solver", applied["transaction_id"])
                self.assertEqual(external_state, managed_state(workspace))
                self.assertEqual(retained, {key: value for key, value in snapshot(history).items() if key in retained})
                self.assertEqual(journals, {key: value for key, value in snapshot(workspace / "transactions").items() if key in journals})
                self.assertEqual(retained_stage, snapshot(stage))
            finally:
                if process.poll() is None:
                    process.kill()
                    process.communicate()

    def test_applied_selection_verifies_virtual_base_and_only_pinned_archives(self) -> None:
        with tempfile.TemporaryDirectory(prefix="facman selected verification ") as value:
            workspace = Path(value)
            mods = setup(workspace) / "mods"
            write_mod(mods / "library_1.0.0.zip", "library", "1.0.0")
            selected = mods / "library_2.0.0.zip"
            write_mod(selected, "library", "2.0.0")
            write_mod(mods / "application_1.0.0.zip", "application", "1.0.0", ["base >= 2.0", "library >= 1.0"])
            (mods / "unselected_1.0.0.zip").write_bytes(b"malformed unselected archive")
            call(workspace, "modsets", "apply", "solver", "--enable", "application")
            before = snapshot(workspace)
            verified = call(workspace, "modsets", "verify", "solver")
            self.assertEqual([], verified["problems"])
            self.assertEqual(before, snapshot(workspace))
            lock = mods / "modset-lock.v1.json"
            original = lock.read_bytes()
            for change in ("source", "version", "duplicate", "path", "malformed"):
                with self.subTest(change=change):
                    document = json.loads(original)
                    base = next(item for item in document["mods"] if item["name"] == "base")
                    if change == "source": base["source"] = "install-data:another-install"
                    elif change == "version": base["version"] = "99.0.0"
                    elif change == "duplicate": document["mods"].append(dict(base))
                    elif change == "path": document["mods"][0]["file_name"] = "../outside.zip"
                    lock.write_bytes(b"{}\n" if change == "malformed" else (json.dumps(document) + "\n").encode())
                    tampered = snapshot(workspace)
                    refused = call(workspace, "modsets", "verify", "solver", success=False)
                    self.assertEqual("mod_hash_mismatch", refused["refusal"]["code"])
                    self.assertEqual(tampered, snapshot(workspace))
                    lock.write_bytes(original)
            selected.write_bytes(selected.read_bytes() + b"changed archive bytes")
            tampered = snapshot(workspace)
            refused = call(workspace, "modsets", "verify", "solver", success=False)
            self.assertTrue(any("mismatch" in problem for problem in refused["problems"]))
            self.assertEqual(tampered, snapshot(workspace))

    def test_failed_apply_retry_preserves_attempts_and_has_its_own_rollback_id(self) -> None:
        for fault in ("after_backup", "after_first_commit"):
            with self.subTest(fault=fault), tempfile.TemporaryDirectory(prefix="facman retry ") as value:
                workspace = Path(value)
                mods = setup(workspace) / "mods"
                write_mod(mods / "simple_1.0.0.zip", "simple", "1.0.0")
                before = managed_state(workspace)
                planned = call(workspace, "modsets", "plan", "solver", "--enable", "simple")
                environment = dict(os.environ, FACMAN_MODSET_FAULT=fault)
                for _attempt in range(2):
                    refused = call(workspace, "modsets", "apply", "solver", "--enable", "simple", success=False, env=environment)
                    self.assertEqual("modset_fault_injected", refused["refusal"]["code"])
                    phrase = "fault injected after backup" if fault == "after_backup" else "fault injection after first commit"
                    self.assertIn(phrase, refused["refusal"]["detail"].lower())
                    self.assertEqual(before, managed_state(workspace))
                history = mods / ".facman-modset-history"
                retained = snapshot(history)
                journals = snapshot(workspace / "transactions")
                failed_journals = [json.loads(data) for data in journals.values()
                                   if json.loads(data).get("command_id") == "modsets.apply"]
                self.assertEqual(2, len(failed_journals))
                self.assertTrue(all(phrase.lower().replace("fault injected", "fault injection") in
                                    journal["error"].lower() for journal in failed_journals))
                stages = {path.name: snapshot(path) for path in mods.glob(".facman-modset-stage-*")}
                applied = call(workspace, "modsets", "apply", "solver", "--enable", "simple")
                self.assertEqual(planned["plan_id"], applied["plan_id"])
                self.assertNotEqual(applied["plan_id"], applied["transaction_id"])
                self.assertEqual([], json_contract.validate(applied, json_contract.load_schema(
                    SCHEMA_ROOT / "factorio_modset_plan.v1.schema.json")))
                for name, content in retained.items(): self.assertEqual(content, (history / name).read_bytes())
                for name, content in journals.items(): self.assertEqual(content, (workspace / "transactions" / name).read_bytes())
                for name, content in stages.items(): self.assertEqual(content, snapshot(mods / name))
                call(workspace, "modsets", "verify", "solver")
                call(workspace, "modsets", "rollback", "solver", applied["transaction_id"])
                self.assertEqual(before, managed_state(workspace))

    def test_retry_refuses_tampered_history_stage_and_active_journal(self) -> None:
        for change in ("backup", "plan", "target", "stage", "marker", "active", "workspace"):
            with self.subTest(change=change), tempfile.TemporaryDirectory(prefix="facman retry refusal ") as value:
                workspace = Path(value)
                mods = setup(workspace) / "mods"
                write_mod(mods / "simple_1.0.0.zip", "simple", "1.0.0")
                (mods / "mod-list.json").write_text('{"mods":[{"name":"base","enabled":true}]}\n', encoding="utf-8")
                before = managed_state(workspace)
                planned = call(workspace, "modsets", "plan", "solver", "--enable", "simple")
                call(workspace, "modsets", "apply", "solver", "--enable", "simple", success=False,
                     env=dict(os.environ, FACMAN_MODSET_FAULT="after_first_commit"))
                history = mods / ".facman-modset-history" / planned["plan_id"]
                stage = mods / (".facman-modset-stage-" + planned["plan_id"])
                manifest = history / "activation.v1.json"
                if change in ("plan", "target"):
                    document = json.loads(manifest.read_bytes())
                    if change == "plan": document["plan_id"] = "0" * 64
                    else: document["files"][0]["target"] = str(workspace / "foreign.json")
                    manifest.write_text(json.dumps(document) + "\n", encoding="utf-8")
                elif change == "backup": (history / "mod-list.before").write_bytes(b"wrong backup")
                elif change == "stage": (stage / "uncommitted.json").write_bytes(b"preserve me")
                elif change == "marker": (stage / ".facman-transaction-staging.v2.json").write_bytes(b"{}\n")
                else:
                    marker = json.loads((history / ".facman-transaction-staging.v2.json").read_bytes())
                    journal = workspace / "transactions" / (marker["transaction_id"] + ".transaction.v1.json")
                    document = json.loads(journal.read_bytes())
                    if change == "active": document["state"] = "committing"
                    else: document["workspace_id"] = "workspace-other"
                    journal.write_text(json.dumps(document) + "\n", encoding="utf-8")
                retained = snapshot(workspace)
                call(workspace, "modsets", "apply", "solver", "--enable", "simple", success=False)
                self.assertEqual(before, managed_state(workspace))
                self.assertEqual(retained, snapshot(workspace))

    def test_legacy_restored_recovery_journal_is_preserved_during_retry(self) -> None:
        with tempfile.TemporaryDirectory(prefix="facman legacy retry ") as value:
            workspace = Path(value)
            mods = setup(workspace) / "mods"
            write_mod(mods / "simple_1.0.0.zip", "simple", "1.0.0")
            before = managed_state(workspace)
            planned = call(workspace, "modsets", "plan", "solver", "--enable", "simple")
            call(workspace, "modsets", "apply", "solver", "--enable", "simple", success=False,
                 env=dict(os.environ, FACMAN_MODSET_FAULT="after_first_commit"))
            history = mods / ".facman-modset-history" / planned["plan_id"]
            stage = mods / (".facman-modset-stage-" + planned["plan_id"])
            manifest = history / "activation.v1.json"
            document = json.loads(manifest.read_bytes())
            del document["plan_id"]
            manifest.write_text(json.dumps(document) + "\n", encoding="utf-8")
            marker = json.loads((history / ".facman-transaction-staging.v2.json").read_bytes())
            journal = workspace / "transactions" / (marker["transaction_id"] + ".transaction.v1.json")
            document = json.loads(journal.read_bytes())
            document["state"] = "recovery_required"
            document["error"] = "fault injection after first commit"
            journal.write_text(json.dumps(document) + "\n", encoding="utf-8")
            retained = (snapshot(history), snapshot(stage), journal.read_bytes())
            applied = call(workspace, "modsets", "apply", "solver", "--enable", "simple")
            self.assertEqual(planned["plan_id"], applied["plan_id"])
            self.assertEqual(retained, (snapshot(history), snapshot(stage), journal.read_bytes()))
            call(workspace, "modsets", "verify", "solver")
            call(workspace, "modsets", "rollback", "solver", applied["transaction_id"])
            self.assertEqual(before, managed_state(workspace))

    def test_apply_and_rollback_refuse_the_existing_instance_configuration_lock(self) -> None:
        with tempfile.TemporaryDirectory(prefix="facman modset lock ") as value:
            workspace = Path(value)
            instance = setup(workspace)
            write_mod(instance / "mods/simple_1.0.0.zip", "simple", "1.0.0")
            applied = call(workspace, "modsets", "apply", "solver", "--enable", "simple")
            before = snapshot(workspace)
            marker = instance / "locks/configuration.write.lock"
            before_unlocked = snapshot(workspace, excluded=marker)
            with hold_configuration_lock(marker):
                for command in (("modsets", "apply", "solver", "--enable", "simple"),
                                ("modsets", "rollback", "solver", applied["transaction_id"])):
                    refused = call(workspace, *command, success=False)
                    self.assertEqual("instance_configuration_lock_contended", refused["refusal"]["code"])
                    self.assertEqual(before_unlocked, snapshot(workspace, excluded=marker))
            self.assertEqual(before, snapshot(workspace))
            call(workspace, "modsets", "rollback", "solver", applied["transaction_id"])

    def test_human_content_reports_show_owner_selection_and_diagnostics(self) -> None:
        with tempfile.TemporaryDirectory(prefix="facman content reports ") as value:
            workspace = Path(value)
            mods = setup(workspace) / "mods"
            write_mod(mods / "simple_1.0.0.zip", "simple", "1.0.0")
            before = snapshot(workspace)
            for command in (("mods", "list"), ("mods", "index"), ("modsets", "plan", "solver", "--enable", "simple"),
                            ("modsets", "diff", "solver", "--enable", "simple"), ("modsets", "explain", "solver", "--enable", "simple")):
                with self.subTest(command=command):
                    code, stdout, stderr = invoke(["--workspace", str(workspace), *command])
                    self.assertEqual(0, code, stderr)
                    self.assertIn("simple 1.0.0", stdout)
                    self.assertIn("base", stdout)
                    self.assertIn("install-data:fixture", stdout)
                    self.assertIn("Portal access: false", stdout)
                    self.assertIn("Mutation executed: false", stdout)
                    if command[0] == "modsets":
                        plan = call(workspace, *command)
                        self.assertIn(plan["plan_id"], stdout)
                        for explanation in plan["explanation"]: self.assertIn(explanation, stdout)
                    self.assertEqual(before, snapshot(workspace))

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
