# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT
"""Bounded adapters for the three existing-owner reconstruction scenarios."""
from __future__ import annotations

import base64
import ctypes
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import types
import unittest
import zlib
from contextlib import ExitStack
from unittest.mock import patch

import native_cli
import test_environment_reconstruction as source
import test_local_modset_solver as solver
import test_macos_delivered_tui as macos
from tools import package_hash_manifest

SCENARIOS = (
    "test_clean_workspace_reconstructs_declared_content_profile_world_and_joined_context",
    "test_reconstructed_world_context_interruption_recovers_without_reimporting_or_recloning",
    "test_reconstruction_owners_preserve_foreign_destinations_and_refuse_invalid_inputs",
)
MAX_CALLS = 64
MAX_SECONDS = 300


class EnvironmentConsumerDriver(macos.PackConsumerDriver):
    def __init__(self, owner, scenario: str, consumer: Path, executable: Path, evidence: Path):
        self.context = types.SimpleNamespace(consumer=consumer, executable=executable,
            assertTrue=owner.assertTrue, assertLess=owner.assertLess,
            assertEqual=owner.assertEqual, assertIn=owner.assertIn,
            assertLessEqual=owner.assertLessEqual)
        hooks = {"FACMAN_TEST_SELECTED_CONTEXT_EXIT": {"after_publication"}} if scenario == SCENARIOS[1] else {}
        super().__init__(self.context, scenario, fault_controls=hooks)
        self.evidence, self.scenario_roots = evidence, []

    def prepare(self, args, kwargs):
        self.owner.assertLess(len(self.calls), MAX_CALLS)
        self.owner.assertLess(time.monotonic() - self.started, MAX_SECONDS)
        return super().prepare(args, kwargs)

    def snapshot(self, workspace):
        self.owner.assertLess(time.monotonic() - self.started, MAX_SECONDS)
        observed = super().snapshot(workspace)
        self.owner.assertLess(time.monotonic() - self.started, MAX_SECONDS)
        return observed

    def finish(self, record, workspace, code, stdout, stderr):
        self.owner.assertLess(time.monotonic() - self.started, MAX_SECONDS)
        hooks = record["environment_inputs"]
        if code == 74:
            self.owner.assertEqual(self.scenario, SCENARIOS[1])
            self.owner.assertEqual("after_publication", hooks.get("FACMAN_TEST_SELECTED_CONTEXT_EXIT"))
            self.owner.assertEqual(["presentation", "action", "readiness.prepare_joined"], record["argv"][3:6])
        else:
            self.owner.assertIn(code, (0, 1, 4))
        super().finish(record, workspace, code, stdout, stderr)
        self.owner.assertLess(time.monotonic() - self.started, MAX_SECONDS)

    def run(self, args, **kwargs):
        record, workspace = self.prepare(args, kwargs)
        remaining = MAX_SECONDS - (time.monotonic() - self.started)
        self.owner.assertTrue(remaining > 0, "Scenario deadline reached before dispatch")
        timeout = min(30, remaining)
        if os.name != "nt":
            kwargs["timeout"] = timeout
            completed = subprocess.run(args, **kwargs)
            self.finish(record, workspace, completed.returncode, completed.stdout, completed.stderr)
            return completed
        from tools import provider_canary_process as owned
        from tools import provider_canary_process_windows as windows
        from ctypes import wintypes as wt

        original_kernel = windows.kernel
        launch = {}
        def checked_kernel():
            api = original_kernel()
            api.GetProcessId.argtypes, api.GetProcessId.restype = [wt.HANDLE], wt.DWORD
            api.GetProcessIdOfThread.argtypes, api.GetProcessIdOfThread.restype = [wt.HANDLE], wt.DWORD
            api.IsProcessInJob.argtypes, api.IsProcessInJob.restype = [wt.HANDLE, wt.HANDLE, ctypes.POINTER(wt.BOOL)], wt.BOOL
            assign, resume = api.AssignProcessToJobObject, api.ResumeThread
            def checked_assign(job, process):
                assigned = assign(job, process)
                membership = wt.BOOL()
                if not assigned or not api.IsProcessInJob(process, job, ctypes.byref(membership)) or not membership.value:
                    raise AssertionError("Suspended CLI lacks its exact owned job")
                launch.update(pid=api.GetProcessId(process), exact_job_membership_before_resume=True)
                if not launch["pid"]:
                    raise AssertionError("Retained CLI handle has no process identity")
                return assigned
            def checked_resume(thread):
                if api.GetProcessIdOfThread(thread) != launch["pid"]:
                    raise AssertionError("Retained initial thread belongs to another process")
                previous = resume(thread)
                if previous != 1:
                    raise AssertionError("Initial suspension count must equal one")
                launch.update(created_suspended=True, resume_previous_suspend_count=previous)
                return previous
            api.AssignProcessToJobObject, api.ResumeThread = checked_assign, checked_resume
            return api
        directory = self.evidence / f"command-{len(self.calls):03}"
        with patch.object(windows, "kernel", checked_kernel):
            completed = owned.command(list(args), cwd=self.context.consumer, environment=kwargs["env"],
                directory=directory, timeout=timeout, output_limit=1024 * 1024,
                wait_for_job_empty_after_primary=True)
        record.update(owned_command_receipt=completed.receipt, launch=launch,
            owned_command_receipt_sha256=hashlib.sha256((directory / "receipt.json").read_bytes()).hexdigest())
        for name in ("receipt.json", "stdout.raw", "stderr.raw"):
            self.files[f"commands/{len(self.calls):03}/{name}"] = (directory / name).read_bytes()
        if (completed.receipt["termination"] != "completed" or not completed.receipt["primary_stopped"]
                or not completed.receipt["job_empty_observed"] or completed.receipt["job_terminated"]):
            raise AssertionError("Delivered CLI did not finish normally with an empty owned job: " + str(directory))
        stdout, stderr = completed.stdout.decode("utf-8"), completed.stderr.decode("utf-8")
        self.finish(record, workspace, completed.returncode, stdout, stderr)
        return subprocess.CompletedProcess(args, completed.returncode, stdout, stderr)


