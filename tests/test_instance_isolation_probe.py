# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import hashlib
import io
import json
import os
import shutil
import subprocess
import tempfile
import time
import unittest
import sys
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from native_cli import facman_executable, invoke

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_INSTALL = ROOT / "tests" / "fixtures" / "fake_factorio_install"
sys.path.insert(0, str(ROOT / "tools"))
import json_contract  # noqa: E402
import real_factorio_isolation_smoke as real_smoke  # noqa: E402

PROBE_SCHEMA = json_contract.load_schema(
    ROOT / "contracts" / "schema" / "factorio" / "factorio_isolation_probe.v1.schema.json"
)


def tree_snapshot(root: Path) -> dict[str, str]:
    if not root.exists():
        return {}
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(item for item in root.rglob("*") if item.is_file())
    }


def isolation_probe_executable() -> Path:
    explicit = os.environ.get("FACMAN_ISOLATION_PROBE_EXE")
    if explicit:
        path = Path(explicit)
        if path.is_file():
            return path
        raise AssertionError(f"FACMAN_ISOLATION_PROBE_EXE does not point to a file: {path}")
    suffix = ".exe" if os.name == "nt" else ""
    candidate = facman_executable().with_name(f"facman_isolation_probe{suffix}")
    if candidate.is_file():
        return candidate
    matches = sorted(
        ROOT.glob(f"build/**/facman_isolation_probe{suffix}"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    if matches:
        return matches[0]
    raise unittest.SkipTest("facman isolation probe has not been built")


class InstanceIsolationProbeTests(unittest.TestCase):
    def make_workspace(self, root: Path) -> tuple[Path, Path, Path]:
        long_component = "long-" + ("x" * 52)
        workspace = (
            root
            / "workspace with spaces"
            / "unicode-\N{SNOWMAN}"
        )
        projected_instance = workspace / "instances" / "isolation-probe"
        while len(str(projected_instance)) <= 300:
            workspace /= long_component
            projected_instance = workspace / "instances" / "isolation-probe"
        workspace /= "workspace"
        install_root = root / "protected foreign install"
        shutil.copytree(FIXTURE_INSTALL, install_root)
        code, _stdout, stderr = invoke(
            ["--workspace", str(workspace), "installs", "import", str(install_root), "--id", "probe"]
        )
        self.assertEqual(code, 0, stderr)
        code, stdout, stderr = invoke(
            [
                "--workspace",
                str(workspace),
                "instances",
                "create",
                "Isolation Probe",
                "--install",
                "probe",
                "--json",
            ]
        )
        self.assertEqual(code, 0, stderr)
        instance = json.loads(stdout)
        instance_root = Path(instance["local_data_root"])
        self.assertGreater(len(str(instance_root)), 260)
        return workspace, install_root, instance_root

    def preview(self, workspace: Path) -> dict:
        code, stdout, stderr = invoke(
            ["--workspace", str(workspace), "run", "isolation-probe", "--json"]
        )
        self.assertEqual(code, 0, stderr)
        return json.loads(stdout)

    def preflight(self, workspace: Path) -> dict:
        code, stdout, stderr = invoke(
            [
                "--workspace",
                str(workspace),
                "launch-plan",
                "isolation-probe",
                "--preflight",
                "--json",
            ]
        )
        self.assertEqual(code, 0, stderr)
        return json.loads(stdout)

    def probe_command(
        self,
        preview: dict,
        instance_root: Path,
        report_path: Path,
        hold_ms: int = 0,
    ) -> list[str]:
        args = preview["args"]
        config_index = args.index("--config") + 1
        mod_index = args.index("--mod-directory") + 1
        return [
            str(isolation_probe_executable()),
            "--config",
            args[config_index],
            "--mod-directory",
            args[mod_index],
            "--instance-root",
            str(instance_root),
            "--read-data-root",
            preview["effective_config"]["read_data"],
            "--report",
            str(report_path),
            "--hold-ms",
            str(hold_ms),
        ]

    def test_probe_preserves_protected_roots_and_reports_effective_isolation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workspace, install_root, instance_root = self.make_workspace(root)
            preview = self.preview(workspace)
            preflight = self.preflight(workspace)
            self.assertEqual(preflight["status"], "pass")
            self.assertEqual(preview["effective_config"], preflight["effective_config"])

            config_text = (instance_root / "config" / "config.ini").read_text(encoding="utf-8")
            self.assertIn(f"read-data={install_root / 'data'}", config_text)
            self.assertIn(f"write-data={instance_root}", config_text)
            self.assertFalse((instance_root / "config" / "config-path.cfg").exists())

            protected = root / "protected environment"
            appdata = protected / "AppData" / "Roaming"
            localappdata = protected / "AppData" / "Local"
            home = protected / "Home"
            for directory in [
                appdata / "Factorio",
                localappdata / "Factorio",
                home / ".factorio",
            ]:
                directory.mkdir(parents=True)
                directory.joinpath("sentinel.txt").write_text("protected\n", encoding="utf-8")
            protected_before = tree_snapshot(protected)
            install_before = tree_snapshot(install_root)

            report_path = instance_root / "logs" / "isolation-probe-report.json"
            cwd = root / "arbitrary cwd \N{SNOWMAN}"
            cwd.mkdir()
            env = os.environ.copy()
            env.update(
                {
                    "APPDATA": str(appdata),
                    "LOCALAPPDATA": str(localappdata),
                    "HOME": str(home),
                    "USERPROFILE": str(home),
                }
            )
            completed = subprocess.run(
                self.probe_command(preview, instance_root, report_path),
                cwd=cwd,
                env=env,
                check=False,
                text=True,
                encoding="utf-8",
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr or completed.stdout)
            report = json.loads(completed.stdout)
            self.assertEqual(json_contract.validate(report, PROBE_SCHEMA), [])
            self.assertEqual(report, json.loads(report_path.read_text(encoding="utf-8")))
            self.assertEqual(report["status"], "pass")
            self.assertEqual(report["current_directory"], str(cwd))
            self.assertEqual(report["resolved_config"], {
                "config_file": str(instance_root / "config" / "config.ini"),
                "read_data": str(install_root / "data"),
                "write_data": str(instance_root),
            })
            self.assertEqual(report["intended_write_root"], str(instance_root))
            self.assertEqual(report["intended_mod_root"], str(instance_root / "mods"))
            self.assertTrue(report["lock"]["acquired"])
            self.assertFalse((instance_root / "locks" / "run.lock").exists())
            for attempted in report["attempted_writes"]:
                self.assertTrue(Path(attempted).is_relative_to(instance_root), attempted)
            self.assertEqual(tree_snapshot(protected), protected_before)
            self.assertEqual(tree_snapshot(install_root), install_before)

    def test_probe_lock_contention_is_structured(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workspace, _install_root, instance_root = self.make_workspace(root)
            preview = self.preview(workspace)
            first_report = instance_root / "logs" / "probe-first.json"
            second_report = instance_root / "logs" / "probe-second.json"
            first = subprocess.Popen(
                self.probe_command(preview, instance_root, first_report, hold_ms=1500),
                cwd=root,
                text=True,
                encoding="utf-8",
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            lock_path = instance_root / "locks" / "run.lock"
            deadline = time.monotonic() + 5
            while not lock_path.exists() and time.monotonic() < deadline:
                time.sleep(0.02)
            self.assertTrue(lock_path.is_file())
            second = subprocess.run(
                self.probe_command(preview, instance_root, second_report),
                cwd=root,
                check=False,
                text=True,
                encoding="utf-8",
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            self.assertEqual(second.returncode, 4)
            refusal = json.loads(second.stdout)
            self.assertEqual(json_contract.validate(refusal, PROBE_SCHEMA), [])
            self.assertEqual(refusal["code"], "run_lock_contended")
            self.assertEqual(refusal["attempted_writes"], [])
            first_stdout, first_stderr = first.communicate(timeout=5)
            self.assertEqual(first.returncode, 0, first_stderr or first_stdout)
            self.assertFalse(lock_path.exists())

    def test_real_factorio_harness_prepares_pending_evidence_and_requires_ack(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workspace, _install_root, instance_root = self.make_workspace(root)
            preview = self.preview(workspace)
            evidence_path = root / "operator-evidence.json"
            base_command = [
                sys.executable,
                str(ROOT / "tools" / "real_factorio_isolation_smoke.py"),
                "--facman",
                str(facman_executable()),
                "--workspace",
                str(workspace),
                "--instance-id",
                "isolation-probe",
                "--factorio-exe",
                preview["executable"],
                "--evidence-out",
                str(evidence_path),
            ]
            prepared = subprocess.run(
                base_command,
                check=False,
                text=True,
                encoding="utf-8",
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            self.assertEqual(prepared.returncode, 0, prepared.stderr or prepared.stdout)
            evidence = json.loads(prepared.stdout)
            self.assertEqual(evidence["status"], "prepared")
            self.assertEqual(evidence["operator_verdict"], "pending")
            self.assertEqual(evidence["schema"], "facman.real_factorio_isolation_smoke.v2")
            self.assertEqual(
                evidence["identity"]["facman_executable"]["sha256"],
                hashlib.sha256(facman_executable().read_bytes()).hexdigest(),
            )
            self.assertEqual(evidence["identity"]["facman_version"]["exit_status"], 0)
            self.assertEqual(
                evidence["identity"]["factorio_executable"]["sha256"],
                hashlib.sha256(Path(preview["executable"]).read_bytes()).hexdigest(),
            )
            self.assertEqual(
                evidence["identity"]["factorio_version"]["status"],
                "not_run_in_prepare_mode",
            )
            self.assertEqual(
                evidence["identity"]["effective_config_file"]["sha256"],
                hashlib.sha256(
                    Path(preview["effective_config"]["config_file"]).read_bytes()
                ).hexdigest(),
            )
            self.assertTrue(
                all(
                    value["revision"]
                    for value in evidence["identity"]["repositories"].values()
                )
            )
            self.assertEqual(
                evidence["system_wide_write_observation"]["review_status"], "pending"
            )
            self.assertEqual(evidence, json.loads(evidence_path.read_text(encoding="utf-8")))
            self.assertFalse((instance_root / "locks" / "run.lock").exists())

            unacknowledged = subprocess.run(
                [*base_command, "--execute-smoke"],
                check=False,
                text=True,
                encoding="utf-8",
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            self.assertEqual(unacknowledged.returncode, 2)
            self.assertIn("--acknowledge must exactly equal", unacknowledged.stderr)
            self.assertFalse((instance_root / "locks" / "run.lock").exists())

    def test_real_smoke_snapshot_is_bounded_no_follow_and_reports_detailed_diff(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            protected = root / "protected"
            kept = protected / "kept"
            removed = protected / "removed"
            kept.mkdir(parents=True)
            removed.mkdir()
            kept.joinpath("modified.txt").write_text("before\n", encoding="utf-8")
            removed.joinpath("deleted.txt").write_text("deleted\n", encoding="utf-8")
            before = real_smoke.snapshot(protected)
            self.assertTrue(before["complete"])

            kept.joinpath("modified.txt").write_text("after\n", encoding="utf-8")
            removed.joinpath("deleted.txt").unlink()
            removed.rmdir()
            created = protected / "created"
            created.mkdir()
            created.joinpath("new.txt").write_text("created\n", encoding="utf-8")
            after = real_smoke.snapshot(protected)
            difference = real_smoke.snapshot_diff(before, after)

            self.assertTrue(difference["complete"])
            self.assertTrue(difference["changed"])
            self.assertEqual(difference["created_directories"], ["created"])
            self.assertEqual(difference["deleted_directories"], ["removed"])
            self.assertEqual(difference["created_files"][0]["path"], "created/new.txt")
            self.assertIsNone(difference["created_files"][0]["before_sha256"])
            self.assertEqual(difference["deleted_files"][0]["path"], "removed/deleted.txt")
            self.assertIsNone(difference["deleted_files"][0]["after_sha256"])
            self.assertEqual(difference["modified_files"][0]["path"], "kept/modified.txt")
            self.assertNotEqual(
                difference["modified_files"][0]["before_sha256"],
                difference["modified_files"][0]["after_sha256"],
            )

            limited = real_smoke.snapshot(protected, max_files=1)
            self.assertFalse(limited["complete"])
            self.assertTrue(
                any(
                    item["reason"] == "file_count_limit_exceeded"
                    for item in limited["omitted_entries"]
                )
            )
            byte_limited = real_smoke.snapshot(protected, max_bytes=1)
            self.assertFalse(byte_limited["complete"])
            self.assertTrue(
                any(
                    item["reason"] == "byte_limit_exceeded"
                    for item in byte_limited["omitted_entries"]
                )
            )
            ticks = [0.0]

            def advancing_clock() -> float:
                ticks[0] += 1.0
                return ticks[0]

            with patch.object(real_smoke.time, "monotonic", side_effect=advancing_clock):
                time_limited = real_smoke.snapshot(protected, max_seconds=2.0)
            self.assertFalse(time_limited["complete"])
            self.assertTrue(
                any(
                    item["reason"] == "elapsed_time_limit_exceeded"
                    for item in time_limited["omitted_entries"]
                )
            )

            link = protected / "outside-link"
            outside = root / "outside"
            outside.mkdir()
            try:
                link.symlink_to(outside, target_is_directory=True)
            except OSError:
                pass
            else:
                linked = real_smoke.snapshot(protected)
                self.assertFalse(linked["complete"])
                self.assertTrue(
                    any(
                        item["path"] == "outside-link"
                        and item["reason"] == "link_or_reparse_refused"
                        for item in linked["omitted_entries"]
                    )
                )
                nested = real_smoke.snapshot(link / "nested")
                self.assertFalse(nested["complete"])
                self.assertEqual(
                    nested["omitted_entries"][0]["reason"],
                    "root_link_or_reparse_refused",
                )

    def test_real_smoke_process_supervision_records_timeout_and_termination(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            report = real_smoke.supervise_process(
                [sys.executable, "-c", "import time; time.sleep(5)"],
                cwd=Path(tmp),
                timeout_seconds=0.2,
                termination_grace_seconds=0.2,
            )
            self.assertTrue(report["timed_out"])
            self.assertTrue(report["termination_requested"])
            self.assertIsNotNone(report["exit_status"])
            self.assertLess(report["duration_seconds"], 3)
            self.assertTrue(report["started_utc"].endswith("Z"))
            self.assertTrue(report["ended_utc"].endswith("Z"))

    def test_factorio_version_invocation_is_inside_protected_snapshot_window(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            facman = root / "facman.exe"
            factorio = root / "factorio.exe"
            facman.write_bytes(b"facman")
            factorio.write_bytes(b"factorio")
            app_root = root / "install"
            protected = root / "protected"
            instance_root = root / "instance"
            config = instance_root / "config" / "config.ini"
            for directory in [app_root, protected, config.parent, instance_root / "locks"]:
                directory.mkdir(parents=True, exist_ok=True)
            config.write_text("[path]\n", encoding="utf-8")
            evidence_path = root / "evidence.json"
            preview = {
                "executable": str(factorio),
                "app_dir": str(app_root),
                "args": ["--config", str(config)],
                "effective_config": {
                    "config_file": str(config),
                    "read_data": str(app_root / "data"),
                    "write_data": str(instance_root),
                    "mod_root": str(instance_root / "mods"),
                    "save_root": str(instance_root / "saves"),
                    "script_output_root": str(instance_root / "script-output"),
                    "log_root": str(instance_root / "logs"),
                },
            }
            preflight = {"status": "pass", "effective_config": preview["effective_config"]}

            def version_identity(command: list[str], _timeout: float) -> dict:
                if Path(command[0]) == factorio:
                    protected.joinpath("version-write.txt").write_text(
                        "observed\n", encoding="utf-8"
                    )
                return {
                    "command": command,
                    "started_utc": "2026-07-11T00:00:00Z",
                    "ended_utc": "2026-07-11T00:00:01Z",
                    "exit_status": 0,
                    "timed_out": False,
                    "termination_requested": False,
                    "killed_after_timeout": False,
                    "stdout": "version",
                    "stderr": "",
                }

            clean_process = {
                "command": [str(factorio)],
                "process_id": 123,
                "started_utc": "2026-07-11T00:00:01Z",
                "ended_utc": "2026-07-11T00:00:02Z",
                "duration_seconds": 1.0,
                "exit_status": 0,
                "timed_out": False,
                "operator_interrupted": False,
                "termination_requested": False,
                "killed_after_grace_period": False,
                "termination_grace_seconds": 1.0,
                "child_process_observation": {"status": "observed", "processes": []},
            }
            revisions = {
                name: {"revision": "a" * 40, "source": "test"}
                for name in ["factorio_launcher", "universal_launcher", "universal_setup"]
            }
            argv = [
                "real_factorio_isolation_smoke.py",
                "--facman",
                str(facman),
                "--workspace",
                str(root / "workspace"),
                "--instance-id",
                "smoke",
                "--factorio-exe",
                str(factorio),
                "--protected-root",
                str(protected),
                "--evidence-out",
                str(evidence_path),
                "--execute-smoke",
                "--acknowledge",
                real_smoke.ACKNOWLEDGEMENT,
            ]
            with (
                patch.object(sys, "argv", argv),
                patch.object(real_smoke, "run_json", side_effect=[preview, preflight]),
                patch.object(real_smoke, "run_command_identity", side_effect=version_identity),
                patch.object(real_smoke, "repository_revisions", return_value=revisions),
                patch.object(real_smoke, "supervise_process", return_value=clean_process),
                redirect_stdout(io.StringIO()),
                redirect_stderr(io.StringIO()),
            ):
                code = real_smoke.main()
            self.assertEqual(code, 1)
            evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
            protected_diff = evidence["protected_snapshots"][str(protected)]["diff"]
            self.assertEqual(
                protected_diff["created_files"][0]["path"], "version-write.txt"
            )
            self.assertEqual(
                evidence["automated_observation"], "protected_root_change_detected"
            )
            self.assertEqual(evidence["operator_verdict"], "pending")

    def test_real_smoke_write_observation_records_artifact_and_classifications(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            artifact = root / "procmon-trace.pml"
            artifact.write_bytes(b"trace")
            classification = root / "classifications.json"
            classification.write_text(
                json.dumps(
                    [
                        {
                            "path": "<instance>/saves/smoke.zip",
                            "classification": "instance-local",
                        },
                        {
                            "path": "<outside>/unresolved.tmp",
                            "classification": "unresolved",
                        },
                    ]
                ),
                encoding="utf-8",
            )
            args = real_smoke.build_parser().parse_args(
                [
                    "--facman",
                    "facman.exe",
                    "--workspace",
                    "workspace",
                    "--instance-id",
                    "smoke",
                    "--factorio-exe",
                    "factorio.exe",
                    "--evidence-out",
                    "evidence.json",
                    "--write-observation-method",
                    "procmon",
                    "--write-observation-artifact",
                    str(artifact),
                    "--write-observation-classification",
                    str(classification),
                ]
            )
            observation = real_smoke.write_observation(args)
            self.assertEqual(
                observation["artifact"]["sha256"], hashlib.sha256(b"trace").hexdigest()
            )
            self.assertEqual(observation["review_status"], "unexpected_or_unresolved")

    def test_preflight_refuses_malformed_missing_mismatched_and_reparse_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workspace, install_root, instance_root = self.make_workspace(root)
            config_file = instance_root / "config" / "config.ini"
            original = config_file.read_text(encoding="utf-8")

            config_file.write_text("[path]\nwrite-data=relative\n", encoding="utf-8")
            report = self.preflight(workspace)
            self.assertEqual(report["status"], "refused")
            self.assertTrue(any("missing read-data" in problem for problem in report["problems"]))
            self.assertTrue(any("relative config path" in problem for problem in report["problems"]))

            config_file.unlink()
            report = self.preflight(workspace)
            self.assertEqual(report["status"], "refused")
            self.assertTrue(any("config file is missing" in problem for problem in report["problems"]))

            appdata = root / "sensitive" / "AppData"
            sensitive = appdata / "Factorio"
            sensitive.mkdir(parents=True)
            config_file.write_text(
                f"[path]\nread-data={install_root / 'data'}\nwrite-data={sensitive}\n",
                encoding="utf-8",
            )
            with patch.dict(os.environ, {"APPDATA": str(appdata)}):
                report = self.preflight(workspace)
            self.assertEqual(report["status"], "refused")
            self.assertTrue(any("default or global" in problem for problem in report["problems"]))

            config_file.write_text(
                f"[path]\nread-data={install_root / 'data'}\nwrite-data={install_root}\n",
                encoding="utf-8",
            )
            report = self.preflight(workspace)
            self.assertEqual(report["status"], "refused")
            self.assertTrue(any("product install root" in problem for problem in report["problems"]))

            config_file.write_text(original, encoding="utf-8")
            if os.name == "nt":
                real_config = instance_root / "config-real"
                (instance_root / "config").rename(real_config)
                external_config = root / "external-config"
                shutil.copytree(real_config, external_config)
                completed = subprocess.run(
                    ["cmd", "/c", "mklink", "/J", str(instance_root / "config"), str(external_config)],
                    check=False,
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
                self.assertEqual(completed.returncode, 0, completed.stderr or completed.stdout)
                report = self.preflight(workspace)
                self.assertEqual(report["status"], "refused")
                self.assertTrue(any("reparse point" in problem for problem in report["problems"]))

                (instance_root / "config").rmdir()
                real_config.rename(instance_root / "config")
                real_mods = instance_root / "mods-real"
                (instance_root / "mods").rename(real_mods)
                external_mods = root / "external-mods"
                external_mods.mkdir()
                completed = subprocess.run(
                    ["cmd", "/c", "mklink", "/J", str(instance_root / "mods"), str(external_mods)],
                    check=False,
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
                self.assertEqual(completed.returncode, 0, completed.stderr or completed.stdout)
                report = self.preflight(workspace)
                self.assertEqual(report["status"], "refused")
                self.assertTrue(any("reparse point" in problem for problem in report["problems"]))


if __name__ == "__main__":
    unittest.main()
