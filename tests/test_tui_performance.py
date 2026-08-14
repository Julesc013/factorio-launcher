# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import ctypes
import os
import subprocess
import tempfile
import threading
import time
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUDGET = ROOT / "release/index/tui_performance_budget.v1.toml"


def tui_executable() -> Path | None:
    configured = os.environ.get("FACMAN_CLI_EXE") or os.environ.get("FACMAN_TUI_EXE")
    candidates = [
        Path(configured) if configured else Path("__missing__"),
        ROOT / "build/native-smoke/Debug/facman.exe",
        ROOT / "build/native-smoke/facman",
        ROOT / "build/macos-native/facman",
    ]
    return next((path for path in candidates if path.is_file()), None)


def working_set_mib(process: subprocess.Popen[bytes]) -> float:
    if os.name == "nt":
        class ProcessMemoryCounters(ctypes.Structure):
            _fields_ = [
                ("cb", ctypes.c_ulong),
                ("PageFaultCount", ctypes.c_ulong),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
            ]

        counters = ProcessMemoryCounters()
        counters.cb = ctypes.sizeof(counters)
        handle = ctypes.c_void_p(int(getattr(process, "_handle")))
        if not ctypes.windll.psapi.GetProcessMemoryInfo(
            handle, ctypes.byref(counters), counters.cb
        ):
            raise ctypes.WinError()
        return counters.PeakWorkingSetSize / (1024 * 1024)
    status = Path(f"/proc/{process.pid}/status")
    if status.is_file():
        for line in status.read_text(encoding="utf-8").splitlines():
            if line.startswith(("VmHWM:", "VmRSS:")):
                return int(line.split()[1]) / 1024
    result = subprocess.run(
        ["ps", "-o", "rss=", "-p", str(process.pid)],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=5,
    )
    return int(result.stdout.strip()) / 1024


def run_linear_receipt(
    executable: Path,
    workspace: Path,
    commands: bytes,
    timeout: float,
) -> dict[str, object]:
    environment = os.environ.copy()
    environment.update({"TERM": "dumb", "NO_COLOR": "1", "FACMAN_SAFE_MODE": "1"})
    started = time.perf_counter()
    process = subprocess.Popen(
        [
            str(executable), "tui", "--ordinary", "--plain",
            "--workspace", str(workspace),
        ],
        cwd=ROOT,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=environment,
    )
    assert process.stdin is not None
    assert process.stdout is not None
    output = bytearray()
    ready = threading.Event()

    def collect() -> None:
        while True:
            value = process.stdout.read(1)
            if not value:
                break
            output.extend(value)
            if b"Command (1-8" in output:
                ready.set()

    reader = threading.Thread(target=collect, daemon=True)
    reader.start()
    if not ready.wait(timeout):
        process.kill()
        process.wait(timeout=5)
        reader.join(timeout=5)
        raise AssertionError("same-binary TUI did not reach its first linear render")
    first_render_ms = (time.perf_counter() - started) * 1000
    memory_mib = working_set_mib(process)
    process.stdin.write(commands)
    process.stdin.flush()
    process.stdin.close()
    try:
        returncode = process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)
        raise
    reader.join(timeout=5)
    stderr = process.stderr.read() if process.stderr is not None else b""
    if process.stdout is not None:
        process.stdout.close()
    if process.stderr is not None:
        process.stderr.close()
    return {
        "returncode": returncode,
        "first_render_ms": first_render_ms,
        "journey_ms": (time.perf_counter() - started) * 1000,
        "working_set_mib": memory_mib,
        "stdout": bytes(output),
        "stderr": stderr,
    }


class TuiPerformanceContractTests(unittest.TestCase):
    def test_budget_is_bounded_non_authorizing_and_indexed(self) -> None:
        with BUDGET.open("rb") as handle:
            budget = tomllib.load(handle)
        self.assertEqual(budget["schema"], "facman.tui_performance_budget.v1")
        self.assertGreaterEqual(budget["samples"], 3)
        self.assertGreaterEqual(budget["limits"]["long_list_items"], 10000)
        self.assertFalse(budget["law"]["alternate_state_authority"])
        self.assertFalse(budget["law"]["resident_service_required"])
        self.assertFalse(budget["law"]["factorio_execution"])
        release_index = (ROOT / "release/index/release_index.v1.toml").read_text(encoding="utf-8")
        self.assertIn("tui_performance_budget.v1.toml", release_index)


@unittest.skipUnless(tui_executable(), "optional: functional same-binary TUI build is not available")
class TuiPerformanceReceiptTests(unittest.TestCase):
    def test_safe_linear_startup_journey_memory_and_accessible_transcript(self) -> None:
        executable = tui_executable()
        assert executable is not None
        with BUDGET.open("rb") as handle:
            budget = tomllib.load(handle)
        limits = budget["limits"]
        receipts: list[dict[str, object]] = []
        with tempfile.TemporaryDirectory(prefix="facman-tui-performance-") as temporary:
            root = Path(temporary)
            for index in range(budget["samples"]):
                workspace = root / f"uncreated-workspace-{index}"
                receipt = run_linear_receipt(
                    executable,
                    workspace,
                    b"2\n4\n7\n1\ntab\nq\n",
                    limits["ordinary_six_input_p95_ms"] / 1000,
                )
                self.assertEqual(receipt["returncode"], 0, receipt["stderr"])
                self.assertFalse(workspace.exists())
                receipts.append(receipt)
        self.assertLessEqual(
            max(float(item["first_render_ms"]) for item in receipts),
            limits["first_render_p95_ms"],
        )
        self.assertLessEqual(
            max(float(item["journey_ms"]) for item in receipts),
            limits["ordinary_six_input_p95_ms"],
        )
        self.assertLessEqual(
            max(float(item["working_set_mib"]) for item in receipts),
            limits["peak_working_set_mib"],
        )
        for receipt in receipts:
            transcript = bytes(receipt["stdout"])
            self.assertLessEqual(len(transcript), limits["transcript_bytes"])
            self.assertIn(b"Focus: Page:", transcript)
            self.assertIn(b"Focus: Action:", transcript)
            self.assertIn(b"Status: Authoritative snapshot", transcript)
            self.assertIn(b"Actions", transcript)
            self.assertNotIn(b"\x1b[", transcript)


if __name__ == "__main__":
    unittest.main()