def exercise(owner, scenario: str, *, package: Path, consumer: Path, fixture: Path,
             binding: dict, evidence_root: Path) -> None:
    owner.assertIn(scenario, SCENARIOS)
    name = "environment-" + scenario.removeprefix("test_")
    evidence = evidence_root / name
    evidence.mkdir()
    driver = EnvironmentConsumerDriver(owner, scenario, consumer, package / "bin/facman.exe" if os.name == "nt" else package / "bin/facman", evidence)
    proxy = types.SimpleNamespace(run=driver.run, PIPE=subprocess.PIPE)
    original_temporary = tempfile.TemporaryDirectory
    class CapturedTemporary(original_temporary):
        def cleanup(self):
            root = Path(self.name).resolve()
            if root.is_dir():
                inventory = driver.snapshot(root)
                driver.scenario_roots.append(dict(path=str(root), inventory=inventory))
            super().cleanup()
    temporary = types.SimpleNamespace(TemporaryDirectory=lambda **kwargs:
        CapturedTemporary(**dict(kwargs, dir=consumer)))
    result = unittest.TestResult()
    passed = False
    before_package = {p.relative_to(package).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                      for p in package.rglob("*") if p.is_file()}
    installation_before = driver.snapshot(fixture)
    try:
        owner.assertEqual([], package_hash_manifest.verify_manifest(package))
        with ExitStack() as stack:
            stack.enter_context(patch.dict(os.environ, macos.consumer_environment(dict(os.environ)), clear=True))
            stack.enter_context(patch.dict(os.environ, FACMAN_CLI_EXE=str(driver.context.executable)))
            stack.enter_context(patch.object(native_cli, "ROOT", consumer))
            stack.enter_context(patch.object(native_cli, "subprocess", proxy))
            for module in (source, solver):
                stack.enter_context(patch.object(module, "FIXTURE_INSTALL", fixture))
            stack.enter_context(patch.object(source, "tempfile", temporary))
            source.EnvironmentReconstructionTests(scenario).run(result)
        owner.assertEqual(1, result.testsRun)
        owner.assertEqual([], result.skipped)
        owner.assertTrue(result.wasSuccessful(), repr(result.errors + result.failures))
        owner.assertTrue(driver.calls)
        owner.assertTrue(driver.scenario_roots, "Capture complete source/world/profile/corrupt inputs before cleanup")
        owner.assertTrue(all(all(key in call for key in ("exit_code", "stdout", "stderr", "after")) for call in driver.calls))
        owner.assertEqual(installation_before, driver.snapshot(fixture))
        owner.assertEqual(before_package, {p.relative_to(package).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                                          for p in package.rglob("*") if p.is_file()})
        owner.assertLess(time.monotonic() - driver.started, MAX_SECONDS)
        passed = True
    finally:
        effects = dict(schema="facman.delivered_environment_calls.v1", scenario=scenario,
            source_test_id=source.__name__ + ".EnvironmentReconstructionTests." + scenario,
            source_test_sha256=hashlib.sha256(Path(source.__file__).read_bytes()).hexdigest(),
            adapter_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            calls=driver.calls, scenario_roots=driver.scenario_roots,
            registered_installation=dict(path=str(fixture), before=installation_before, after=driver.snapshot(fixture)),
            package_file_count=len(before_package), package_closure_sha256=hashlib.sha256(
                json.dumps(before_package, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
            tests_run=result.testsRun, errors=[text for _, text in result.errors],
            failures=[text for _, text in result.failures], skips=[text for _, text in result.skipped],
            elapsed_seconds=time.monotonic() - driver.started, raw_stream_bytes=driver.stream_bytes,
            limits=dict(calls=MAX_CALLS, seconds=MAX_SECONDS, raw_cas_bytes=macos.MAX_CUSTODY_RAW_BYTES),
            real_play=False, real_game=False, human=False)
        raw = json.dumps(effects, sort_keys=True, separators=(",", ":")).encode("utf-8")
        files = dict(driver.files, **{"calls.json": raw})
        receipt = dict(binding, mode=name, test_id=owner.id() + ":" + scenario,
            result="pass" if passed else "fail", source_test_id=effects["source_test_id"],
            calls_sha256=hashlib.sha256(raw).hexdigest(), evidence_scope="produced_package_environment_reconstruction_fixture; no_real_game_or_human_claim")
        if os.name != "nt":
            custody = macos.custody_record(receipt, files)
            custody_line = "delivered-tui-custody: " + json.dumps(custody, sort_keys=True, separators=(",", ":"))
        else:
            owner.assertLessEqual(sum(map(len, files.values())), macos.MAX_CUSTODY_RAW_BYTES)
            content = dict(receipt=receipt, files={name: dict(size_bytes=len(data),
                sha256=hashlib.sha256(data).hexdigest(), bytes_base64=base64.b64encode(data).decode("ascii")) for name, data in files.items()})
            canonical = json.dumps(content, sort_keys=True, separators=(",", ":")).encode("utf-8")
            owner.assertLessEqual(len(canonical), macos.MAX_CUSTODY_JSON_BYTES)
            compressed = zlib.compress(canonical, 9)
            encoded = base64.b64encode(compressed).decode("ascii")
            owner.assertLessEqual(len(encoded), macos.MAX_CUSTODY_ENCODED_BYTES)
            custody = dict(schema="facman.windows_delivered_environment_custody.v1",
                canonical_json_sha256=hashlib.sha256(canonical).hexdigest(),
                compressed_sha256=hashlib.sha256(compressed).hexdigest(), payload_base64=encoded)
            custody_line = "delivered-windows-environment-custody " + json.dumps(custody, sort_keys=True)
        receipt["custody_canonical_json_sha256"] = custody["canonical_json_sha256"]
        for name, data in files.items():
            path = evidence / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        owner.assertLess(time.monotonic() - driver.started, MAX_SECONDS)
        (evidence / "result.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
        print(custody_line, flush=True)
        print("delivered-environment-evidence: " + json.dumps(receipt, sort_keys=True), flush=True)
        owner.assertLess(time.monotonic() - driver.started, MAX_SECONDS)
