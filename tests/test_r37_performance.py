# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import json
import os
import shutil
import tempfile
import time
import unittest
import zipfile
from pathlib import Path

from native_cli import invoke


ROOT = Path(__file__).resolve().parents[1]
INSTALL = ROOT / "tests/fixtures/fake_factorio_install"


def call(workspace: Path, *args: str, success: bool = True) -> dict:
    code, stdout, stderr = invoke(["--workspace", str(workspace), *args, "--json"])
    if success and code != 0:
        raise AssertionError(stderr or stdout)
    if not success and code == 0:
        raise AssertionError(f"command unexpectedly succeeded: {stdout}")
    return json.loads(stdout or stderr)


def write_mod(path: Path, index: int) -> None:
    name = f"perf_mod_{index:04d}"
    dependencies = ["base >= 2.0"]
    dependencies.extend(f"perf_mod_{prior:04d} >= 1.0" for prior in range(max(0, index - 5), index))
    info = {
        "name": name,
        "title": name,
        "version": "1.0.0",
        "factorio_version": "2.0",
        "dependencies": dependencies,
    }
    entry = zipfile.ZipInfo(f"{name}_1.0.0/info.json", (2026, 7, 12, 0, 0, 0))
    entry.external_attr = 0o644 << 16
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_STORED) as archive:
        archive.writestr(entry, json.dumps(info, separators=(",", ":")))


def write_save(path: Path) -> None:
    entry = zipfile.ZipInfo("world/level-init.dat", (2026, 7, 12, 0, 0, 0))
    entry.external_attr = 0o644 << 16
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_STORED) as archive:
        archive.writestr(entry, b"bounded performance fixture")


@unittest.skipUnless(
    os.environ.get("FACMAN_RUN_R37_FULL_PERFORMANCE") == "1",
    "set FACMAN_RUN_R37_FULL_PERFORMANCE=1 for the bounded full-scale corpus",
)
class R37PerformanceTests(unittest.TestCase):
    def test_required_bounded_scale_corpus(self) -> None:
        with tempfile.TemporaryDirectory(prefix="facman-r37-performance-") as temporary:
            workspace = Path(temporary)
            call(workspace, "installs", "import", str(INSTALL), "--id", "fixture")
            call(workspace, "instances", "create", "Performance", "--id", "performance", "--install", "fixture")
            instance = workspace / "instances" / "performance"

            for index in range(1000):
                write_mod(instance / "mods" / f"perf_mod_{index:04d}_1.0.0.zip", index)
            started = time.perf_counter()
            plan = call(
                workspace, "modsets", "plan", "performance", "--enable", "perf_mod_0999",
                "--max-packages", "1001", "--max-graph-edges", "7000",
                "--max-solver-states", "20000", "--max-backtracks", "5000",
                "--max-elapsed-ms", "60000", "--max-explanation-nodes", "10000",
            )
            self.assertEqual(1001, len(plan["desired_mods"]))
            self.assertLess(time.perf_counter() - started, 120.0)
            exhausted = call(
                workspace, "modsets", "plan", "performance", "--enable", "perf_mod_0999",
                "--max-packages", "1001", "--max-graph-edges", "7000",
                "--max-solver-states", "1", success=False,
            )
            self.assertEqual("solver_budget_exceeded", exhausted["refusal"]["code"])

            template = workspace / "save-template.zip"
            write_save(template)
            for index in range(10000):
                shutil.copyfile(template, instance / "saves" / f"save-{index:05d}.zip")
            started = time.perf_counter()
            saves = call(workspace, "saves", "index", "--instance", "performance")
            if "error" in saves:
                self.fail(json.dumps(saves["error"], sort_keys=True))
            self.assertEqual(10000, saves.get("save_count"), sorted(saves))
            self.assertLess(time.perf_counter() - started, 180.0)

            for index in range(100):
                call(workspace, "snapshots", "create", "performance", f"snapshot-{index:03d}")
            self.assertEqual(100, len(call(workspace, "snapshots", "list", "performance")["snapshots"]))

            large = instance / "script-output" / "large-corpus"
            large.mkdir(parents=True)
            for index in range(2000):
                (large / f"file-{index:04d}.txt").write_text(f"payload-{index}\n", encoding="utf-8")
            started = time.perf_counter()
            call(workspace, "instances", "clone", "performance", "performance-copy")
            difference = call(workspace, "instances", "diff", "performance", "performance-copy")
            self.assertEqual(
                {"effective_config", "manifest"},
                {item["category"] for item in difference["differences"]},
            )
            self.assertEqual(2, len(difference["differences"]))
            self.assertLess(time.perf_counter() - started, 120.0)


if __name__ == "__main__":
    unittest.main()
