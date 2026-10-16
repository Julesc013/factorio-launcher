# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT
from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

from native_cli import invoke_machine
from test_local_modset_solver import call, snapshot
from test_make_ready_joined import PausedAction, file_identity
from test_save_index_retention import write_save
import test_selected_save_preparation as selected
from test_presentation_profile_preparation import factorio_validator

PUBLICATION_SUPPORTED = selected.PUBLICATION_SUPPORTED


def read_pause_marker(path: Path) -> bytes:
    if os.name != "nt": return path.read_bytes()
    import ctypes
    import msvcrt
    from ctypes import wintypes

    api = ctypes.WinDLL("kernel32", use_last_error=True)
    api.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                               ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    api.CreateFileW.restype = wintypes.HANDLE
    api.CloseHandle.argtypes = [wintypes.HANDLE]
    api.CloseHandle.restype = wintypes.BOOL
    # The CRT maps denied access and sharing to EACCES. Preserve the real error
    # so only ERROR_SHARING_VIOLATION can retry the marker publication gap.
    handle = api.CreateFileW(str(path), 0x80000000, 7, None, 3, 0x200000, None)
    if handle == ctypes.c_void_p(-1).value: raise ctypes.WinError(ctypes.get_last_error())
    try: descriptor = msvcrt.open_osfhandle(int(handle), os.O_RDONLY | os.O_BINARY)
    except BaseException:
        api.CloseHandle(handle)
        raise
    with os.fdopen(descriptor, "rb") as stream: return stream.read(2)


