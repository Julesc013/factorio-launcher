# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

"""Exercise interrupted first installation through a supplied Linux Setup package."""

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


def invoke(
    setup: Path, home: Path, deadline: float, *args: str, interrupt: str = ""
) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["HOME"] = str(home)
    if interrupt:
        environment[interrupt] = "1"
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise TimeoutError("Linux Setup package proof exceeded its absolute deadline")
    return subprocess.run(
        [str(setup), *args], env=environment,
        capture_output=True, text=True, check=False,
        timeout=remaining,
    )


def require(result: subprocess.CompletedProcess[str], code: int, step: str) -> None:
    if result.returncode != code:
        raise RuntimeError(
            f"{step}: expected exit {code}, got {result.returncode}; "
            f"stdout={result.stdout[-500:]} stderr={result.stderr[-500:]}"
        )


def main() -> int:
    if len(sys.argv) != 6:
        raise SystemExit(
            "usage: linux_setup_package_first_install_recovery.py "
            "CANDIDATE_BUNDLE NEW_HOME RECEIPT SOURCE_SHA RUN_ID"
        )
    bundle = Path(sys.argv[1]).resolve(strict=True)
    candidate = verify_bundle(bundle)
    source_sha, run_id = sys.argv[4:6]
    if candidate["source_revision"] != source_sha or candidate["github"]["run_id"] != run_id:
        raise SystemExit("candidate source or run identity differs from requested proof")
    version = candidate["version"]
    setup = bundle / f"FacMan-{version}-linux-x64-setup.run"
    setup.resolve(strict=True)
    home = Path(sys.argv[2])
    receipt = Path(sys.argv[3])
    if home.exists() or home.is_symlink() or not home.parent.is_dir():
        raise SystemExit("NEW_HOME must be a new path beneath an existing directory")
    if receipt.exists() or not receipt.parent.is_dir():
        raise SystemExit("RECEIPT must be a new file beneath an existing directory")
    home.mkdir()
    workspace = home / "workspace"
    workspace.mkdir()
    sentinel = workspace / "world.zip"
    sentinel.write_bytes(b"preserved world bytes\n")
    deadline = time.monotonic() + 180.0
    version_result = invoke(setup, home, deadline, "--version")
    require(version_result, 0, "Setup version")
    if version_result.stdout.strip() != version:
        raise RuntimeError("produced Setup version differs from candidate manifest")

    require(invoke(
        setup, home, deadline, "install", "--yes",
        interrupt="FACMAN_TEST_LINUX_SETUP_INTERRUPT_FIRST_AFTER_CURRENT",
    ), 75, "first-install cutover interruption")
    install = home / ".local/opt/facman"
    installed_setup = install / "maintenance/FacManSetup.run"
    if not installed_setup.is_file() or not (install / "current").is_symlink():
        raise RuntimeError("interrupted produced Setup did not preserve maintenance entry")
    if not (install / "state/first-install-pending.v1").is_dir():
        raise RuntimeError("interrupted produced Setup did not preserve recovery record")
    if invoke(setup, home, deadline, "verify").returncode == 0:
        raise RuntimeError("verify accepted an interrupted first install")
    require(invoke(
        installed_setup, home, deadline, "recover", "--yes",
        interrupt="FACMAN_TEST_LINUX_SETUP_INTERRUPT_FIRST_RECOVERY_AFTER_CURRENT",
    ), 75, "recovery interruption")
    require(invoke(installed_setup, home, deadline, "recover", "--yes"), 0, "restarted recovery")
    if install.exists() or sentinel.read_bytes() != b"preserved world bytes\n":
        raise RuntimeError("first-install recovery did not restore absence and preserve workspace")
    require(invoke(setup, home, deadline, "install", "--yes"), 0, "retry installation")
    require(invoke(setup, home, deadline, "verify"), 0, "verified retry")
    require(invoke(setup, home, deadline, "uninstall", "--yes"), 0, "removal after retry")
    if (install.exists() or
        (home / ".local/bin/facman").is_symlink() or
        (home / ".local/bin/FacMan").is_symlink() or
        sentinel.read_bytes() != b"preserved world bytes\n"):
        raise RuntimeError("produced Setup removal changed workspace or left application")

    sha256 = hashlib.sha256(setup.read_bytes()).hexdigest()
    receipt.write_text(json.dumps({
        "schema": "facman.linux_first_install_package_recovery_proof.v1",
        "status": "pass",
        "source_revision": source_sha,
        "source_tree": candidate["source_tree"],
        "github_run_id": run_id,
        "github_run_attempt": candidate["github"]["run_attempt"],
        "candidate_manifest_sha256": hashlib.sha256(
            (bundle / "product-candidate-bundle.v1.json").read_bytes()
        ).hexdigest(),
        "setup_filename": setup.name,
        "setup_sha256": sha256,
        "setup_version": version,
        "steps": [
            "ordinary_first_install_interrupted_after_current",
            "installed_maintenance_entry_retained",
            "verify_refused_incomplete_install",
            "first_recovery_interrupted",
            "installed_entry_restarted_recovery_to_absence",
            "workspace_preserved",
            "reinstall_verified_and_removed",
        ],
    }, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(f"Linux Setup first-install recovery passed: {sha256}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
