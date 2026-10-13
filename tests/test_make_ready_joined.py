# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT
"""Ordinary preparation composition; fixtures do not qualify real game hosts."""
from __future__ import annotations

import hashlib
import copy
import ctypes
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

import test_configuration_preparation as missing
import test_configuration_reconciliation as existing
import test_make_ready_preparation as legacy
import test_tui_product as tui
from native_cli import ROOT, invoke_machine
from test_local_modset_solver import snapshot
from test_presentation_profile_preparation import factorio_validator
from tools.winforms_build import msbuild_executable


def file_identity(path: Path) -> str:
    if os.name != "nt":
        observed = path.stat()
        return f"{observed.st_dev}:{observed.st_ino}"
    from ctypes import wintypes

    class FileInformation(ctypes.Structure):
        _fields_ = [("attributes", wintypes.DWORD), ("creation", wintypes.FILETIME),
                    ("access", wintypes.FILETIME), ("write", wintypes.FILETIME),
                    ("volume_serial", wintypes.DWORD), ("size_high", wintypes.DWORD),
                    ("size_low", wintypes.DWORD), ("links", wintypes.DWORD),
                    ("index_high", wintypes.DWORD), ("index_low", wintypes.DWORD)]

    api = ctypes.WinDLL("kernel32", use_last_error=True)
    api.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                               ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    api.CreateFileW.restype = wintypes.HANDLE
    api.GetFileInformationByHandle.argtypes = [wintypes.HANDLE, ctypes.POINTER(FileInformation)]
    api.GetFileInformationByHandle.restype = wintypes.BOOL
    api.CloseHandle.argtypes = [wintypes.HANDLE]
    api.CloseHandle.restype = wintypes.BOOL
    # FILE_READ_ATTRIBUTES, all sharing, OPEN_EXISTING: observe the actual file
    # through its held handle without changing or adopting its contents.
    handle = api.CreateFileW(str(path), 0x80, 7, None, 3, 0, None)
    if handle == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        observed = FileInformation()
        if not api.GetFileInformationByHandle(handle, ctypes.byref(observed)):
            raise ctypes.WinError(ctypes.get_last_error())
        return f"{observed.volume_serial}:{(observed.index_high << 32) | observed.index_low}"
    finally:
        if not api.CloseHandle(handle):
            raise ctypes.WinError(ctypes.get_last_error())


@unittest.skipUnless(os.name == "nt" or sys.platform in ("linux", "darwin"),
                     "unsupported: preparation publication requires Windows, Linux or macOS")
