# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import ctypes
import argparse
import json
import math
import os
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

from tools import provider_canary_process as process


@unittest.skipUnless(os.name == "nt", "unsupported: Windows owned-job containment is not qualified on this host")
class CanaryProcessTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="canary-deadline-test-"))

    def run_helper(self, text, **options):
        path = self.root / "helper.py"
        path.write_text(text, encoding="utf-8")
        return process.command([sys.executable, str(path)], cwd=self.root,
                               directory=self.root / "command", **options)

    def test_success_preserves_exact_streams_and_exit(self):
        result = self.run_helper("import sys\nprint('out')\nprint('err', file=sys.stderr)\n")
        self.assertTrue(result.ok, result.receipt)
        self.assertEqual(result.stdout, b"out\r\n")
        self.assertEqual(result.stderr, b"err\r\n")
        self.assertEqual(json.loads((result.directory / "receipt.json").read_text())["exit_code"], 0)

    def test_timeout_retains_initial_effect_and_output(self):
        result = self.run_helper("import time\nfrom pathlib import Path\n"
                                 "Path('started').write_text('retain')\n"
                                 "print('partial', flush=True)\ntime.sleep(60)\n", timeout=0.5)
        self.assertEqual(result.receipt["termination"], "command_timeout", result.receipt)
        self.assertTrue(result.receipt["primary_stopped"])
        self.assertEqual((self.root / "started").read_text(), "retain")
        self.assertIn(b"partial", result.stdout)
        self.assertLess(result.receipt["elapsed_seconds"], 8)
        self.assertEqual(result.receipt["effects"], "possible_retained")

    def test_expired_overall_budget_never_dispatches_later_command(self):
        budget = process.Budget(0.01, 1)
        time.sleep(0.03)
        result = self.run_helper("from pathlib import Path\nPath('forbidden').touch()\n",
                                 budget=budget)
        self.assertEqual(result.receipt["termination"], "overall_deadline_before_dispatch")
        self.assertFalse(result.receipt["dispatched"])
        self.assertFalse((self.root / "forbidden").exists())

    def test_overall_budget_stops_a_blocked_worker(self):
        budget = process.Budget(0.5, 10)
        result = self.run_helper("import time\nprint('worker', flush=True)\ntime.sleep(60)\n",
                                 budget=budget, timeout=10)
        self.assertEqual(result.receipt["termination"], "overall_timeout")
        self.assertTrue(result.receipt["primary_stopped"])

    def test_invalid_budgets_refuse_before_effects(self):
        for value in (0, -1, math.inf, math.nan, 7201, True):
            with self.subTest(value=value), self.assertRaises(ValueError):
                process.command([sys.executable, "-c", "pass"], cwd=self.root,
                                timeout=value, directory=self.root / "forbidden")
        self.assertFalse((self.root / "forbidden").exists())

    def test_output_limit_stops_capture_at_the_declared_bound(self):
        result = self.run_helper("import sys\nsys.stdout.buffer.write(b'x' * 200000)\n",
                                 output_limit=4096)
        self.assertEqual(result.receipt["termination"], "output_limit")
        self.assertLessEqual((result.directory / "stdout.raw").stat().st_size, 4096)
        self.assertEqual(len(result.stdout), 4096)

    def test_assignment_failure_cannot_resume_the_owned_child(self):
        api = process.windows.kernel()
        def refuse(*args):
            ctypes.set_last_error(5)
            return 0
        api.AssignProcessToJobObject = refuse
        with mock.patch.object(process.windows, "kernel", return_value=api):
            result = self.run_helper("from pathlib import Path\nPath('forbidden').touch()\n")
        self.assertEqual(result.receipt["termination"], "start_failed")
        self.assertFalse(result.receipt["resumed"])
        self.assertTrue(result.receipt["primary_stopped"])
        self.assertFalse((self.root / "forbidden").exists())
        self.assertIn("AssignProcess", result.receipt["error"])

    def test_timeout_stops_descendant_but_preserves_unrelated_sentinel(self):
        api = process.windows.kernel()
        api.OpenProcess.argtypes = [ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32]
        api.OpenProcess.restype = ctypes.c_void_p
        captured = []
        def observe():
            deadline = time.monotonic() + 3
            while time.monotonic() < deadline:
                path = self.root / "child.pid"
                if path.exists():
                    try:
                        pid = int(path.read_text())
                    except ValueError:
                        continue
                    handle = api.OpenProcess(0x100000 | 0x1000, False, pid)
                    if handle:
                        captured.append(handle)
                        return
                time.sleep(0.01)
        watcher = threading.Thread(target=observe)
        sentinel = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"],
                                    creationflags=subprocess.CREATE_NO_WINDOW)
        try:
            watcher.start()
            result = self.run_helper("import subprocess,sys,time\nfrom pathlib import Path\n"
                "child=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)'])\n"
                "Path('child.pid').write_text(str(child.pid))\n"
                "print('descendant-started',flush=True)\ntime.sleep(60)\n", timeout=1)
            watcher.join(timeout=4)
            self.assertFalse(watcher.is_alive())
            self.assertEqual(result.receipt["termination"], "command_timeout")
            self.assertEqual(len(captured), 1)
            self.assertEqual(api.WaitForSingleObject(captured[0], 2000), 0)
            self.assertIsNone(sentinel.poll())
        finally:
            sentinel.terminate()
            sentinel.wait(timeout=5)
            watcher.join(timeout=4)
            for handle in captured:
                api.CloseHandle(handle)

    def test_command_budget_is_distinct_from_larger_overall_budget(self):
        result = self.run_helper("import time\ntime.sleep(60)\n",
            timeout=10, budget=process.Budget(10, 0.2))
        self.assertEqual(result.receipt["termination"], "command_timeout")
        self.assertTrue(result.receipt["job_empty_observed"])

    def test_successful_primary_cannot_leave_descendant_or_pipe_open(self):
        result = self.run_helper("import subprocess,sys\n"
            "subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)'])\n"
            "print('parent-complete',flush=True)\n", timeout=1)
        self.assertTrue(result.ok, result.receipt)
        self.assertTrue(result.receipt["job_empty_observed"])
        self.assertIn(b"parent-complete", result.stdout)
        self.assertLess(result.receipt["elapsed_seconds"], 3)

    def test_pipe_error_retains_partial_output_and_refuses_success(self):
        drain = process.windows.Capture.drain
        def fail_after_read(capture):
            drain(capture)
            if capture.count:
                raise OSError("injected pipe collection error")
        with mock.patch.object(process.windows.Capture, "drain", fail_after_read):
            result = self.run_helper("import time\nprint('partial',flush=True)\ntime.sleep(60)\n")
        self.assertFalse(result.ok)
        self.assertEqual(result.receipt["termination"], "cleanup_incomplete")
        self.assertIn(b"partial", result.stdout)
        self.assertIn("injected pipe", result.receipt["error"])

    def test_failed_job_empty_observation_cannot_claim_success(self):
        api = process.windows.kernel()
        api.QueryInformationJobObject = lambda *args: 0
        with mock.patch.object(process.windows, "kernel", return_value=api):
            result = self.run_helper("print('completed')\n")
        self.assertEqual(result.receipt["termination"], "cleanup_incomplete")
        self.assertFalse(result.ok)
        self.assertIn("QueryInformationJobObject", result.receipt["cleanup_error"])

    def test_invalid_input_and_environment_refuse_without_evidence_effect(self):
        for options in ({"input_bytes": b"x" * (process.MAX_INPUT_BYTES + 1)},
                        {"environment": {"BAD": "nul\0value"}},
                        {"output_limit": process.MAX_OUTPUT_BYTES + 1}):
            with self.subTest(options=list(options)), self.assertRaises(ValueError):
                process.command([sys.executable, "-c", "pass"], cwd=self.root,
                                directory=self.root / "forbidden", **options)
        self.assertFalse((self.root / "forbidden").exists())

    def test_receipt_and_worker_result_caps_refuse_without_partial_success(self):
        from tools import provider_local_source_canary as canary
        with mock.patch.object(process, "MAX_RECEIPT_BYTES", 128):
            with self.assertRaisesRegex(ValueError, "receipt size"):
                process.write_json(self.root / "receipt.json", {"large": "x" * 200})
            self.assertFalse((self.root / "receipt.json").exists())
            (self.root / "result.json").write_bytes(b" " * 129)
            with self.assertRaisesRegex(ValueError, "observation limit"):
                canary.read_result(self.root / "result.json")

    def test_outer_supervisor_covers_blocked_source_worker_and_retains_effects(self):
        from tools import provider_local_source_canary as canary
        worker = self.root / "blocked_worker.py"
        worker.write_text("import sys,time\nfrom pathlib import Path\n"
            "root=Path(sys.argv[sys.argv.index('--work-dir')+1]);root.mkdir()\n"
            "(root/'source-observation-started').touch()\n"
            "print('source observation blocked',flush=True)\ntime.sleep(60)\n")
        usk, ulk, temp = (self.root / name for name in ("usk", "ulk", "temp"))
        for path in (usk, ulk, temp):
            path.mkdir()
        args = argparse.Namespace(usk_root=usk, ulk_root=ulk, work_dir=self.root / "work",
            temp_root=temp, review_receipt=self.root / "unused-review",
            review_sha256="0"*64, usk_commit="1"*40, usk_tree="2"*40,
            usk_ref="refs/heads/task/fixture", overall_timeout=0.5, command_timeout=10)
        with mock.patch.object(canary, "__file__", str(worker)):
            with self.assertRaises(process.CommandFailure) as caught:
                canary.execute(args)
        self.assertEqual(caught.exception.result.receipt["termination"], "overall_timeout")
        self.assertTrue(caught.exception.result.receipt["job_empty_observed"])
        self.assertTrue((args.work_dir / "source-observation-started").exists())
        final = json.loads((self.root / "work-control/supervision.json").read_text())
        self.assertEqual(final["result"], "failed_retained")

    def test_owned_metadata_records_actual_bounded_git_execution(self):
        from tools import provider_source_bytes
        with mock.patch.dict(os.environ, FACMAN_CANARY_OWNED_JOB="1",
                             FACMAN_CANARY_EVIDENCE_ROOT=str(self.root)):
            result = provider_source_bytes.git_bytes(self.root, "--version")
        self.assertTrue(result.startswith(b"git version "))
        receipts = list(self.root.glob("canary-command-*/receipt.json"))
        self.assertEqual(len(receipts), 1)
        receipt = json.loads(receipts[0].read_text())
        self.assertEqual(receipt["termination"], "completed")
        self.assertTrue(receipt["job_empty_observed"])
        self.assertEqual(receipt["configured_seconds"], 30)
        self.assertEqual(receipt["stdout"]["captured_bytes"], len(result))

    def test_cmake_timeout_and_invalid_limits_refuse_without_acceptance(self):
        module = Path(__file__).resolve().parents[1] / "cmake/FacManProviderLocalCustody.cmake"
        helper = self.root / "slow.py"
        helper.write_text("import time\nprint('partial-custody',flush=True)\ntime.sleep(60)\n")
        for number, limit in enumerate(("0.2", "0", "-1", "nan", "7201")):
            script = self.root / f"timeout-{number}.cmake"
            script.write_text("\n".join([
                "cmake_minimum_required(VERSION 3.20)",
                f'include("{module.as_posix()}")',
                f'set(Python3_EXECUTABLE "{Path(sys.executable).as_posix()}")',
                f'set(_FACMAN_LOCAL_CUSTODY_CHECKER "{helper.as_posix()}")',
                'set(FACMAN_PROVIDER_LOCAL_SOURCE_CUSTODY_FILE "fixture")',
                'set(FACMAN_PROVIDER_LOCAL_SOURCE_CUSTODY_SHA256 "fixture")',
                'set(FACMAN_PROVIDER_MODE source)', 'set(FACMAN_PROVIDER_SOURCE_LINKAGE static)',
                'set(FACMAN_PROVIDER_SDK_CONSUMPTION_CANDIDATE ON)',
                'set(FACMAN_PROVIDER_LOCK_KIND sdk_candidate)',
                f'set(FACMAN_PROVIDER_LOCAL_SOURCE_CUSTODY_TIMEOUT "{limit}")',
                '_facman_local_source_checkpoint(result "fixture" "c" "t" '
                '"https://github.com/Julesc013/universal-setup.git" "r")',
                'message(FATAL_ERROR "forbidden acceptance")']) + "\n")
            result = process.command(["cmake", "-P", str(script)], cwd=self.root, timeout=10,
                                     directory=self.root / f"cmake-{number}")
            self.assertEqual(result.receipt["termination"], "completed", result.receipt)
            self.assertNotEqual(result.returncode, 0)
            self.assertNotIn(b"forbidden acceptance", result.stderr)
            self.assertIn(b"timeout" if number == 0 else b"finite, positive", result.stderr.lower())


if __name__ == "__main__":
    unittest.main()
