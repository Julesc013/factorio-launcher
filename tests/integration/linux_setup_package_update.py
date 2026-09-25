# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

"""Exercise a version-distinct update using two produced Linux Setup packages."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import time
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def setup_from_bundle(root: Path) -> tuple[Path, dict[str, object]]:
    if root.is_symlink():
        raise SystemExit(f"linked candidate bundle is refused: {root}")
    root = root.resolve(strict=True)
    receipt = root / "product-candidate-bundle.v1.json"
    value = json.loads(receipt.read_text(encoding="utf-8"))
    version = value.get("version")
    revision = value.get("source_revision")
    tree = value.get("source_tree")
    github = value.get("github")
    if (value.get("schema") != "facman.product_candidate_bundle.v1" or
            value.get("status") != "pass" or not isinstance(version, str) or
            not isinstance(revision, str) or not re.fullmatch(r"[0-9a-f]{40}", revision) or
            not isinstance(tree, str) or not re.fullmatch(r"[0-9a-f]{40}", tree) or
            not isinstance(github, dict) or
            github.get("repository") != "Julesc013/factorio-launcher" or
            not str(github.get("run_id", "")).isdigit() or
            not str(github.get("run_attempt", "")).isdigit()):
        raise SystemExit(f"invalid exact candidate bundle receipt: {receipt}")
    name = f"FacMan-{version}-linux-x64-setup.run"
    matches = [item for item in value.get("assets", [])
               if isinstance(item, dict) and item.get("filename") == name]
    if len(matches) != 1:
        raise SystemExit(f"candidate bundle lacks one exact Linux Setup asset: {receipt}")
    setup = root / name
    if setup.is_symlink() or not setup.is_file():
        raise SystemExit(f"candidate Linux Setup is missing or linked: {setup}")
    if matches[0].get("sha256") != sha256(setup) or matches[0].get("bytes") != setup.stat().st_size:
        raise SystemExit(f"candidate Linux Setup does not match its bundle receipt: {setup}")
    return setup, {
        "version": version, "source_revision": revision, "source_tree": tree,
        "sha256": sha256(setup), "bundle_receipt_sha256": sha256(receipt),
        "run_id": github["run_id"], "run_attempt": github["run_attempt"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--previous-bundle", type=Path, required=True)
    parser.add_argument("--candidate-bundle", type=Path, required=True)
    parser.add_argument("--home", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    args = parser.parse_args()

    previous, previous_identity = setup_from_bundle(args.previous_bundle)
    candidate, candidate_identity = setup_from_bundle(args.candidate_bundle)
    if previous == candidate:
        raise SystemExit("distinct Setup packages are required")
    home = args.home.resolve()
    if home.exists():
        raise SystemExit(f"proof home must be new: {home}")
    home.mkdir(parents=True)
    environment = os.environ.copy()
    environment["HOME"] = str(home)
    deadline = time.monotonic() + 1800
    observations: list[dict[str, object]] = []

    def run(label: str, executable: Path, *arguments: str,
            interrupted: bool = False) -> str:
        variables = environment.copy()
        if interrupted:
            variables["FACMAN_TEST_LINUX_SETUP_INTERRUPT_AFTER_CURRENT"] = "1"
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise SystemExit("package update proof exceeded its absolute deadline")
        result = subprocess.run(
            [str(executable), *arguments], env=variables,
            capture_output=True, text=True, check=False, timeout=remaining,
        )
        observations.append({"step": label, "exit_code": result.returncode})
        expected = 75 if interrupted else 0
        if result.returncode != expected:
            raise SystemExit(
                f"{label}: expected exit {expected}, got {result.returncode}: "
                f"{result.stderr[-1200:]}"
            )
        return result.stdout.strip()

    def assert_installed_version(label: str, version: str, revision: str) -> None:
        output = run(label, install / "current/facman", "--version")
        if version not in output:
            raise SystemExit(f"{label}: installed executable reported the wrong version")
        if f"revision {revision}" not in output:
            raise SystemExit(f"{label}: installed executable reported the wrong source")

    old_version = run("previous-version", previous, "--version")
    new_version = run("candidate-version", candidate, "--version")
    if old_version != previous_identity["version"] or new_version != candidate_identity["version"]:
        raise SystemExit("Setup version does not match its candidate bundle")
    if old_version == new_version:
        raise SystemExit("package update requires distinct product versions")
    install = home / ".local/opt/facman"
    current = install / "current"
    installed_setup = install / "maintenance/FacManSetup.run"
    workspace = home / "Factorio Worlds"
    workspace.mkdir()
    sentinel = workspace / "world.zip"
    sentinel.write_bytes(b"preserved world bytes in produced-package update proof\n")
    sentinel_sha = sha256(sentinel)

    run("install-previous", previous, "install", "--yes", "--quiet")
    run("verify-previous", previous, "verify")
    assert_installed_version("execute-previous", old_version,
                             str(previous_identity["source_revision"]))
    run("interrupt-update", candidate, "install", "--yes", "--quiet", interrupted=True)
    if not (install / "state/update-pending.v1").is_dir():
        raise SystemExit("interrupted update did not retain its recovery journal")
    if sha256(installed_setup) != sha256(candidate):
        raise SystemExit("interrupted update did not retain the new Setup package")
    run("recover-update-from-installed-setup", installed_setup, "recover", "--yes")
    if sha256(installed_setup) != sha256(previous):
        raise SystemExit("recovery did not restore the previous Setup package")
    run("verify-recovered-previous", previous, "verify")
    assert_installed_version("execute-recovered-previous", old_version,
                             str(previous_identity["source_revision"]))

    run("install-candidate", candidate, "install", "--yes", "--quiet")
    run("verify-candidate", candidate, "verify")
    assert_installed_version("execute-candidate", new_version,
                             str(candidate_identity["source_revision"]))
    if sha256(installed_setup) != sha256(candidate):
        raise SystemExit("completed update did not install the candidate Setup package")
    run("repair-candidate-from-installed-setup", installed_setup,
        "repair", "--yes", "--quiet")
    run("verify-repaired-candidate", candidate, "verify")
    run("rollback-candidate-from-installed-setup", installed_setup,
        "rollback", "--yes")
    if sha256(installed_setup) != sha256(previous):
        raise SystemExit("rollback did not restore the previous Setup package")
    run("verify-rolled-back-previous", previous, "verify")
    assert_installed_version("execute-rolled-back-previous", old_version,
                             str(previous_identity["source_revision"]))
    run("reapply-candidate", candidate, "install", "--yes", "--quiet")
    run("verify-reapplied-candidate", candidate, "verify")
    assert_installed_version("execute-reapplied-candidate", new_version,
                             str(candidate_identity["source_revision"]))
    run("uninstall-candidate-from-installed-setup", installed_setup,
        "uninstall", "--yes", "--quiet")
    if current.exists() or current.is_symlink() or install.exists():
        raise SystemExit("uninstall retained the application root")
    if sha256(sentinel) != sentinel_sha:
        raise SystemExit("update or removal changed workspace bytes")
    history = home / ".local/state/facman-setup/history"
    if len(list(history.rglob("old-target"))) < 2:
        raise SystemExit("update history did not retain recovery and rollback records")

    record = {
        "schema": "facman.linux_setup_package_update_proof.v1",
        "status": "pass",
        "previous": previous_identity,
        "candidate": candidate_identity,
        "interruption": "deterministic exit after current pointer cutover",
        "workspace_sha256": sentinel_sha,
        "history_record_count": len(list(history.rglob("old-target"))),
        "steps": observations,
    }
    args.evidence.parent.mkdir(parents=True, exist_ok=True)
    args.evidence.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(record, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