class JoinedMakeReadyTests(unittest.TestCase):
    query = existing.ExistingConfigurationTests.query
    preserved_inputs = legacy.MakeReadyPreparationTests.preserved_inputs

    def arguments(self, workspace: Path, observation: dict, identity: str) -> list[str]:
        plan = observation["dependency_identities"]["joined_preparation"]["plan"]
        desired = plan["desired_state"]
        args = ["--workspace", str(workspace), "presentation", "action", "readiness.prepare_joined",
                "--scope", "instances", "--instance", "main", "--intent", plan["launch_intent"],
                "--installation", desired["installation_id"], "--profile", desired["profile_id"],
                "--expected-revision", observation["revision"], "--request-id", identity,
                "--idempotency-key", identity, "--operation-id", identity, "--attempt-id", identity,
                "--confirmation", "explicit", "--json"]
        if desired["selected_save"]:
            args.extend(["--save", desired["selected_save"]])
        return args

    def result(self, response: tuple[int, str, str], code: int = 0) -> dict:
        actual, output, error = response
        self.assertEqual((code, ""), (actual, error), output)
        result = json.loads(output)["payload"]
        factorio_validator("factorio_make_ready_joined_result.v1.schema.json").validate(result["action_payload"])
        return result

    def journals(self, workspace: Path) -> list[dict]:
        return [json.loads(path.read_bytes()) for path in
                (workspace / "transactions").glob("*.transaction.v1.json")]

    def assert_effects(self, workspace: Path, result: dict, commands: list[str]) -> None:
        components = result["action_payload"]["completed_components"]
        self.assertEqual(commands, [effect["owner_command"] for effect in components])
        records = self.journals(workspace)
        for effect in components:
            owner = next(record for record in records if record["transaction_id"] == effect["transaction_id"])
            self.assertEqual("complete", owner["state"])
            self.assertEqual(effect["owner_command"], owner["command_id"])
            context = json.loads(owner["operation_context"])
            self.assertEqual(result["operation"]["operation_id"], context["operation_id"])
            self.assertEqual(result["operation"]["attempt_id"], context["attempt_id"])
            target = Path(owner["target"])
            self.assertEqual(file_identity(target), owner["effect_file_identity"])
            expected = context.get("config_text", context.get("sidecar_text"))
            self.assertEqual(expected.encode(), target.read_bytes())
        payload = result["action_payload"]
        self.assertEqual(payload["plan"]["plan_sha256"], payload["plan_sha256"])
        self.assertFalse(payload["readiness_complete"])
        self.assertFalse(payload["execution_started"])
        self.assertFalse(payload["permit_issued"])

    def test_one_ordinary_request_prepares_routing_and_exact_world_with_independent_receipts(self) -> None:
        for kind in ("missing", "existing"):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory(prefix="joined-world-") as value:
                workspace = Path(value)
                if kind == "existing":
                    instance, _, expected = existing.ExistingConfigurationTests.prepare(self, workspace, "load_save", True, True)
                    identity = (instance / "config/config.ini").stat().st_ino
                else:
                    instance, expected = missing.ConfigurationPreparationTests.prepare(self, workspace, "load_save", True)
                    identity = None
                inputs = self.preserved_inputs(instance)
                installation = snapshot(workspace / "fixture-install")
                frozen = snapshot(workspace)
                initial = self.query(workspace, "instances", "load_save")
                time.sleep(1.05)  # Sidecar timestamps must not make a read-only plan unstable.
                second = self.query(workspace, "instances", "load_save")
                self.assertEqual(initial["revision"], second["revision"])
                self.assertEqual(frozen, snapshot(workspace))
                descriptor = next(a for a in initial["available_semantic_actions"] if a["action_id"] == "readiness.prepare_joined")
                self.assertEqual("primary", descriptor["role"])
                self.assertEqual(["selected_instance_id", "installation_id", "profile_id", "save"],
                                 [field["field_id"] for field in descriptor["input_fields"]])
                args = self.arguments(workspace, initial, "joined-world")
                result = self.result(invoke_machine(args))
                self.assert_effects(workspace, result, ["readiness.prepare_configuration", "readiness.prepare_selected_save"])
                self.assertEqual("completed", result["outcome"])
                self.assertFalse(result["action_payload"]["preparation_complete"])
                self.assertEqual("observe_readiness", result["action_payload"]["continuation"])
                ready = self.query(workspace, "instances", "load_save")["readiness"]
                self.assertEqual(ready, result["action_payload"]["readiness_observation"])
                self.assertEqual("degraded", ready["configuration_state"])
                self.assertEqual("already_prepared", ready["preparation_state"])
                self.assertEqual("degraded", next(d["state"] for d in ready["dimensions"] if d["id"] == "environment"))
                self.assertEqual("satisfied", ready["selected_save"]["state"])
                self.assertFalse(ready["execution_available"])
                self.assertIn("real_play_gate_not_passed", [b["code"] for b in ready["blockers"]])
                self.assertEqual(expected, (instance / "config/config.ini").read_bytes())
                if identity is not None:
                    self.assertEqual(identity, (instance / "config/config.ini").stat().st_ino)
                sidecar = json.loads((instance / "metadata/save-refs/selected.zip.save-ref.v1.json").read_bytes())
                self.assertEqual(hashlib.sha256((instance / "saves/selected.zip").read_bytes()).hexdigest(), sidecar["save_sha256"])
                self.assertEqual(inputs, self.preserved_inputs(instance))
                self.assertEqual(installation, snapshot(workspace / "fixture-install"))
                frozen = snapshot(workspace)
                self.assertEqual(result, self.result(invoke_machine(args)))
                self.assertEqual(frozen, snapshot(workspace))

    def test_menu_and_already_prepared_paths_follow_owner_observation(self) -> None:
        with tempfile.TemporaryDirectory(prefix="joined-menu-") as value:
            workspace = Path(value)
            instance, expected = missing.ConfigurationPreparationTests.prepare(self, workspace, "menu", False)
            self.assertFalse((instance / "instance-overrides.v1.json").exists())
            initial = self.query(workspace, "instances", "menu")
            result = self.result(invoke_machine(self.arguments(workspace, initial, "joined-menu")))
            self.assert_effects(workspace, result, ["readiness.prepare_configuration"])
            self.assertFalse(result["action_payload"]["preparation_complete"])
            self.assertEqual(expected, (instance / "config/config.ini").read_bytes())
            self.assertFalse((instance / "instance-overrides.v1.json").exists())
            initial = self.query(workspace, "instances", "menu")
            originals = snapshot(instance)
            result = self.result(invoke_machine(self.arguments(workspace, initial, "joined-already")))
            self.assert_effects(workspace, result, [])
            self.assertFalse(result["action_payload"]["preparation_complete"])
            self.assertEqual(originals, snapshot(instance))

    def test_wrong_desired_inputs_confirmation_and_stale_observation_refuse_before_effects(self) -> None:
        with tempfile.TemporaryDirectory(prefix="joined-refusal-") as value:
            workspace = Path(value)
            instance, _, _ = existing.ExistingConfigurationTests.prepare(self, workspace, "load_save")
            initial = self.query(workspace, "instances", "load_save")
            base = self.arguments(workspace, initial, "joined-refusal")
            for field, value in (("--installation", "other"), ("--profile", "other"), ("--save", "other.zip"), ("--confirmation", "")):
                with self.subTest(field=field):
                    args = base.copy()
                    position = args.index(field)
                    if value:
                        args[position + 1] = value
                    else:
                        del args[position:position + 2]
                    frozen = snapshot(workspace)
                    code, out, err = invoke_machine(args)
                    self.assertEqual((1, ""), (code, err), out)
                    self.assertEqual("refused_before_effects", json.loads(out)["payload"]["outcome"])
                    self.assertEqual(frozen, snapshot(workspace))
            settings = instance / "mods/mod-settings.dat"
            settings.write_bytes(b"changed after observation")
            frozen = snapshot(workspace)
            code, out, err = invoke_machine(base)
            self.assertEqual((1, ""), (code, err), out)
            self.assertEqual("stale_snapshot_revision", json.loads(out)["error"]["code"])
            self.assertEqual(frozen, snapshot(workspace))

    def test_missing_prerequisites_and_foreign_context_are_visible_and_preserved(self) -> None:
        for missing_input in ("installation", "content", "profile", "foreign-context", "legacy-routing"):
            with self.subTest(input=missing_input), tempfile.TemporaryDirectory(prefix="joined-prereq-") as value:
                workspace = Path(value)
                instance, _, _ = existing.ExistingConfigurationTests.prepare(self, workspace, "load_save")
                if missing_input == "installation":
                    (workspace / "fixture-install/bin/x64/factorio.exe.stub").unlink()
                elif missing_input == "content":
                    (instance / "mods/modset-lock.v1.json").write_bytes(b"{}\n")
                elif missing_input == "profile":
                    (instance / "instance-overrides.v1.json").write_bytes(b"{}\n")
                elif missing_input == "legacy-routing":
                    (instance / "config-path.cfg").write_bytes(b"foreign routing\n")
                else:
                    target = instance / "metadata/save-refs/selected.zip.save-ref.v1.json"
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(b"foreign preserved\n")
                frozen = snapshot(workspace)
                initial = self.query(workspace, "instances", "load_save")
                descriptor = next(a for a in initial["available_semantic_actions"] if a["action_id"] == "readiness.prepare_joined")
                self.assertEqual("refused", descriptor["availability"])
                self.assertIsNone(initial["dependency_identities"]["joined_preparation"]["plan"])
                self.assertEqual(frozen, snapshot(workspace))

    def paused(self, workspace: Path, args: list[str], mutation) -> tuple[dict, dict[str, bytes]]:
        instance = workspace / "instances/main"
        worker_results = []
        worker = threading.Thread(target=lambda: worker_results.append(invoke_machine(args,
            env=dict(os.environ, FACMAN_TEST_MAKE_READY_PAUSE_BEFORE_CONTEXT="1"))))
        worker.start()
        try:
            marker = instance / ".facman-test-make-ready-before-context"
            for _ in range(200):
                if marker.exists():
                    break
                time.sleep(0.025)
            self.assertTrue(marker.is_file(), "joined request did not checkpoint its first completed owner")
            mutation(instance)
            frozen = snapshot(workspace)
        finally:
            (instance / ".facman-test-make-ready-context-release").write_text("continue\n")
            worker.join(timeout=15)
        self.assertFalse(worker.is_alive())
        return self.result(worker_results[0], 3), frozen

    def test_unrelated_drift_and_foreign_targets_after_configuration_stop_with_visible_partial_effects(self) -> None:
        for changed in ("settings", "archive", "sidecar", "configuration"):
            with self.subTest(changed=changed), tempfile.TemporaryDirectory(prefix="joined-late-") as value:
                workspace = Path(value)
                instance, _, expected = existing.ExistingConfigurationTests.prepare(self, workspace, "load_save")
                args = self.arguments(workspace, self.query(workspace, "instances", "load_save"), "joined-late")
                paths = {"settings": "mods/mod-settings.dat", "archive": "saves/selected.zip",
                         "sidecar": "metadata/save-refs/selected.zip.save-ref.v1.json", "configuration": "config/config.ini"}
                def mutate(root: Path) -> None:
                    target = root / paths[changed]
                    target.parent.mkdir(parents=True, exist_ok=True)
                    if changed == "configuration":
                        original = target.read_bytes()
                        target.rename(root / ".facman-test-original-config")
                        target.write_bytes(original)  # Foreign same-byte object is not adopted.
                    else:
                        target.write_bytes(b"foreign changed input\n")
                result, _ = self.paused(workspace, args, mutate)
                self.assertEqual("recovery_required", result["outcome"])
                self.assertEqual(["readiness.prepare_configuration"], [c["owner_command"] for c in result["action_payload"]["completed_components"]])
                self.assertFalse(result["action_payload"]["preparation_complete"])
                self.assertEqual("inspect_domain_recovery" if changed == "configuration" else
                                 "fresh_request_after_input_correction", result["action_payload"]["continuation"])
                self.assertEqual(1, len([r for r in self.journals(workspace) if r["command_id"] == "readiness.prepare_configuration" and r["state"] == "complete"]))
                self.assertEqual([], [r for r in self.journals(workspace) if r["command_id"] == "readiness.prepare_selected_save"])
                if changed != "configuration":
                    self.assertEqual(expected, (instance / "config/config.ini").read_bytes())
                    self.assertEqual(b"foreign changed input\n", (instance / paths[changed]).read_bytes())
                else:
                    self.assertEqual(expected, (instance / "config/config.ini").read_bytes())
                    self.assertEqual(expected, (instance / ".facman-test-original-config").read_bytes())
                frozen = snapshot(workspace)
                self.assertEqual(result, self.result(invoke_machine(args), 3))
                self.assertEqual(frozen, snapshot(workspace))

    def test_concurrent_exact_request_reads_checkpoint_without_redispatch(self) -> None:
        with tempfile.TemporaryDirectory(prefix="joined-concurrent-") as value:
            workspace = Path(value)
            existing.ExistingConfigurationTests.prepare(self, workspace, "load_save")
            args = self.arguments(workspace, self.query(workspace, "instances", "load_save"), "joined-concurrent")
            def replay(_: Path) -> None:
                frozen = snapshot(workspace)
                unknown = self.result(invoke_machine(args), 4)
                self.assertEqual("outcome_unknown", unknown["outcome"])
                self.assertEqual("inspect_original_request", unknown["action_payload"]["continuation"])
                self.assert_effects(workspace, unknown, ["readiness.prepare_configuration"])
                self.assertEqual(frozen, snapshot(workspace))
                conflict = args.copy()
                conflict[conflict.index("--attempt-id") + 1] = "another"
                code, out, err = invoke_machine(conflict)
                self.assertEqual((1, ""), (code, err), out)
                self.assertEqual("idempotency_key_conflict", json.loads(out)["error"]["code"])
                self.assertEqual(frozen, snapshot(workspace))
            # The helper expects a stopped partial result; this request completes.
            worker_results = []
            worker = threading.Thread(target=lambda: worker_results.append(invoke_machine(args,
                env=dict(os.environ, FACMAN_TEST_MAKE_READY_PAUSE_BEFORE_CONTEXT="1"))))
            worker.start()
            instance = workspace / "instances/main"
            try:
                for _ in range(200):
                    if (instance / ".facman-test-make-ready-before-context").exists():
                        break
                    time.sleep(0.025)
                self.assertTrue((instance / ".facman-test-make-ready-before-context").is_file())
                replay(instance)
            finally:
                (instance / ".facman-test-make-ready-context-release").write_text("continue\n")
                worker.join(timeout=15)
            self.assertFalse(worker.is_alive())
            result = self.result(worker_results[0])
            self.assert_effects(workspace, result, ["readiness.prepare_configuration", "readiness.prepare_selected_save"])
            self.assertFalse(result["action_payload"]["preparation_complete"])

    def test_process_loss_retains_plan_and_completed_effect_without_replaying_or_rollback(self) -> None:
        for seam in ("after-configuration", "configuration-owner", "selected-owner"):
            with self.subTest(seam=seam), tempfile.TemporaryDirectory(prefix="joined-loss-") as value:
                workspace = Path(value)
                instance, _, expected = existing.ExistingConfigurationTests.prepare(self, workspace, "load_save")
                initial = self.query(workspace, "instances", "load_save")
                args = self.arguments(workspace, initial, "joined-loss")
                env = dict(os.environ)
                if seam == "after-configuration":
                    env["FACMAN_TEST_MAKE_READY_EXIT_AFTER_CONFIGURATION"] = "1"
                elif seam == "configuration-owner":
                    env["FACMAN_TEST_CONFIGURATION_EXIT"] = "rewrite_after_prefix"
                else:
                    env["FACMAN_TEST_SELECTED_CONTEXT_EXIT"] = "before_publication"
                code, out, err = invoke_machine(args, env=env)
                self.assertEqual((88 if seam == "after-configuration" else 74, ""), (code, err), out)
                frozen = snapshot(workspace)
                unknown = self.result(invoke_machine(args), 4)
                self.assertEqual("outcome_unknown", unknown["outcome"])
                self.assertEqual("inspect_original_request", unknown["action_payload"]["continuation"])
                self.assertEqual(initial["dependency_identities"]["joined_preparation"]["plan"], unknown["action_payload"]["plan"])
                self.assertEqual(0 if seam == "configuration-owner" else 1, len(unknown["action_payload"]["completed_components"]))
                self.assertEqual(frozen, snapshot(workspace))
                for journal in self.journals(workspace):
                    if journal["state"] != "complete":
                        code, recovered = missing.ConfigurationPreparationTests.recover(self, workspace, journal)
                        self.assertEqual(0, code, recovered)
                self.assertEqual(expected, (instance / "config/config.ini").read_bytes())
                frozen = snapshot(workspace)
                self.assertEqual(unknown, self.result(invoke_machine(args), 4))
                self.assertEqual(frozen, snapshot(workspace))
                fresh = self.query(workspace, "instances", "load_save")
                completed = self.result(invoke_machine(self.arguments(workspace, fresh, "joined-after-recovery")))
                self.assertEqual("completed", completed["outcome"])
                self.assertFalse(completed["action_payload"]["preparation_complete"])

    def test_known_partial_correction_uses_a_fresh_request_without_changing_prior_receipts(self) -> None:
        with tempfile.TemporaryDirectory(prefix="joined-fresh-request-") as value:
            workspace = Path(value)
            instance, _, _ = existing.ExistingConfigurationTests.prepare(self, workspace, "load_save")
            initial = self.query(workspace, "instances", "load_save")
            args = self.arguments(workspace, initial, "joined-known-partial")
            settings = instance / "mods/mod-settings.dat"
            original = settings.read_bytes() if settings.exists() else None
            result, _ = self.paused(workspace, args, lambda root: (root / "mods/mod-settings.dat").write_bytes(b"changed\n"))
            self.assert_effects(workspace, result, ["readiness.prepare_configuration"])
            self.assertEqual("fresh_request_after_input_correction", result["action_payload"]["continuation"])
            self.assertTrue(result["action_payload"]["completed_effects_verified"])
            self.assertTrue(result["action_payload"]["remaining_effects_blocked_before_effects"])
            receipt = workspace / ".facman/action-receipts-v2" / (hashlib.sha256(b"joined-known-partial").hexdigest() + ".v2.json")
            receipt_bytes = receipt.read_bytes()
            journal = workspace / "transactions" / (result["action_payload"]["completed_components"][0]["transaction_id"] + ".transaction.v1.json")
            journal_bytes = journal.read_bytes()
            if original is None:
                settings.unlink()
            else:
                settings.write_bytes(original)
            fresh = self.query(workspace, "instances", "load_save")
            continued = self.result(invoke_machine(self.arguments(workspace, fresh, "joined-new-request")))
            self.assert_effects(workspace, continued, ["readiness.prepare_selected_save"])
            self.assertEqual("observe_readiness", continued["action_payload"]["continuation"])
            self.assertEqual(receipt_bytes, receipt.read_bytes())
            self.assertEqual(journal_bytes, journal.read_bytes())

    def test_unverifiable_owner_result_retains_uncertainty_and_never_starts_another_effect(self) -> None:
        for owner in ("configuration", "selected_save"):
            with self.subTest(owner=owner), tempfile.TemporaryDirectory(prefix="joined-owner-result-") as value:
                workspace = Path(value)
                instance, _, expected = existing.ExistingConfigurationTests.prepare(self, workspace, "load_save")
                args = self.arguments(workspace, self.query(workspace, "instances", "load_save"), "joined-result-unknown")
                result = self.result(invoke_machine(args, env=dict(os.environ, FACMAN_TEST_MAKE_READY_OWNER_RESULT_UNKNOWN=owner)), 3)
                self.assertEqual("inspect_domain_recovery", result["action_payload"]["continuation"])
                self.assertFalse(result["action_payload"]["completed_effects_verified"])
                self.assertFalse(result["action_payload"]["remaining_effects_blocked_before_effects"])
                self.assertEqual(0 if owner == "configuration" else 1, len(result["action_payload"]["completed_components"]))
                self.assertEqual(expected, (instance / "config/config.ini").read_bytes())
                records = [r for r in self.journals(workspace) if r["command_id"].startswith("readiness.prepare_")]
                self.assertEqual(1 if owner == "configuration" else 2, len(records))
                self.assertTrue(all(r["state"] == "complete" for r in records))
                frozen = snapshot(workspace)
                self.assertEqual(result, self.result(invoke_machine(args), 3))
                self.assertEqual(frozen, snapshot(workspace))

    def test_failed_final_receipt_persistence_preserves_foreign_target_and_exposes_no_clearing_directive(self) -> None:
        with tempfile.TemporaryDirectory(prefix="joined-final-receipt-") as value:
            workspace = Path(value)
            instance, _, expected = existing.ExistingConfigurationTests.prepare(self, workspace, "load_save")
            args = self.arguments(workspace, self.query(workspace, "instances", "load_save"), "joined-final-receipt")
            results = []
            worker = threading.Thread(target=lambda: results.append(invoke_machine(args, env=dict(os.environ,
                FACMAN_TEST_MAKE_READY_PAUSE_BEFORE_CONTEXT="1", FACMAN_TEST_MAKE_READY_PAUSE_BEFORE_FINAL_RECEIPT="1"))))
            worker.start()
            def wait_marker(name: str) -> None:
                for _ in range(300):
                    if (instance / name).is_file():
                        break
                    time.sleep(0.025)
                self.assertTrue((instance / name).is_file(), name)
            try:
                wait_marker(".facman-test-make-ready-before-context")
                (instance / "mods/mod-settings.dat").write_bytes(b"changed\n")
                (instance / ".facman-test-make-ready-context-release").write_text("continue\n")
                wait_marker(".facman-test-make-ready-before-final-receipt")
                receipt = workspace / ".facman/action-receipts-v2" / (hashlib.sha256(b"joined-final-receipt").hexdigest() + ".v2.json")
                retained = receipt.with_suffix(".retained-test-receipt")
                original = receipt.read_bytes()
                receipt.rename(retained)
                receipt.mkdir()  # Actual wrong-type namespace target blocks final persistence.
            finally:
                (instance / ".facman-test-make-ready-context-release").write_text("continue\n")
                (instance / ".facman-test-make-ready-final-receipt-release").write_text("continue\n")
                worker.join(timeout=15)
            self.assertFalse(worker.is_alive())
            code, out, err = results[0]
            self.assertEqual((4, ""), (code, err), out)
            result = json.loads(out)["payload"]
            self.assertEqual("outcome_unknown", result["outcome"])
            self.assertIsNone(result["action_payload"])
            self.assertEqual("idempotency_receipt_finalization_failed", result["problems"][0]["code"])
            self.assertTrue(receipt.is_dir())
            self.assertEqual(original, retained.read_bytes())
            self.assertEqual(expected, (instance / "config/config.ini").read_bytes())
            self.assertFalse((instance / "metadata/save-refs/selected.zip.save-ref.v1.json").exists())
            pending = json.loads(json.loads(original)["result_json"])
            self.assertEqual("inspect_original_request", pending["action_payload"]["continuation"])
            self.assert_effects(workspace, pending, ["readiness.prepare_configuration"])

    def test_changed_effect_after_final_observation_cannot_manufacture_success(self) -> None:
        with tempfile.TemporaryDirectory(prefix="joined-final-effect-") as value:
            workspace = Path(value)
            instance, _, expected = existing.ExistingConfigurationTests.prepare(self, workspace, "load_save")
            args = self.arguments(workspace, self.query(workspace, "instances", "load_save"), "joined-final-effect")
            responses = []
            worker = threading.Thread(target=lambda: responses.append(invoke_machine(args, env=dict(os.environ,
                FACMAN_TEST_MAKE_READY_PAUSE_BEFORE_FINAL_RECEIPT="1"))))
            worker.start()
            try:
                for _ in range(300):
                    if (instance / ".facman-test-make-ready-before-final-receipt").is_file():
                        break
                    time.sleep(0.025)
                self.assertTrue((instance / ".facman-test-make-ready-before-final-receipt").is_file())
                target = instance / "config/config.ini"
                retained = instance / ".facman-test-verified-config"
                target.rename(retained)
                target.write_bytes(expected)
                foreign_identity = target.stat().st_ino
            finally:
                (instance / ".facman-test-make-ready-final-receipt-release").write_text("continue\n")
                worker.join(timeout=15)
            self.assertFalse(worker.is_alive())
            result = self.result(responses[0], 3)
            self.assertEqual("recovery_required", result["outcome"])
            self.assertEqual("inspect_domain_recovery", result["action_payload"]["continuation"])
            self.assertFalse(result["action_payload"]["completed_effects_verified"])
            self.assertIsNone(result["action_payload"]["readiness_observation"])
            self.assertEqual(2, len(result["action_payload"]["completed_components"]))
            records = [r for r in self.journals(workspace) if r["command_id"].startswith("readiness.prepare_")]
            self.assertEqual(2, len(records))
            self.assertTrue(all(r["state"] == "complete" for r in records))
            configuration = next(r for r in records if r["command_id"] == "readiness.prepare_configuration")
            self.assertEqual(file_identity(retained), configuration["effect_file_identity"])
            self.assertEqual(expected, target.read_bytes())
            self.assertEqual(expected, retained.read_bytes())
            self.assertEqual(foreign_identity, target.stat().st_ino)

    def test_ordinary_tui_dispatches_one_confirmed_request_for_both_components(self) -> None:
        executable = tui.tui_executable()
        self.assertIsNotNone(executable, "joined ordinary workflow requires the matching native TUI")
        with tempfile.TemporaryDirectory(prefix="joined-tui-") as value:
            workspace = Path(value)
            instance, expected = missing.ConfigurationPreparationTests.prepare(self, workspace, "load_save", True)
            observation = self.query(workspace, "instances", "load_save")
            index = next(i for i, a in enumerate(observation["available_semantic_actions"]) if a["action_id"] == "readiness.prepare_joined")
            result = subprocess.run([str(executable), "tui", "--workspace", str(workspace), "--ordinary", "--plain"],
                input="s\n2\n" + "tab\n" * index + "space\nspace\nq\n", cwd=ROOT,
                capture_output=True, text=True, timeout=45)
            self.assertEqual((0, ""), (result.returncode, result.stderr), result.stdout)
            self.assertIn("Confirm Make Ready with current settings", result.stdout)
            self.assertIn("review remaining readiness checks", result.stdout)
            receipts = [json.loads(p.read_bytes()) for p in (workspace / ".facman/action-receipts-v2").glob("*.v2.json")]
            receipt = next(r for r in receipts if r["action_id"] == "readiness.prepare_joined")
            outcome = json.loads(receipt["result_json"])
            self.assert_effects(workspace, outcome, ["readiness.prepare_configuration", "readiness.prepare_selected_save"])
            self.assertEqual("completed", outcome["outcome"])
            self.assertFalse(outcome["action_payload"]["preparation_complete"])
            self.assertEqual(expected, (instance / "config/config.ini").read_bytes())

    @unittest.skipUnless(os.name == "nt", "unsupported: WinForms requires Windows")
    def test_compiled_ordinary_gui_control_preserves_actual_preparation_receipt(self) -> None:
        with tempfile.TemporaryDirectory(prefix="joined-gui-") as value:
            root = Path(value)
            workspace = root / "workspace"
            existing.ExistingConfigurationTests.prepare(self, workspace, "load_save")
            scopes = ("launch_deck", "instances", "installations", "content", "saves", "activity_recovery", "settings_support")
            gallery = root / "gallery.json"
            gallery.write_text(json.dumps(dict(schema="facman.control_gallery_case.v1", state="blocked",
                variant="make-ready-current-settings", observed_at="2026-10-14T00:00:00Z",
                snapshots={scope: self.query(workspace, scope, "load_save") for scope in scopes})))
            observation = self.query(workspace, "instances", "load_save")
            response = invoke_machine(self.arguments(workspace, observation, "joined-gui"))
            self.result(response)
            receipt = root / "receipt.json"
            receipt.write_text(response[1])
            project = ROOT / "tests/winforms_control_gallery/FacMan.SelectedSave.Harness.csproj"
            build = subprocess.run([msbuild_executable(), str(project), "/m:2", "/nr:false",
                "/p:Configuration=Debug", "/p:Platform=x64", f"/p:OutputPath={root / 'bin'}{os.sep}",
                f"/p:IntermediateOutputPath={root / 'obj'}{os.sep}", f"/p:BaseIntermediateOutputPath={root / 'obj'}{os.sep}"],
                cwd=ROOT, capture_output=True, text=True, timeout=180)
            self.assertEqual(0, build.returncode, build.stdout + build.stderr)
            frozen = snapshot(workspace)
            run = subprocess.run([str(root / "bin/FacMan.SelectedSave.Harness.exe"), str(gallery), str(receipt), "make-ready-complete"],
                cwd=root, capture_output=True, text=True, timeout=60)
            self.assertEqual(0, run.returncode, run.stdout + run.stderr)
            self.assertEqual(1, run.stdout.count("PASS "))
            self.assertEqual(frozen, snapshot(workspace))

            partial_workspace = root / "known-partial"
            existing.ExistingConfigurationTests.prepare(self, partial_workspace, "load_save")
            partial_args = self.arguments(partial_workspace, self.query(partial_workspace, "instances", "load_save"), "joined-gui-partial")
            partial, _ = self.paused(partial_workspace, partial_args,
                lambda instance: (instance / "mods/mod-settings.dat").write_bytes(b"changed\n"))
            self.assert_effects(partial_workspace, partial, ["readiness.prepare_configuration"])
            self.assertEqual("fresh_request_after_input_correction", partial["action_payload"]["continuation"])
            code, output, error = invoke_machine(partial_args)
            self.assertEqual((3, ""), (code, error), output)
            envelope = json.loads(output)
            original_receipt = partial_workspace / ".facman/action-receipts-v2" / (hashlib.sha256(b"joined-gui-partial").hexdigest() + ".v2.json")
            original_input = json.loads(json.loads(original_receipt.read_bytes())["request_json"])
            cases = []
            def case(name: str, change=None, change_input=None, expected=False, exit_code=3) -> None:
                modified = copy.deepcopy(envelope)
                inputs = copy.deepcopy(original_input)
                if change:
                    change(modified)
                if change_input:
                    change_input(inputs)
                cases.append(dict(name=name, envelope=json.dumps(modified), input=inputs,
                                  exit_code=exit_code, expected_clear=expected))
            case("actual-known-partial", expected=True)
            def unknown(value: dict) -> None:
                value["operation"]["outcome"] = "outcome_unknown"
                value["payload"]["outcome"] = "outcome_unknown"
                value["payload"]["operation"]["outcome"] = "outcome_unknown"
            case("pending-even-with-forged-fresh-directive", unknown, exit_code=4)
            def failed_finalization(value: dict) -> None:
                unknown(value)
                value["payload"]["action_payload"] = None
            case("failed-final-persistence", failed_finalization, exit_code=4)
            case("domain-owner-unknown", lambda v: v["payload"]["action_payload"].update(
                continuation="inspect_domain_recovery", completed_effects_verified=False, remaining_effects_blocked_before_effects=False))
            case("mismatched-semantic-request", lambda v: v["payload"].update(request_id="another-request"))
            case("mismatched-semantic-operation", lambda v: v["payload"]["operation"].update(operation_id="another-operation"))
            case("mismatched-attempt", lambda v: v["payload"]["operation"].update(attempt_id="another-attempt"))
            case("mismatched-desired-profile", change_input=lambda v: v.update(profile_id="another-profile"))
            case("missing-effect-proof", lambda v: v["payload"]["action_payload"].pop("completed_effects_verified"))
            case("malformed-effect-proof", lambda v: v["payload"]["action_payload"].update(completed_effects_verified="true"))
            case("unproven-refusal", lambda v: v["payload"]["action_payload"].update(remaining_effects_blocked_before_effects=False))
            case("unrecognized-result-field", lambda v: v["payload"]["action_payload"].update(extra_clearing_authority=True))
            case("mismatched-completed-owner", lambda v: v["payload"]["action_payload"]["completed_components"][0].update(transaction_id="foreign-transaction"))
            case("duplicated-owner", lambda v: v["payload"]["action_payload"]["completed_components"].append(
                copy.deepcopy(v["payload"]["action_payload"]["completed_components"][0])))
            case("execution-authority-invented", lambda v: v["payload"]["action_payload"].update(permit_issued=True))
            case("legacy-recovery-blocking-preserved", lambda v: v["payload"].update(action_id="readiness.prepare"))
            case("wrong-snapshot-scope", lambda v: v["payload"]["replacement_snapshot"]["page"].update(scope="content"))
            case("foreign-owner-target", lambda v: v["payload"]["action_payload"]["completed_components"][0]["owner_result"].update(target="foreign/config.ini"))
            case("foreign-reviewed-target", lambda v: v["payload"]["action_payload"]["plan"]["configuration_plan"].update(target="foreign/config.ini"))
            def device_targets(value: dict, prefix: str) -> None:
                payload = value["payload"]["action_payload"]
                target = prefix + payload["plan"]["configuration_plan"]["target"]
                payload["plan"]["configuration_plan"]["target"] = target
                payload["completed_components"][0]["owner_result"]["target"] = target
            case("unexpected-device-targets", lambda v: device_targets(v, "\\\\?\\"))
            case("unexpected-forward-slash-device-targets", lambda v: device_targets(v, "//?/"))
            corpus = root / "continuations.json"
            corpus.write_text(json.dumps(dict(request_id="joined-gui-partial", operation_id="joined-gui-partial",
                                             attempt_id="joined-gui-partial", cases=cases)))
            frozen = snapshot(partial_workspace)
            run = subprocess.run([str(root / "bin/FacMan.SelectedSave.Harness.exe"), "make-ready-continuation", str(corpus)],
                cwd=root, capture_output=True, text=True, timeout=60)
            self.assertEqual(0, run.returncode, run.stdout + run.stderr)
            self.assertIn(f"PASS {len(cases)}", run.stdout)
            self.assertEqual(frozen, snapshot(partial_workspace))
