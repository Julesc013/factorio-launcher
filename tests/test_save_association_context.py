# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path

from test_save_index_retention import call, setup, validate, write_save


def inventory(workspace: Path) -> dict[str, str]:
    return {
        path.relative_to(workspace).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in workspace.rglob("*")
        if path.is_file() and not path.is_symlink()
    }


class SaveAssociationContextTests(unittest.TestCase):
    def prepare(self, workspace: Path, content: bytes = b'{"mods":[]}\n') -> tuple[Path, Path, Path]:
        instance = setup(workspace)
        write_save(instance / "saves" / "world.zip", b"opaque save context fixture")
        lock = instance / "mods" / "modset-lock.v1.json"
        lock.write_bytes(content)
        call(workspace, "saves", "associate", "world.zip", "--instance", "save-index")
        sidecar = instance / "metadata" / "save-refs" / "world.zip.save-ref.v1.json"
        return instance, lock, sidecar

    def observe(self, workspace: Path, expected: str) -> dict:
        before = inventory(workspace)
        contexts = []
        for command in ("index", "inspect", "verify"):
            arguments = ["saves", command]
            if command != "index":
                arguments.append("world.zip")
            report = call(workspace, *arguments, "--instance", "save-index")
            self.assertEqual([], validate(report, "factorio_save_intelligence.v1.schema.json"))
            self.assertEqual("unsupported", report["deep_factorio_save_metadata"])
            self.assertFalse(report["mutation_executed"])
            self.assertFalse(report["save_content_modified"])
            self.assertEqual("current", report["saves"][0]["association"]["status"])
            if command == "verify":
                self.assertEqual("pass", report["status"])
            context = report["saves"][0]["association"]["context"]
            self.assertEqual(expected, context["status"])
            self.assertEqual("unclaimed", context["gameplay_compatibility"])
            contexts.append(context)
        self.assertEqual(contexts[0], contexts[1])
        self.assertEqual(contexts[1], contexts[2])
        self.assertEqual(before, inventory(workspace))
        return contexts[0]

    def query(self, workspace: Path) -> dict:
        return call(workspace, "presentation", "query", "saves", "--instance", "save-index")

    def test_game_and_content_drift_reach_ordinary_snapshot_without_save_mutation(self) -> None:
        with tempfile.TemporaryDirectory(prefix="facman save context drift ") as directory:
            workspace = Path(directory)
            instance, lock, sidecar = self.prepare(workspace)
            pinned = sidecar.read_bytes()
            self.observe(workspace, "match")
            first = self.query(workspace)
            manifest = instance / "instance.v1.json"
            original = manifest.read_bytes()
            record = json.loads(original)
            record["factorio_version"] = "2.0.78"
            manifest.write_text(json.dumps(record) + "\n", encoding="utf-8")
            context = self.observe(workspace, "drifted")
            self.assertEqual("drifted", context["factorio_version"]["status"])
            changed = self.query(workspace)
            self.assertNotEqual(first["revision"], changed["revision"])
            self.assertEqual(context, changed["page"]["items"][0]["association_context"])
            manifest.write_bytes(original)
            lock.write_bytes(b'{"mods":[],"changed":true}\n')
            context = self.observe(workspace, "drifted")
            self.assertEqual("match", context["factorio_version"]["status"])
            self.assertEqual("drifted", context["modset_lock"]["status"])
            content = self.query(workspace)
            self.assertNotEqual(first["revision"], content["revision"])
            self.assertEqual(context, content["page"]["items"][0]["association_context"])
            self.assertEqual(pinned, sidecar.read_bytes())
            before = inventory(workspace)
            self.assertEqual(content["revision"], self.query(workspace)["revision"])
            self.assertEqual(before, inventory(workspace))

    def test_missing_legacy_evidence_stays_unknown(self) -> None:
        with tempfile.TemporaryDirectory(prefix="facman save context legacy ") as directory:
            workspace = Path(directory)
            _, _, sidecar = self.prepare(workspace)
            original = json.loads(sidecar.read_text(encoding="utf-8"))
            cases = [("factorio_version", None), ("factorio_version", "2.0"),
                     ("modset_lock_sha256", ""), ("modset_lock_sha256", "z" * 64)]
            for field, value in cases:
                with self.subTest(field=field, value=value):
                    record = dict(original)
                    if value is None:
                        del record[field]
                    else:
                        record[field] = value
                    sidecar.write_text(json.dumps(record) + "\n", encoding="utf-8")
                    self.observe(workspace, "unknown")

    def test_empty_file_and_absent_lock_have_distinct_observations(self) -> None:
        with tempfile.TemporaryDirectory(prefix="facman save context absence ") as directory:
            workspace = Path(directory)
            _, lock, sidecar = self.prepare(workspace, b"")
            context = self.observe(workspace, "match")
            self.assertEqual(hashlib.sha256(b"").hexdigest(), context["modset_lock"]["current_sha256"])
            lock.unlink()
            context = self.observe(workspace, "drifted")
            self.assertEqual("absent", context["modset_lock"]["current_presence"])
            self.assertIsNone(context["modset_lock"]["current_sha256"])
            record = json.loads(sidecar.read_text(encoding="utf-8"))
            record["modset_lock_sha256"] = ""
            sidecar.write_text(json.dumps(record) + "\n", encoding="utf-8")
            self.observe(workspace, "unknown")
            lock.write_bytes(b"")
            self.observe(workspace, "unknown")

    def test_historical_profile_is_provenance(self) -> None:
        with tempfile.TemporaryDirectory(prefix="facman save context profile ") as directory:
            workspace = Path(directory)
            instance, _, sidecar = self.prepare(workspace)
            pinned = sidecar.read_bytes()
            manifest = instance / "instance.v1.json"
            record = json.loads(manifest.read_text(encoding="utf-8"))
            record["profile"] = "different-profile"
            manifest.write_text(json.dumps(record) + "\n", encoding="utf-8")
            self.observe(workspace, "match")
            self.assertEqual(pinned, sidecar.read_bytes())

    def test_nonregular_multiply_linked_and_over_budget_context_is_unavailable(self) -> None:
        with tempfile.TemporaryDirectory(prefix="facman save context unreadable ") as directory:
            workspace = Path(directory)
            _, lock, _ = self.prepare(workspace)
            content = lock.read_bytes()
            alias = lock.with_name("hardlink-fixture.json")
            os.link(lock, alias)
            self.observe(workspace, "unavailable")
            alias.unlink()
            self.observe(workspace, "match")
            lock.unlink()
            lock.mkdir()
            self.observe(workspace, "unavailable")
            lock.rmdir()
            lock.write_bytes(b"x" * (1024 * 1024 + 1))
            self.observe(workspace, "unavailable")
            lock.write_bytes(content)
            self.observe(workspace, "match")

    def test_final_broken_and_parent_links_are_unavailable(self) -> None:
        with tempfile.TemporaryDirectory(prefix="facman save context links ") as directory:
            workspace = Path(directory)
            instance, lock, _ = self.prepare(workspace)
            original = lock.with_name("original-lock.json")
            lock.rename(original)
            try:
                lock.symlink_to(original)
            except OSError as error:
                original.rename(lock)
                self.skipTest(f"required_blocked: symlink creation unavailable: {error}")
            self.observe(workspace, "unavailable")
            lock.unlink()
            lock.symlink_to(lock.with_name("missing-lock.json"))
            self.observe(workspace, "unavailable")
            lock.unlink()
            original.rename(lock)
            mods = instance / "mods"
            moved = instance / "original-mods"
            mods.rename(moved)
            mods.symlink_to(moved, target_is_directory=True)
            self.observe(workspace, "unavailable")
            mods.unlink()
            mods.symlink_to(instance / "missing-mods", target_is_directory=True)
            self.observe(workspace, "unavailable")
            mods.unlink()
            moved.rename(mods)
            self.observe(workspace, "match")
            metadata = instance / "metadata"
            moved_metadata = instance / "original-metadata"
            metadata.rename(moved_metadata)
            metadata.symlink_to(moved_metadata, target_is_directory=True)
            report = call(workspace, "saves", "inspect", "world.zip", "--instance", "save-index")
            self.assertEqual("unavailable", report["saves"][0]["association"]["context"]["status"])
            metadata.unlink()
            metadata.symlink_to(instance / "missing-metadata", target_is_directory=True)
            report = call(workspace, "saves", "inspect", "world.zip", "--instance", "save-index")
            self.assertEqual("unavailable", report["saves"][0]["association"]["context"]["status"])
            metadata.unlink()
            moved_metadata.rename(metadata)
            self.observe(workspace, "match")


if __name__ == "__main__":
    unittest.main()
