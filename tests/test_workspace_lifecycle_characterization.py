# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import hashlib
import json
import os
import stat
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path

from native_cli import invoke, invoke_machine

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "tests" / "fixtures" / "workspace-lifecycle" / "current-behavior.v1.json"
FIXTURE_INSTALL = ROOT / "tests" / "fixtures" / "fake_factorio_install"


def tree(root: Path) -> list[tuple[str, str]]:
    result: list[tuple[str, str]] = []
    if not root.exists() and not root.is_symlink():
        return result
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        if path.is_symlink():
            result.append((relative, "link"))
        elif path.is_file():
            result.append((relative, hashlib.sha256(path.read_bytes()).hexdigest()))
        else:
            result.append((relative, "directory"))
    return result


def payload(stdout: str) -> dict[str, object]:
    document = json.loads(stdout)
    if document.get("schema") == "facman.transport_response.v2":
        value = document.get("payload")
        return value if isinstance(value, dict) else document
    return document


class WorkspaceLifecycleCharacterization(unittest.TestCase):
    maxDiff = None

    def setUp(self) -> None:
        self.corpus = json.loads(CORPUS.read_text(encoding="utf-8"))

    def initialize(self, workspace: Path) -> None:
        code, _stdout, stderr = invoke([
            "--workspace", str(workspace), "installs", "import",
            str(FIXTURE_INSTALL), "--id", "fixture", "--json",
        ])
        self.assertEqual(code, 0, stderr)

    def make_legacy_install(self, workspace: Path) -> tuple[Path, Path]:
        canonical = workspace / "installs" / "refs" / "fixture.json"
        legacy = workspace / "installs" / "installed_state" / "fixture.json"
        legacy.parent.mkdir(parents=True, exist_ok=True)
        canonical.replace(legacy)
        return legacy, canonical

    def inspect(self, workspace: Path) -> tuple[int, dict[str, object], str]:
        code, stdout, stderr = invoke_machine([
            "--workspace", str(workspace), "workspace", "migration", "inspect", "--json",
        ])
        return code, payload(stdout), stderr

    def apply(self, workspace: Path) -> tuple[int, dict[str, object], str]:
        code, plan_stdout, stderr = invoke_machine([
            "--workspace", str(workspace), "workspace", "migration", "plan", "--json",
        ])
        self.assertEqual(code, 0, plan_stdout)
        plan = payload(plan_stdout)
        code, stdout, stderr = invoke_machine([
            "--workspace", str(workspace), "workspace", "migration", "apply",
            "--expected-revision", str(plan["expected_workspace_revision"]),
            "--expected-root", str(plan["expected_root_identity"]),
            "--plan-digest", str(plan["plan_digest"]),
            "--confirmation", "explicit",
            "--request-id", "request-characterization",
            "--operation-id", "operation-characterization",
            "--attempt-id", "attempt-characterization",
            "--idempotency-key", "idempotency-characterization",
            "--json",
        ])
        return code, payload(stdout), stderr

    def test_corpus_is_closed_and_binds_every_required_observation(self) -> None:
        self.assertEqual(self.corpus["schema"], "facman.workspace_lifecycle_characterization.v1")
        cases = self.corpus["cases"]
        self.assertEqual(len(cases), 12)
        self.assertEqual(len({case["id"] for case in cases}), 12)
        self.assertEqual(len({case["probe"] for case in cases}), 12)
        required = {
            "id", "probe", "root_identity", "format", "workspace_revision",
            "inventory_digest", "authority", "observation", "mutation_available", "gap",
        }
        for case in cases:
            self.assertEqual(set(case), required, case["id"])

    def test_all_characterized_probes_execute_without_unrecorded_mutation(self) -> None:
        handlers = {case["probe"]: getattr(self, f"probe_{case['probe']}") for case in self.corpus["cases"]}
        self.assertEqual(len(handlers), 12)
        for name, handler in handlers.items():
            with self.subTest(probe=name):
                handler()

    def probe_missing(self) -> None:
        with tempfile.TemporaryDirectory() as parent:
            workspace = Path(parent) / "not-created"
            code, result, stderr = self.inspect(workspace)
            self.assertEqual((code, stderr), (0, ""))
            self.assertEqual(result["status"], "changes_detected")
            self.assertEqual(result["actions"][0]["kind"], "create_workspace_identity")
            self.assertFalse(workspace.exists())

    def probe_healthy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            self.initialize(workspace)
            before = tree(workspace)
            code, result, stderr = self.inspect(workspace)
            self.assertEqual((code, stderr), (0, ""))
            self.assertEqual(result["status"], "no_changes")
            self.assertEqual(tree(workspace), before)

    def probe_legacy_record(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            self.initialize(workspace)
            self.make_legacy_install(workspace)
            before = tree(workspace)
            code, stdout, stderr = invoke([
                "--workspace", tmp, "workspace", "migration", "plan", "--json",
            ])
            result = json.loads(stdout)
            self.assertEqual((code, stderr), (0, ""))
            self.assertTrue(result["apply_enabled"])
            self.assertEqual(result["actions"][0]["kind"], "canonicalize_legacy_install_ref")
            self.assertEqual(tree(workspace), before)

    def probe_interrupted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            self.initialize(workspace)
            journal_root = workspace / "transactions" / "workspace-migrations"
            journal_root.mkdir(parents=True, exist_ok=True)
            (journal_root / "interrupted.workspace-migration.v1.json").write_text(json.dumps({
                "schema": "facman.workspace_migration_journal.v1",
                "migration_id": "interrupted",
                "state": "recovery_required",
                "completed_actions": 0,
                "actions": [],
            }), encoding="utf-8")
            before = tree(workspace)
            code, result, stderr = self.apply(workspace)
            self.assertEqual((code, stderr), (1, ""))
            self.assertEqual(result["refusal"]["code"], "workspace_migration_recovery_required")
            self.assertEqual(tree(workspace), before)

    def probe_future(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            (workspace / "workspace.v1.json").write_text(json.dumps({
                "schema": "facman.factorio.workspace.v2", "workspace_id": "future", "layout_version": 2,
            }), encoding="utf-8")
            before = tree(workspace)
            code, result, _stderr = self.inspect(workspace)
            self.assertEqual(code, 1)
            self.assertEqual(result["refusal"]["code"], "workspace_layout_future_or_unknown")
            self.assertEqual(tree(workspace), before)

    def probe_corrupt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            self.initialize(workspace)
            (workspace / "workspace.v1.json").write_text("{", encoding="utf-8")
            before = tree(workspace)
            code, result, _stderr = self.inspect(workspace)
            self.assertEqual(code, 1)
            self.assertIn(result["refusal"]["code"], {
                "workspace_manifest_invalid", "json_parse_error", "json_unexpected_end",
            })
            self.assertEqual(tree(workspace), before)

    def probe_foreign(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            (workspace / "foreign.txt").write_text("foreign", encoding="utf-8")
            before = tree(workspace)
            code, result, stderr = self.apply(workspace)
            self.assertEqual((code, stderr), (1, ""))
            self.assertIn(result["refusal"]["code"], {
                "workspace_migration_action_unsupported", "workspace_migration_stale_plan",
            })
            self.assertEqual(tree(workspace), before)

    def probe_link(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            parent = Path(tmp)
            target = parent / "target"
            target.mkdir()
            link = parent / "linked"
            try:
                link.symlink_to(target, target_is_directory=True)
            except OSError:
                return
            before = tree(target)
            code, result, _stderr = self.apply(link)
            self.assertEqual(code, 1)
            self.assertIn(result["refusal"]["code"], {
                "workspace_migration_action_unsupported", "workspace_migration_conflict",
                "workspace_root_claim_refused",
            })
            self.assertEqual(tree(target), before)

    def probe_read_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            self.initialize(workspace)
            self.make_legacy_install(workspace)
            before = tree(workspace)
            original_mode = workspace.stat().st_mode
            try:
                workspace.chmod(stat.S_IREAD | stat.S_IEXEC)
                code, result, stderr = self.inspect(workspace)
                self.assertEqual((code, stderr), (0, ""))
                self.assertTrue(result["apply_enabled"])
                self.assertEqual(tree(workspace), before)
            finally:
                workspace.chmod(original_mode)

    @contextmanager
    def held_migration_lock(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        text = b'{"schema":"facman.workspace_migration_lock.v1","identity":"characterization"}\n'
        if os.name == "nt":
            import ctypes
            from ctypes import wintypes
            create_file = ctypes.windll.kernel32.CreateFileW
            create_file.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                    wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
            create_file.restype = wintypes.HANDLE
            handle = create_file(str(path), 0xC0000000, 0x00000001, None, 1, 0x80, None)
            invalid = wintypes.HANDLE(-1).value
            if handle == invalid:
                self.fail("could not create characterization lock")
            written = wintypes.DWORD()
            self.assertTrue(ctypes.windll.kernel32.WriteFile(handle, text, len(text), ctypes.byref(written), None))
            try:
                yield
            finally:
                ctypes.windll.kernel32.CloseHandle(handle)
                path.unlink(missing_ok=True)
        else:
            import fcntl
            with path.open("xb+") as stream:
                stream.write(text)
                stream.flush()
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
                try:
                    yield
                finally:
                    fcntl.flock(stream, fcntl.LOCK_UN)
            path.unlink(missing_ok=True)

    def probe_contended_lock(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            self.initialize(workspace)
            self.make_legacy_install(workspace)
            lock = workspace / "transactions" / "workspace-migrations" / "workspace-migration.lock"
            lock.parent.mkdir(parents=True, exist_ok=True)
            before_without_lock = tree(workspace)
            with self.held_migration_lock(lock):
                code, result, stderr = self.apply(workspace)
                self.assertEqual((code, stderr), (1, ""))
                self.assertEqual(result["refusal"]["code"], "workspace_migration_conflict")
            self.assertEqual(tree(workspace), before_without_lock)

    def probe_stale_plan(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            self.initialize(workspace)
            self.make_legacy_install(workspace)
            before = tree(workspace)
            code, stdout, stderr = invoke([
                "--workspace", tmp, "workspace", "migration", "plan", "--json",
            ])
            result = json.loads(stdout)
            self.assertEqual((code, stderr), (0, ""))
            self.assertIn("expected_workspace_revision", result)
            self.assertIn("plan_digest", result)
            legacy = workspace / "installs" / "installed_state" / "fixture.json"
            legacy.write_text(legacy.read_text(encoding="utf-8") + "\n", encoding="utf-8")
            code, stale, stderr = invoke_machine([
                "--workspace", tmp, "workspace", "migration", "apply",
                "--expected-revision", str(result["expected_workspace_revision"]),
                "--expected-root", str(result["expected_root_identity"]),
                "--plan-digest", str(result["plan_digest"]),
                "--confirmation", "explicit",
                "--request-id", "request-stale",
                "--operation-id", "operation-stale",
                "--attempt-id", "attempt-stale",
                "--idempotency-key", "idempotency-stale",
                "--json",
            ])
            self.assertEqual((code, stderr), (1, ""))
            self.assertEqual(payload(stale)["refusal"]["code"], "workspace_migration_stale_plan")
            self.assertFalse((workspace / "installs" / "refs" / "fixture.json").exists())
            self.assertNotEqual(tree(workspace), before)

    def probe_foreign_staging(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            self.initialize(workspace)
            self.make_legacy_install(workspace)
            foreign = workspace / "transactions" / "workspace-migrations" / "foreign.data" / "keep.txt"
            foreign.parent.mkdir(parents=True, exist_ok=True)
            foreign.write_text("do not overwrite", encoding="utf-8")
            before = tree(workspace)
            code, result, stderr = self.inspect(workspace)
            self.assertEqual((code, stderr), (0, ""))
            self.assertEqual(result["status"], "changes_detected")
            self.assertEqual(foreign.read_text(encoding="utf-8"), "do not overwrite")
            self.assertEqual(tree(workspace), before)


if __name__ == "__main__":
    unittest.main()
