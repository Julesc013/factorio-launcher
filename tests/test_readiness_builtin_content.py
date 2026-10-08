# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT
from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from native_cli import invoke_machine
from test_local_modset_solver import FIXTURE_INSTALL, call, snapshot, write_mod
from test_save_index_retention import write_save
from tests.windows_junction import create_junction


class ReadinessBuiltinContentTests(unittest.TestCase):
    def prepare(self, workspace: Path, mixed: bool = False) -> tuple[Path, Path]:
        call(workspace, "installs", "import", str(FIXTURE_INSTALL), "--id", "bootstrap")
        # Mutations are confined to this small owned fixture, never the source fixture.
        install = workspace / "fixture-install"
        shutil.copytree(FIXTURE_INSTALL, install)
        call(workspace, "installs", "import", str(install), "--id", "fixture")
        call(workspace, "instances", "create", "Main", "--id", "main", "--install", "fixture")
        instance = workspace / "instances/main"
        if mixed:
            write_mod(instance / "mods/simple_1.0.0.zip", "simple", "1.0.0")
        call(workspace, "modsets", "apply", "main", "--enable", "simple" if mixed else "base")
        self.assertEqual([], call(workspace, "modsets", "verify", "main")["problems"])
        return instance, install

    def query(self, workspace: Path, scope: str = "instances", intent: str = "menu") -> dict:
        code, out, err = invoke_machine(["--workspace", str(workspace), "presentation", "query",
                                         scope, "--instance", "main", "--intent", intent, "--json"])
        self.assertEqual((code, err), (0, ""), out)
        return json.loads(out)["payload"]

    def test_builtin_and_mixed_solver_locks_are_verified_read_only(self) -> None:
        for mixed in (False, True):
            with self.subTest(mixed=mixed), tempfile.TemporaryDirectory(prefix="ready-builtin-") as value:
                workspace = Path(value)
                _, install = self.prepare(workspace, mixed)
                before = snapshot(workspace)
                for scope in ("instances", "launch_deck"):
                    ready = self.query(workspace, scope)["readiness"]
                    mods = ready["preparation_preview"]["modset"]
                    self.assertEqual("locked_verified", mods["status"])
                    self.assertEqual("observation_only", mods["disposition"])
                    self.assertEqual("satisfied", next(d["state"] for d in ready["dimensions"]
                                                       if d["id"] == "mod_content"))
                    self.assertEqual("degraded", ready["configuration_state"])
                    self.assertEqual("degraded", next(d["state"] for d in ready["dimensions"]
                                                      if d["id"] == "environment"))
                    self.assertEqual(["real_play_gate_not_passed"], [b["code"] for b in ready["blockers"]])
                    self.assertTrue(any(hashlib.sha256((install / "data/base/info.json").read_bytes()).hexdigest()
                                        in identity for identity in mods["artifact_identities"]))
                    self.assertFalse(ready["preparation_available"])
                    self.assertFalse(ready["execution_available"])
                    self.assertEqual("unavailable", ready["play_authority_state"])
                self.assertEqual(before, snapshot(workspace))

    def test_builtin_raw_metadata_identity_invalidates_reviewed_snapshot(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ready-builtin-stale-") as value:
            workspace = Path(value)
            _, install = self.prepare(workspace)
            old = self.query(workspace)
            metadata = install / "data/base/info.json"
            metadata.write_bytes(metadata.read_bytes() + b"\n")
            self.assertEqual([], call(workspace, "modsets", "verify", "main")["problems"])
            before = snapshot(workspace)
            fresh = self.query(workspace)
            self.assertEqual("locked_verified", fresh["readiness"]["preparation_preview"]["modset"]["status"])
            self.assertNotEqual(old["readiness"]["instance_binding_digest"],
                                fresh["readiness"]["instance_binding_digest"])
            self.assertNotEqual(old["revision"], fresh["revision"])
            code, out, err = invoke_machine(["--workspace", str(workspace), "presentation", "action",
                "readiness.refresh", "--scope", "instances", "--instance", "main",
                "--expected-revision", old["revision"], "--request-id", "stale-builtin",
                "--idempotency-key", "stale-builtin", "--json"])
            self.assertEqual((code, err), (1, ""), out)
            self.assertEqual("stale_snapshot_revision", json.loads(out)["error"]["code"])
            self.assertEqual(before, snapshot(workspace))

    def test_forged_virtual_source_and_changed_builtin_metadata_stay_blocked(self) -> None:
        for mutation in ("foreign-source", "archive-as-virtual", "builtin-version",
                         "missing-metadata", "malformed-metadata", "oversized-metadata", "hardlinked-metadata"):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory(prefix="ready-builtin-refuse-") as value:
                workspace = Path(value)
                instance, install = self.prepare(workspace, mixed=True)
                metadata = install / "data/base/info.json"
                if mutation == "missing-metadata":
                    metadata.unlink()
                elif mutation == "malformed-metadata":
                    metadata.write_bytes(b"{invalid builtin metadata\n")
                elif mutation == "oversized-metadata":
                    metadata.write_bytes(b" " * (1024 * 1024 + 1))
                elif mutation == "hardlinked-metadata":
                    os.link(metadata, workspace / "metadata-alias.json")
                elif mutation == "builtin-version":
                    document = json.loads(metadata.read_text())
                    document["version"] = "2.0.78"
                    metadata.write_text(json.dumps(document) + "\n", encoding="utf-8")
                else:
                    local = instance / "mods/modset-lock.v1.json"
                    document = json.loads(local.read_text())
                    entry = next(item for item in document["mods"]
                                 if item["name"] == ("base" if mutation == "foreign-source" else "simple"))
                    entry.update(source="install-data:other" if mutation == "foreign-source" else "install-data:fixture",
                                 sha256="", sha1="", metadata_source="builtin_info_json",
                                 validation_status="virtual", virtual_package=True)
                    for path in (local, workspace / "modsets/main.modset-lock.v1.json"):
                        path.write_text(json.dumps(document) + "\n", encoding="utf-8")
                before = snapshot(workspace)
                ready = self.query(workspace)["readiness"]
                self.assertEqual("blocked", ready["configuration_state"])
                self.assertEqual("plan_unavailable", ready["preparation_preview"]["modset"]["disposition"])
                for dependency in ready["dependency_identities"]:
                    if dependency["kind"] == "modset_artifact" and ":unavailable:" in dependency["identity"]:
                        self.assertEqual("unavailable", dependency["state"])
                self.assertFalse(ready["execution_available"])
                self.assertEqual(before, snapshot(workspace))

    def test_selected_save_projection_binds_builtin_metadata_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ready-builtin-save-") as value:
            workspace = Path(value)
            instance, install = self.prepare(workspace, mixed=True)
            write_save(instance / "saves/selected.zip", b"selected world")
            call(workspace, "profiles", "apply", "main", "gui", "--selection-mode", "load-save",
                 "--selection", "selected.zip", "--arg", "--low-vram")
            old = self.query(workspace, intent="load_save")["readiness"]
            self.assertEqual("locked_verified", old["preparation_preview"]["modset"]["status"])
            self.assertEqual("degraded", old["selected_save"]["state"])
            metadata = install / "data/base/info.json"
            metadata.write_bytes(metadata.read_bytes() + b"\n")
            before = snapshot(workspace)
            fresh = self.query(workspace, intent="load_save")["readiness"]
            self.assertNotEqual(old["instance_binding_digest"], fresh["instance_binding_digest"])
            self.assertEqual("selected.zip", fresh["selected_save"]["filename"])
            self.assertFalse(fresh["preparation_executed"])
            self.assertEqual(before, snapshot(workspace))

    def test_linked_builtin_package_does_not_bind_external_metadata_as_evidence(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ready-builtin-link-") as value:
            workspace = Path(value)
            _, install = self.prepare(workspace)
            package = install / "data/base"
            retained = install / "data/retained-base"
            package.rename(retained)
            outside = workspace / "outside-package"
            outside.mkdir()
            marker = b'{"name":"base","version":"2.0.77","private":"never hash me"}\n'
            (outside / "info.json").write_bytes(marker)
            try:
                try:
                    package.symlink_to(outside, target_is_directory=True)
                except OSError:
                    if os.name != "nt":
                        raise
                    create_junction(package, outside)
                before = snapshot(workspace)
                ready = self.query(workspace)["readiness"]
                self.assertEqual("blocked", ready["configuration_state"])
                self.assertNotIn(hashlib.sha256(marker).hexdigest(), json.dumps(ready))
                self.assertEqual(before, snapshot(workspace))
            finally:
                if package.is_symlink():
                    package.unlink()
                elif package.exists():
                    package.rmdir()  # Remove the junction itself; never its target.


if __name__ == "__main__":
    unittest.main()
