# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

"""Laboratory identity, coverage, drift and no-effect custody refusals."""
from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
import tempfile
import subprocess
import sys
import unittest
from unittest.mock import patch

from tools import development_layout as layout
from tools import lab_input_registry as lab
from tools import lab_run_custody as custody


def swap_after_read(target, replacement):
    """Replace real disposable bytes after a read closes, before parsing reopens."""
    original = Path.open
    def opened(path, *args, **kwargs):
        stream = original(path, *args, **kwargs)
        if path != target or not args or args[0] != "rb":
            return stream
        class AfterClose:
            def __enter__(self):
                return stream.__enter__()
            def __exit__(self, *error):
                result = stream.__exit__(*error)
                with original(target, "wb") as output:
                    output.write(replacement)
                return result
        return AfterClose()
    return patch.object(Path, "open", opened)


class LabRegistryTests(unittest.TestCase):
    def setUp(self):
        self.document = lab.load(lab.ROOT / lab.REGISTRY)

    def test_current_census_keeps_available_fixtures_and_external_cells_distinct(self):
        lab.validate(self.document)
        rows = lab.matrix(self.document)
        self.assertEqual(len(rows), 123)
        self.assertEqual(len({row["id"] for row in rows}), 123)
        self.assertEqual(sum(row["status"] == "fixture_preparation_available" for row in rows), 52)
        self.assertTrue(all(not row["qualified"] and not row["execution_authorized"] for row in rows))
        for row in rows:
            if row["kind"] != "machine_fixture" or row["platform"] == "macos_intel_x64":
                self.assertEqual(row["status"], "blocked_external")
                self.assertTrue(row["blockers"])
            self.assertIn("owned_roots", row["pending_run_custody"])

    def test_real_cli_check_and_matrix_run_without_pythonpath(self):
        env = dict(os.environ)
        env.pop("PYTHONPATH", None)
        for command in ("check", "matrix"):
            completed = subprocess.run([sys.executable, str(lab.ROOT / "tools/lab_input_registry.py"), command],
                                       cwd=lab.ROOT, env=env, capture_output=True, text=True)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            if command == "matrix":
                self.assertEqual(len(json.loads(completed.stdout)["cells"]), 123)

    def test_no_game_is_needed_for_first_run_human_observation(self):
        rows = lab.matrix(self.document)
        row = next(row for row in rows if row["id"] == "windows_x64/human_experience/J01_first_run_workspace")
        self.assertFalse(any("Factorio input custody" in item for item in row["blockers"]))
        play = next(row for row in rows if row["id"] == "windows_x64/human_experience/J09_play_session")
        self.assertTrue(any("Factorio input custody" in item for item in play["blockers"]))

    def test_invented_authority_missing_coverage_and_host_substitution_refuse(self):
        mutations = [
            lambda d: d.update(execution_authorized=True),
            lambda d: d.update(qualification_granted=True),
            lambda d: d["coverage"]["journeys"].pop(),
            lambda d: d["coverage"]["fixture_scenarios"].pop(),
            lambda d: d["hosts"][0].update(identity="another-machine"),
            lambda d: d["hosts"][0].update(environment="another-os"),
            lambda d: d["hosts"][2].update(capabilities=["machine_fixture"]),
            lambda d: d["hosts"][1].update(id=d["hosts"][0]["id"]),
            lambda d: d["inputs"]["approved_game"]["linux_x64"].update(digest="a" * 64),
            lambda d: d["run_requirements"].remove("reset_and_export"),
            lambda d: d["source_refs"]["corpus"].update(path="../outside.json"),
            lambda d: d["source_refs"]["hosts"].update(semantic_sha256="0" * 64),
        ]
        for index, mutate in enumerate(mutations):
            document = copy.deepcopy(self.document)
            mutate(document)
            with self.subTest(index=index), self.assertRaises(lab.Invalid):
                lab.validate(document)

    def test_duplicate_json_and_actual_input_drift_refuse(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary).resolve() / "input.json"
            path.write_bytes(b'{"schema":1,"schema":2}')
            with self.assertRaisesRegex(lab.Invalid, "duplicate"):
                lab.load(path)
            path.write_bytes(b"original")
            pin = hashlib.sha256(path.read_bytes()).hexdigest()
            self.assertEqual(lab.inspect_file(path, pin)["bytes"], 8)
            path.write_bytes(b"modified")
            before = path.read_bytes()
            with self.assertRaisesRegex(lab.Invalid, "digest differs"):
                lab.inspect_file(path, pin)
            self.assertEqual(path.read_bytes(), before)
            with self.assertRaises(lab.Invalid):
                lab.inspect_file(Path("relative-input"), pin)

    def test_approval_semantics_and_pin_use_the_same_read(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            for ref in self.document["source_refs"].values():
                destination = root / ref["path"]
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes((lab.ROOT / ref["path"]).read_bytes())
            approval = {"schema": "facman.lab-input-approval.v1", "platform": "linux_x64",
                        "input_sha256": "a" * 64, "issuer": "fixture-only", "scope": "input_custody_only"}
            path = root / "approval.json"
            path.write_bytes(json.dumps(approval).encode())
            game = self.document["inputs"]["approved_game"]["windows_x64"]
            game.update(status="registered", digest="a" * 64, blocker=None,
                        approval_ref={"path": "approval.json", "semantic_sha256": lab.semantic_digest(path)})
            replacement = json.dumps(dict(approval, platform="windows_x64")).encode()
            with swap_after_read(path, replacement), self.assertRaises(lab.Invalid):
                lab.validate(self.document, root)
            self.assertEqual(path.read_bytes(), replacement)

    def test_semantic_source_pin_survives_only_whitespace_changes(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary).resolve() / "data.json"
            path.write_bytes(b'{"scenario":"one"}\r\n')
            first = lab.semantic_digest(path)
            path.write_bytes(b'{\n  "scenario": "one"\n}\n')
            self.assertEqual(first, lab.semantic_digest(path))
            path.write_bytes(b'{"scenario":"two"}')
            self.assertNotEqual(first, lab.semantic_digest(path))


class RunCustodyTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="facman-lab-")
        self.addCleanup(self.temporary.cleanup)
        env = patch.dict(os.environ, {"FACMAN_DEV_ROOT": self.temporary.name})
        env.start()
        self.addCleanup(env.stop)
        self.document = lab.load(lab.ROOT / lab.REGISTRY)
        self.task_root = layout.task_root(lab.ROOT, "lab-custody-test")
        layout.ensure_task_root(self.task_root, lab.ROOT, "lab-custody-test")
        self.candidate = self.task_root / "synthetic-candidate"
        self.candidate.write_bytes(b"synthetic source-fixture candidate, not product qualification")
        fixture = lab.ROOT / self.document["inputs"]["fixture"]["path"]
        pin = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
        self.record = {"schema": "facman.lab-run-custody.v1",
                       "scenario_id": "windows_x64/machine_fixture/no_installation",
                       "registry_sha256": hashlib.sha256(json.dumps(self.document, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
                       "source_commit": "a" * 40, "source_tree": "b" * 40,
                       "task_root": str(self.task_root), "marker_sha256": pin(self.task_root / layout.MARKER_NAME),
                       "roots": {"state": str(self.task_root / "state"), "export": str(self.task_root / "export")},
                       "effects": ["owned_fixture_files", "injected_or_fake_process", "evidence_export"],
                       "reset": "retain_then_marker_owned_cleanup", "export": "hash_and_archive_before_reset",
                       "candidate": {"path": str(self.candidate), "sha256": pin(self.candidate)},
                       "input": {"path": str(fixture), "sha256": pin(fixture)}}

    def snapshot(self):
        return {p.relative_to(self.task_root).as_posix(): p.read_bytes()
                for p in self.task_root.rglob("*") if p.is_file()}

    def test_concrete_inputs_roots_reset_and_export_bind_without_effects(self):
        before = self.snapshot()
        result = custody.inspect(self.record, self.document)
        self.assertEqual(result["scenario_id"], self.record["scenario_id"])
        self.assertFalse(result["execution_authorized"])
        self.assertFalse(result["qualification_granted"])
        self.assertTrue(result["fresh_host_check_required"])
        self.assertEqual(before, self.snapshot())
        self.assertFalse((self.task_root / "state").exists())

    def test_input_hash_and_semantic_custody_cannot_mix_two_reads(self):
        path = self.task_root / "swapped-input.json"
        path.write_bytes(b'{"unregistered":"fixture"}')
        self.record["input"] = {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        approved = (lab.ROOT / self.document["inputs"]["fixture"]["path"]).read_bytes()
        with swap_after_read(path, approved), self.assertRaises(lab.Invalid):
            custody.inspect(self.record, self.document)
        self.assertEqual(path.read_bytes(), approved)

    def test_marker_hash_and_ownership_cannot_mix_two_reads(self):
        marker = self.task_root / layout.MARKER_NAME
        original = marker.read_bytes()
        foreign = json.loads(original)
        foreign["owner"] = "foreign"
        marker.write_bytes(json.dumps(foreign).encode())
        self.record["marker_sha256"] = hashlib.sha256(marker.read_bytes()).hexdigest()
        with swap_after_read(marker, original), self.assertRaises(ValueError):
            custody.inspect(self.record, self.document)
        self.assertEqual(marker.read_bytes(), original)

    def test_actual_dangling_link_ancestor_is_refused(self):
        target = self.task_root / "temporary-target"
        target.mkdir()
        link = self.task_root / "dangling-link"
        if os.name == "nt":
            completed = subprocess.run(["cmd.exe", "/d", "/c", "mklink", "/J", str(link), str(target)],
                                       capture_output=True, text=True)
            self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        else:
            link.symlink_to(target, target_is_directory=True)
        try:
            target.rmdir()
            self.assertFalse(link.exists())
            self.record["roots"]["state"] = str(link / "state")
            with self.assertRaisesRegex(lab.Invalid, "link"):
                custody.inspect(self.record, self.document)
        finally:
            # Remove only the newly created link itself, never follow its target.
            if os.name == "nt":
                os.rmdir(link)
            else:
                link.unlink()

    def test_missing_ownership_root_escape_effect_or_input_substitution_refuse_without_effects(self):
        mutations = [
            lambda r: r.update(marker_sha256="f" * 64),
            lambda r: r["roots"].update(state=str(self.task_root.parent / "foreign")),
            lambda r: r["roots"].update(export=r["roots"]["state"]),
            lambda r: r["effects"].append("factorio_process"),
            lambda r: r.update(reset="delete_all"),
            lambda r: r.update(registry_sha256="c" * 64),
            lambda r: r.update(scenario_id="windows_x64/real_game/J09_play_session"),
            lambda r: r.update(scenario_id="macos_intel_x64/machine_fixture/no_installation"),
            lambda r: r["candidate"].update(sha256="0" * 64),
            lambda r: r["input"].update(path=str(self.candidate), sha256=r["candidate"]["sha256"]),
        ]
        for index, mutate in enumerate(mutations):
            record = copy.deepcopy(self.record)
            mutate(record)
            before = self.snapshot()
            with self.subTest(index=index), self.assertRaises((ValueError, OSError)):
                custody.inspect(record, self.document)
            self.assertEqual(before, self.snapshot())


if __name__ == "__main__":
    unittest.main()
