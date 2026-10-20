# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import copy
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from test_save_association_context import inventory
from test_save_index_retention import call, setup, write_save
from tools.winforms_build import msbuild_executable


ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "tests/winforms_control_gallery/FacMan.SaveContext.Harness.csproj"


@unittest.skipUnless(os.name == "nt", "not_applicable: WinForms requires Windows")
class WinFormsSaveAssociationContextTests(unittest.TestCase):
    def test_owner_observations_survive_projection_and_rendering(self) -> None:
        with tempfile.TemporaryDirectory(prefix="facman saves view ") as directory:
            root = Path(directory)
            workspace = root / "workspace"
            instance = setup(workspace)
            save = instance / "saves/world.zip"
            write_save(save, b"opaque save view fixture")
            original_save = save.read_bytes()
            lock = instance / "mods/modset-lock.v1.json"
            original_lock = b'{"mods":[]}\n'
            lock.write_bytes(original_lock)
            call(workspace, "saves", "associate", "world.zip", "--instance", "save-index")
            sidecar = instance / "metadata/save-refs/world.zip.save-ref.v1.json"
            original_sidecar = sidecar.read_bytes()
            manifest = instance / "instance.v1.json"
            original_manifest = manifest.read_bytes()
            before = inventory(workspace)
            snapshots = {
                scope: call(workspace, "presentation", "query", scope, "--instance", "save-index")
                for scope in ("launch_deck", "instances", "installations", "content",
                              "saves", "activity_recovery", "settings_support")
            }
            self.assertEqual(before, inventory(workspace))
            cases: list[dict] = []

            def capture(name: str, context: str, version: str, content: str, byte_status: str = "current") -> None:
                before_query = inventory(workspace)
                snapshots["saves"] = call(workspace, "presentation", "query", "saves", "--instance", "save-index")
                self.assertEqual(before_query, inventory(workspace))
                owner = snapshots["saves"]["page"]["items"][0]
                self.assertEqual(byte_status, owner["association_status"])
                observed = owner["association_context"]
                self.assertEqual(context, observed["status"])
                self.assertEqual(version, observed["factorio_version"]["status"])
                self.assertEqual(content, observed["modset_lock"]["status"])
                cases.append(dict(name=name, gallery=dict(schema="facman.control_gallery_case.v1",
                    state="blocked", variant=name, observed_at="2026-10-05T00:00:00Z", snapshots=copy.deepcopy(snapshots)),
                    expected=dict(association_status=byte_status, association_context_status=context,
                        association_version_status=version, association_modset_status=content)))

            capture("match", "match", "match", "match")
            record = json.loads(original_manifest)
            record["factorio_version"] = "2.0.78"
            manifest.write_text(json.dumps(record) + "\n", encoding="utf-8")
            capture("version-drift", "drifted", "drifted", "match")
            manifest.write_bytes(original_manifest)
            lock.write_bytes(b'{"mods":[],"changed":true}\n')
            capture("content-drift", "drifted", "match", "drifted")
            lock.write_bytes(original_lock)
            record = json.loads(original_sidecar)
            record.pop("factorio_version")
            record["modset_lock_sha256"] = ""
            sidecar.write_text(json.dumps(record) + "\n", encoding="utf-8")
            capture("legacy-unknown", "unknown", "unknown", "unknown")
            sidecar.write_bytes(original_sidecar)
            peer = instance / "mods/lock-peer.json"
            os.link(lock, peer)
            capture("context-unavailable", "unavailable", "match", "unavailable")
            peer.unlink()
            write_save(save, b"changed opaque save view fixture")
            capture("byte-drift-context-match", "match", "match", "match", "drifted")
            save.write_bytes(original_save)
            legacy = copy.deepcopy(cases[0])
            legacy["name"] = legacy["gallery"]["variant"] = "optional-context-absent"
            del legacy["gallery"]["snapshots"]["saves"]["page"]["items"][0]["association_context"]
            for field in ("association_context_status", "association_version_status", "association_modset_status"):
                legacy["expected"][field] = ""
            cases.append(legacy)
            before_render = inventory(workspace)
            fixture = root / "cases.json"
            fixture.write_text(json.dumps(dict(cases=cases), ensure_ascii=False) + "\n", encoding="utf-8")
            output = root / "bin"
            intermediate = root / "obj"
            build = subprocess.run([msbuild_executable(), str(PROJECT), "/m:2", "/nr:false",
                "/p:Configuration=Debug", "/p:Platform=x64", f"/p:OutputPath={output}{os.sep}",
                f"/p:IntermediateOutputPath={intermediate}{os.sep}", f"/p:BaseIntermediateOutputPath={intermediate}{os.sep}"],
                cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180)
            evidence_value = os.environ.get("FACMAN_WINFORMS_SAVE_CONTEXT_EVIDENCE_DIR", "")
            evidence = Path(evidence_value) if evidence_value else None
            if evidence is not None:
                self.assertTrue(evidence.is_dir())
                (evidence / "build.log").write_text(build.stdout + build.stderr, encoding="utf-8")
                shutil.copyfile(fixture, evidence / "cases.json")
            self.assertEqual(0, build.returncode, build.stdout + build.stderr)
            binary = output / "FacMan.SaveContext.Harness.exe"
            rendered_output = []
            for index, case in enumerate(cases):
                # The gallery consumes one observation, not the aggregate of
                # seven independent cases. Preserve its existing size bound.
                case_fixture = root / f"case-{index}.json"
                document = json.dumps(dict(cases=[case]), ensure_ascii=False) + "\n"
                self.assertLessEqual(len(document), 1024 * 1024, case["name"])
                case_fixture.write_text(document, encoding="utf-8")
                result = subprocess.run([str(binary), str(case_fixture)], cwd=root, capture_output=True,
                    text=True, encoding="utf-8", errors="replace", timeout=60)
                rendered_output.append(result.stdout + result.stderr)
                if evidence is not None:
                    (evidence / "run.log").write_text("".join(rendered_output), encoding="utf-8")
                self.assertEqual(0, result.returncode, case["name"] + ": " + result.stdout + result.stderr)
                self.assertEqual(1, result.stdout.count("PASS "), case["name"])
            if evidence is not None:
                identities = {}
                for name in ("FacMan.exe", "FacMan.SaveContext.Harness.exe"):
                    path = output / name
                    identities[name] = hashlib.sha256(path.read_bytes()).hexdigest()
                    shutil.copyfile(path, evidence / name)
                (evidence / "binary-identities.json").write_text(json.dumps(identities, indent=2) + "\n", encoding="utf-8")
            self.assertEqual(7, "".join(rendered_output).count("PASS "))
            self.assertEqual(before_render, inventory(workspace))
            self.assertEqual(original_sidecar, sidecar.read_bytes())
            print("".join(rendered_output), end="")


if __name__ == "__main__":
    unittest.main()
