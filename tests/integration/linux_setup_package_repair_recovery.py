# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

"""Exercise same-version repair recovery through an exact produced Linux Setup."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.package.candidate_evidence import verify_bundle  # noqa: E402


def invoke(setup: Path, home: Path, deadline: float, *args: str,
           interrupt: str = "") -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["HOME"] = str(home)
    if interrupt:
        environment[interrupt] = "1"
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise TimeoutError("Linux Setup repair proof exceeded its absolute deadline")
    return subprocess.run(
        [str(setup), *args], env=environment, capture_output=True,
        text=True, check=False, timeout=remaining,
    )


def require(result: subprocess.CompletedProcess[str], code: int, step: str) -> str:
    if result.returncode != code:
        raise RuntimeError(
            f"{step}: expected exit {code}, got {result.returncode}; "
            f"stdout={result.stdout[-500:]} stderr={result.stderr[-500:]}"
        )
    return result.stdout.strip()


def main() -> int:
    if len(sys.argv) != 6:
        raise SystemExit(
            "usage: linux_setup_package_repair_recovery.py "
            "CANDIDATE_BUNDLE NEW_HOME_ROOT RECEIPT SOURCE_SHA RUN_ID"
        )
    bundle = Path(sys.argv[1]).resolve(strict=True)
    candidate = verify_bundle(bundle)
    source_sha, run_id = sys.argv[4:6]
    if candidate["source_revision"] != source_sha or candidate["github"]["run_id"] != run_id:
        raise SystemExit("candidate source or run identity differs from requested proof")
    version = candidate["version"]
    setup = bundle / f"FacMan-{version}-linux-x64-setup.run"
    if setup.is_symlink() or not setup.is_file():
        raise SystemExit("candidate Linux Setup is absent or linked")
    home_root = Path(sys.argv[2])
    receipt = Path(sys.argv[3])
    if home_root.exists() or home_root.is_symlink() or not home_root.parent.is_dir():
        raise SystemExit("NEW_HOME_ROOT must be a new path beneath an existing directory")
    if receipt.exists() or not receipt.parent.is_dir():
        raise SystemExit("RECEIPT must be a new file beneath an existing directory")
    home_root.mkdir()
    deadline = time.monotonic() + 300.0
    if require(invoke(setup, home_root, deadline, "--version"), 0, "Setup version") != version:
        raise RuntimeError("produced Setup version differs from candidate manifest")
    steps: list[str] = []
    for scenario, interrupt in (
        ("old-moved", "FACMAN_TEST_LINUX_SETUP_INTERRUPT_REPAIR_AFTER_OLD_MOVE"),
        ("partial-backup", "FACMAN_TEST_LINUX_SETUP_INTERRUPT_REPAIR_AFTER_NEW_MOVE"),
    ):
        home = home_root / scenario
        home.mkdir()
        workspace = home / "workspace"
        workspace.mkdir()
        sentinel = workspace / "world.zip"
        sentinel.write_bytes(b"produced package repair preserves workspace\n")
        require(invoke(setup, home, deadline, "install", "--yes"), 0, f"{scenario} install")
        install = home / ".local/opt/facman"
        generation = install / "generations" / version
        installed_setup = install / "maintenance/FacManSetup.run"
        if not installed_setup.is_file():
            raise RuntimeError("ordinary installation omitted maintenance Setup")
        (generation / "facman").unlink()
        require(invoke(installed_setup, home, deadline, "repair", "--yes",
                       interrupt=interrupt), 75, f"{scenario} interrupted repair")
        if not (install / "state/repair-pending.v1").is_dir():
            raise RuntimeError(f"{scenario}: repair omitted its recovery record")
        if invoke(installed_setup, home, deadline, "verify").returncode == 0:
            raise RuntimeError(f"{scenario}: verify accepted incomplete repair")
        if scenario == "old-moved":
            if generation.exists() or not (install / "current").is_symlink():
                raise RuntimeError("old-moved interruption did not expose the real cutover gap")
        else:
            backups = list((install / "generations").glob(".repair-previous-*"))
            if len(backups) != 1:
                raise RuntimeError("partial-backup interruption omitted its owned backup")
            (backups[0] / "share/facman/manifest/MANIFEST.sha256").unlink()
        require(invoke(installed_setup, home, deadline, "recover", "--yes"),
                0, f"{scenario} installed-entry recovery")
        require(invoke(installed_setup, home, deadline, "verify"), 0, f"{scenario} verify")
        executed = require(invoke(generation / "facman", home, deadline, "--version"),
                           0, f"{scenario} executable")
        if version not in executed or f"revision {source_sha}" not in executed:
            raise RuntimeError(f"{scenario}: repaired executable is not the candidate source")
        for name in ("facman", "FacMan"):
            link = home / ".local/bin" / name
            if not link.is_symlink() or link.readlink() != install / "current" / name:
                raise RuntimeError(f"{scenario}: native terminal entry changed")
        desktop = home / ".local/share/applications/facman.desktop"
        if desktop.is_symlink() or f"Exec={install}/current/FacMan" not in desktop.read_text():
            raise RuntimeError(f"{scenario}: native desktop entry changed")
        if sentinel.read_bytes() != b"produced package repair preserves workspace\n":
            raise RuntimeError(f"{scenario}: workspace bytes changed")
        history = home / ".local/state/facman-setup/history"
        if not any(history.rglob(f"completed-repair-{version}-*/new-target")):
            raise RuntimeError(f"{scenario}: repair history was not retained")
        require(invoke(installed_setup, home, deadline, "uninstall", "--yes"),
                0, f"{scenario} removal")
        if install.exists() or sentinel.read_bytes() != b"produced package repair preserves workspace\n":
            raise RuntimeError(f"{scenario}: removal left application or changed workspace")
        steps.append(scenario)

    setup_sha = hashlib.sha256(setup.read_bytes()).hexdigest()
    receipt.write_text(json.dumps({
        "schema": "facman.linux_setup_package_repair_recovery_proof.v1",
        "status": "pass",
        "source_revision": source_sha,
        "source_tree": candidate["source_tree"],
        "github_run_id": run_id,
        "github_run_attempt": candidate["github"]["run_attempt"],
        "candidate_manifest_sha256": hashlib.sha256(
            (bundle / "product-candidate-bundle.v1.json").read_bytes()
        ).hexdigest(),
        "setup_filename": setup.name,
        "setup_sha256": setup_sha,
        "setup_version": version,
        "scenarios": steps,
    }, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(f"Linux Setup repair recovery passed: {setup_sha}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