@unittest.skipUnless(PUBLICATION_SUPPORTED, "unsupported: selected-context owner requires Windows, Linux or macOS")
class SelectedContextRefreshTests(unittest.TestCase):
    prepare = selected.SelectedSavePreparationTests.prepare
    query = selected.SelectedSavePreparationTests.query
    arguments = selected.SelectedSavePreparationTests.arguments
    recover = selected.SelectedSavePreparationTests.recover

    def owned(self, workspace: Path, wide: bool = False) -> tuple[Path, Path, dict]:
        instance = self.prepare(workspace)
        if wide:
            (instance / "backups").mkdir(exist_ok=True)
            # The existing owner records this fixture history. Its >4KiB sidecar
            # makes the real retained writer cross a durable prefix boundary.
            for n in range(96):
                write_save(instance / "backups" / f"selected-owned-fixture-backup-history-{n:03}.zip", b"fixture backup")
        code, out, err = invoke_machine(self.arguments(workspace, self.query(workspace)["revision"], "create"))
        self.assertEqual((0, ""), (code, err), out)
        journal = next(p for p in (workspace / "transactions").glob("*.transaction.v1.json")
                       if json.loads(p.read_text())["command_id"] == "readiness.prepare_selected_save")
        return instance, journal, json.loads(journal.read_text())

    def drift(self, instance: Path, content: bytes = b"kept changed world") -> Path:
        save = instance / "saves/selected.zip"
        write_save(save, content)
        return instance / "metadata/save-refs/selected.zip.save-ref.v1.json"

    def latest(self, workspace: Path) -> dict:
        return next(json.loads(p.read_text()) for p in (workspace / "transactions").glob("*.transaction.v1.json")
                    if json.loads(p.read_text())["commit_strategy"] == "selected_context_retained_stream_rewrite_v1")

    def wait_pause(self, instance: Path, worker: PausedAction, phase: str) -> None:
        marker = instance / (".facman-test-selected-context-" + phase)
        deadline = time.monotonic() + 15
        while worker.thread.is_alive() and time.monotonic() < deadline:
            if marker.is_file() and worker.process is not None:
                try:
                    contents = read_pause_marker(marker)
                except OSError as error:
                    # Windows can expose the name before the marker creator
                    # closes its exclusive handle after the durable flush.
                    if getattr(error, "winerror", None) != 32 or not worker.running(): raise
                    worker.thread.join(0.02)
                    continue
                self.assertEqual(b"1", contents)
                self.assertTrue(worker.running(), worker.summary())
                return
            worker.thread.join(0.02)
        self.fail("No readable marker from the live owned refresh: " + worker.summary())

    def test_paused_world_profile_configuration_source_and_foreign_object_drift_preserve_the_context(self) -> None:
        for variant in ("world", "profile", "configuration", "source", "source-replacement", "target", "parent", "reparse", "metadata"):
            with self.subTest(variant=variant), tempfile.TemporaryDirectory(prefix="selected-refresh-drift-") as value:
                workspace = Path(value)
                instance, source, _ = self.owned(workspace)
                target = self.drift(instance)
                phase = "rewrite_after_manifest"
                worker = PausedAction(self.arguments(workspace, self.query(workspace)["revision"], "refresh"),
                                      dict(os.environ, FACMAN_TEST_SELECTED_CONTEXT_PAUSE=phase))
                link = None
                try:
                    self.wait_pause(instance, worker, phase)
                    if variant == "world": write_save(instance / "saves/selected.zip", b"changed again after confirmation")
                    elif variant == "profile":
                        path = instance / "instance-overrides.v1.json"; path.write_bytes(path.read_bytes() + b"\n")
                    elif variant == "configuration":
                        path = instance / "config/config.ini"; path.write_bytes(path.read_bytes() + b"\n")
                    elif variant == "source": source.write_bytes(source.read_bytes() + b"\n")
                    elif variant == "source-replacement":
                        data = source.read_bytes(); source.rename(source.with_suffix(".original")); source.write_bytes(data)
                    elif variant == "target":
                        data = target.read_bytes(); target.rename(target.with_suffix(".original")); target.write_bytes(data)
                    elif variant in ("parent", "reparse"):
                        parent = target.parent; old = parent.with_name("save-refs.original"); parent.rename(old)
                        if variant == "reparse":
                            if os.name == "nt":
                                from windows_junction import create_junction
                                create_junction(parent, old)
                            else: parent.symlink_to(old, target_is_directory=True)
                            link = parent
                        else:
                            parent.mkdir(); target.write_bytes((old / target.name).read_bytes())
                    elif os.name == "nt":
                        from test_configuration_reconciliation import change_synthetic_dacl_inheritance
                        change_synthetic_dacl_inheritance(target)
                    else: target.chmod(target.stat().st_mode ^ 0o100)
                    release = instance / ".facman-test-selected-context-release"
                    before = snapshot(instance, excluded=release)
                    release.write_bytes(b"release")
                    if variant == "metadata":
                        if os.name == "nt":
                            from test_configuration_reconciliation import readable_security
                            metadata = readable_security(target)
                        else: metadata = target.stat().st_mode
                    worker.finish()
                    self.assertEqual(3, worker.response[0], worker.response)
                    self.assertEqual("recovery_required", json.loads(worker.response[1])["payload"]["outcome"])
                    self.assertEqual(before, snapshot(instance, excluded=release))
                    journal = self.latest(workspace)
                    code, output = self.recover(workspace, journal)
                    self.assertIn(code, (1, 3), output)
                    self.assertEqual(before, snapshot(instance, excluded=release))
                    if variant == "metadata":
                        self.assertEqual(metadata, readable_security(target) if os.name == "nt" else target.stat().st_mode)
                finally:
                    (instance / ".facman-test-selected-context-release").write_bytes(b"release")
                    worker.finish()
                    if link is not None:
                        if os.name == "nt": link.rmdir()
                        else: link.unlink()

    def test_retained_refresh_serializes_competing_owner_and_source_journal_custody(self) -> None:
        with tempfile.TemporaryDirectory(prefix="selected-refresh-concurrency-") as value:
            workspace = Path(value)
            instance, source, _ = self.owned(workspace)
            target = self.drift(instance)
            phase = "rewrite_before_admission"
            worker = PausedAction(self.arguments(workspace, self.query(workspace)["revision"], "refresh"),
                                  dict(os.environ, FACMAN_TEST_SELECTED_CONTEXT_PAUSE=phase))
            try:
                self.wait_pause(instance, worker, phase)
                journal = self.latest(workspace)
                # This exact live owner's recovery lock is intentionally held
                # exclusively. Compare its durable journals without reading
                # lock bytes or excluding any other lock/foreign object.
                own_lock = workspace / "transactions" / (journal["transaction_id"] + ".transaction.v1.json.recovery.lock")
                self.assertTrue(own_lock.is_file())
                frozen = snapshot(workspace / "transactions", excluded=own_lock)
                code, out = self.recover(workspace, journal)
                self.assertEqual(3, code, out)
                self.assertEqual("recovery_lock_contended", out["error"]["code"])
                self.assertEqual(frozen, snapshot(workspace / "transactions", excluded=own_lock))
                projected = self.query(workspace)
                code, out, _ = invoke_machine(self.arguments(workspace, projected["revision"], "competitor"))
                self.assertEqual(1, code, out)
                self.assertEqual(frozen, snapshot(workspace / "transactions", excluded=own_lock))
                self.assertTrue(own_lock.is_file())
                if os.name == "nt":
                    for path in (target, source):
                        with self.assertRaises(OSError): path.rename(path.with_suffix(".foreign"))
                        with self.assertRaises(OSError): path.write_bytes(path.read_bytes())
            finally:
                (instance / ".facman-test-selected-context-release").write_bytes(b"release")
                worker.finish()
            self.assertEqual(0, worker.response[0], worker.response)
            self.assertEqual("satisfied", self.query(workspace)["readiness"]["selected_save"]["state"])

    def test_two_explicit_refreshes_keep_world_file_object_and_original_journals(self) -> None:
        with tempfile.TemporaryDirectory(prefix="selected-refresh-positive-") as value:
            workspace = Path(value)
            instance, source, _ = self.owned(workspace)
            originals = {p: p.read_bytes() for p in (workspace / "transactions").glob("*") if p.is_file()}
            sidecar = instance / "metadata/save-refs/selected.zip.save-ref.v1.json"
            identity = file_identity(sidecar)
            created = json.loads(sidecar.read_text())["created_utc"]
            for n in (1, 2):
                self.drift(instance, f"changed world {n}".encode())
                world = (instance / "saves/selected.zip").read_bytes()
                projected = self.query(workspace)
                self.assertEqual("blocked", projected["readiness"]["selected_save"]["state"])
                descriptor = next(a for a in projected["available_semantic_actions"]
                                  if a["action_id"] == "readiness.prepare_selected_save")
                self.assertEqual("available", descriptor["availability"])
                self.assertIn("Refresh", descriptor["label"])
                plan = projected["dependency_identities"]["selected_save_preparation"]["plan"]
                factorio_validator("factorio_selected_save_preparation_plan.v1.schema.json").validate(plan)
                self.assertIn("refresh", plan)
                before = snapshot(workspace)
                denied, out, _ = invoke_machine(self.arguments(workspace, projected["revision"], f"no-confirm-{n}", confirmation="none"))
                self.assertEqual(1, denied, out)
                self.assertEqual(before, snapshot(workspace))
                args = self.arguments(workspace, projected["revision"], f"refresh-{n}")
                code, out, err = invoke_machine(args)
                self.assertEqual((0, ""), (code, err), out)
                result = json.loads(out)["payload"]
                self.assertEqual("completed", result["outcome"])
                factorio_validator("factorio_selected_save_preparation_result.v1.schema.json").validate(result["action_payload"])
                self.assertEqual("satisfied", result["replacement_snapshot"]["readiness"]["selected_save"]["state"])
                self.assertEqual(identity, file_identity(sidecar))
                current = json.loads(sidecar.read_text())
                self.assertEqual(created, current["created_utc"])
                self.assertEqual(hashlib.sha256(world).hexdigest(), current["save_sha256"])
                self.assertEqual(world, (instance / "saves/selected.zip").read_bytes())
                for p, data in originals.items(): self.assertEqual(data, p.read_bytes())
                frozen = snapshot(workspace)
                replay, replay_out, _ = invoke_machine(args)
                self.assertEqual(0, replay, replay_out)
                self.assertEqual(result, json.loads(replay_out)["payload"])
                self.assertEqual(frozen, snapshot(workspace))
                originals.update({p: p.read_bytes() for p in (workspace / "transactions").glob("*") if p.is_file()})
            self.assertEqual(3, sum(json.loads(p.read_text())["command_id"] == "readiness.prepare_selected_save"
                                    for p in (workspace / "transactions").glob("*.transaction.v1.json")))

    def test_foreign_torn_replaced_linked_and_changed_source_context_get_no_refresh(self) -> None:
        for variant in ("foreign", "torn", "replacement", "hardlink", "source", "generic"):
            with self.subTest(variant=variant), tempfile.TemporaryDirectory(prefix="selected-refresh-refusal-") as value:
                workspace = Path(value)
                instance, source, journal = self.owned(workspace)
                target = self.drift(instance)
                if variant == "foreign":
                    document = json.loads(target.read_text()); document["profile_id"] = "foreign"
                    target.write_text(json.dumps(document) + "\n")
                elif variant == "torn": target.write_bytes(target.read_bytes()[:23])
                elif variant == "replacement":
                    data = target.read_bytes(); target.rename(target.with_suffix(".original")); target.write_bytes(data)
                elif variant == "hardlink": os.link(target, target.with_suffix(".extra-link"))
                elif variant == "source":
                    journal["effect_file_identity"] = "0:0"; source.write_text(json.dumps(journal) + "\n")
                else:
                    journal["commit_strategy"] = "durable_sidecar_create_no_save_mutation"
                    source.write_text(json.dumps(journal) + "\n")
                before = snapshot(workspace)
                projected = self.query(workspace)
                self.assertIsNone(projected["dependency_identities"]["selected_save_preparation"]["plan"])
                code, out, _ = invoke_machine(self.arguments(workspace, projected["revision"], "refused"))
                self.assertEqual(1, code, out)
                self.assertEqual(before, snapshot(workspace))

    def test_interrupted_refresh_resumes_only_its_retained_object_and_terminal_is_read_only(self) -> None:
        for phase in ("rewrite_after_manifest", "rewrite_before_admission", "rewrite_after_admission",
                      "rewrite_after_prefix", "rewrite_after_write", "rewrite_after_truncate",
                      "rewrite_after_verification_checkpoint", "rewrite_after_finalization"):
            with self.subTest(phase=phase), tempfile.TemporaryDirectory(prefix="selected-refresh-loss-") as value:
                workspace = Path(value)
                instance, source, _ = self.owned(workspace, wide=phase == "rewrite_after_prefix")
                original_journal = source.read_bytes()
                target = self.drift(instance)
                identity = file_identity(target)
                if phase == "rewrite_after_prefix": time.sleep(1.05)
                code, out, _ = invoke_machine(self.arguments(workspace, self.query(workspace)["revision"], "refresh"),
                    env=dict(os.environ, FACMAN_TEST_SELECTED_CONTEXT_EXIT=phase))
                self.assertEqual(74, code, out)
                journal = self.latest(workspace)
                if phase == "rewrite_after_prefix":
                    context = json.loads(journal["operation_context"])
                    actual = target.read_bytes()
                    self.assertGreater(len(actual), 4096)
                    self.assertNotEqual(context["original_sidecar_text"].encode(), actual)
                    self.assertNotEqual(context["sidecar_text"].encode(), actual)
                    self.assertEqual(hashlib.sha256((instance / "saves/selected.zip").read_bytes()).hexdigest(), json.loads(actual)["save_sha256"])
                    public = self.query(workspace)
                    self.assertEqual("blocked", public["readiness"]["selected_save"]["state"])
                    self.assertIsNone(public["dependency_identities"]["selected_save_preparation"]["plan"])
                code, out = self.recover(workspace, journal)
                self.assertEqual(0, code, out)
                self.assertEqual(identity, file_identity(target))
                self.assertEqual(original_journal, source.read_bytes())
                self.assertEqual("satisfied", self.query(workspace)["readiness"]["selected_save"]["state"])
                before = snapshot(workspace)
                code, out = self.recover(workspace, journal)
                self.assertEqual(0, code, out)
                self.assertEqual(before, snapshot(workspace))
                data = target.read_bytes(); target.rename(target.with_suffix(".retained")); target.write_bytes(data)
                before = snapshot(instance)
                code, out = self.recover(workspace, journal)
                self.assertEqual(3, code, out)
                self.assertEqual(before, snapshot(instance))
                target.rename(target.with_suffix(".foreign-preserved"))
                before = snapshot(instance)
                code, out = self.recover(workspace, journal)
                self.assertEqual(3, code, out)
                self.assertFalse(target.exists())
                self.assertEqual(before, snapshot(instance))

    def test_unadmitted_partial_and_foreign_interrupted_bytes_are_preserved(self) -> None:
        for variant in ("before-admission", "after-admission", "missing-authority"):
            with self.subTest(variant=variant), tempfile.TemporaryDirectory(prefix="selected-refresh-foreign-loss-") as value:
                workspace = Path(value)
                instance, source, _ = self.owned(workspace, wide=True)
                target = self.drift(instance)
                phase = "rewrite_after_manifest" if variant == "before-admission" else "rewrite_after_prefix"
                if phase == "rewrite_after_prefix": time.sleep(1.05)
                code, out, _ = invoke_machine(self.arguments(workspace, self.query(workspace)["revision"], "refresh"),
                    env=dict(os.environ, FACMAN_TEST_SELECTED_CONTEXT_EXIT=phase))
                self.assertEqual(74, code, out)
                journal = self.latest(workspace)
                if variant == "missing-authority":
                    journal["completed_steps"].remove("selected_context_rewrite_mutation_authorized")
                    path = workspace / "transactions" / (journal["transaction_id"] + ".transaction.v1.json")
                    path.write_text(json.dumps(journal) + "\n")
                elif variant == "before-admission":
                    from test_configuration_reconciliation import genuine_partial
                    context = json.loads(journal["operation_context"])
                    target.write_bytes(genuine_partial(context["original_sidecar_text"].encode(), context["sidecar_text"].encode()))
                else: target.write_bytes(b"foreign partial bytes must be preserved\n")
                before = snapshot(instance)
                source_bytes = source.read_bytes()
                code, out = self.recover(workspace, journal)
                self.assertEqual(3, code, out)
                self.assertEqual(before, snapshot(instance))
                self.assertEqual(source_bytes, source.read_bytes())


    def test_pending_refresh_does_not_relabel_other_selected_filename_or_instance(self) -> None:
        for variant in ("filename", "instance"):
            with self.subTest(variant=variant), tempfile.TemporaryDirectory(prefix="selected-refresh-other-") as value:
                workspace = Path(value)
                instance, _, _ = self.owned(workspace)
                if variant == "instance":
                    call(workspace, "instances", "create", "Other", "--id", "other", "--install", "fixture")
                    other = workspace / "instances/other"
                    write_save(other / "saves/selected.zip", b"other instance world")
                    call(workspace, "modsets", "apply", "other", "--enable", "base")
                    call(workspace, "profiles", "apply", "other", "gui", "--selection-mode", "load-save", "--selection", "selected.zip")
                self.drift(instance)
                phase = "rewrite_after_manifest"
                worker = PausedAction(self.arguments(workspace, self.query(workspace)["revision"], "refresh"),
                                      dict(os.environ, FACMAN_TEST_SELECTED_CONTEXT_PAUSE=phase))
                try:
                    self.wait_pause(instance, worker, phase)
                    self.assertEqual("blocked", self.query(workspace)["readiness"]["selected_save"]["state"])
                    if variant == "filename":
                        before = snapshot(instance)
                        refused = call(workspace, "profiles", "apply", "main", "gui", "--selection-mode",
                                       "load-save", "--selection", "selected-other.zip", success=False)
                        self.assertEqual("profile_transaction_recovery_required", refused["refusal"]["code"])
                        self.assertEqual(before, snapshot(instance))
                        # The ordinary profile owner correctly refuses while
                        # recovery is pending. Change only this owned fixture's
                        # selected input to exercise public observation drift.
                        path = instance / "instance-overrides.v1.json"
                        profile = json.loads(path.read_bytes())
                        profile["values"]["selection"] = "selected-other.zip"
                        path.write_text(json.dumps(profile) + "\n", encoding="utf-8")
                        projected = self.query(workspace)
                    else:
                        code, out, error = invoke_machine(["--workspace", str(workspace), "presentation", "query", "instances",
                                                         "--instance", "other", "--intent", "load_save", "--json"])
                        self.assertEqual((0, ""), (code, error), out)
                        projected = json.loads(out)["payload"]
                    self.assertEqual("degraded", projected["readiness"]["selected_save"]["state"])
                    self.assertNotIn("instance_selected_save_context_refresh_pending",
                                     [b["code"] for b in projected["readiness"]["blockers"]])
                finally:
                    (instance / ".facman-test-selected-context-release").write_bytes(b"release")
                    worker.finish()
                self.assertEqual(3 if variant == "filename" else 0, worker.response[0], worker.response)


if __name__ == "__main__":
    unittest.main()
