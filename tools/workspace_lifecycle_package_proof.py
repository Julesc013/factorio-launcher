#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

"""Qualify the workspace lifecycle through one exact packaged FacMan binary."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import json_contract  # noqa: E402

ACTIVE_PROFILES = {
    "windows_product_x64",
    "macos_product_x64",
    "linux_product_x64",
}
FIXTURE_INSTALL = ROOT / "tests/fixtures/fake_factorio_install"
FAULT_BOUNDARIES = (
    "after_journal_creation",
    "after_backup:1",
    "after_staged_file:1",
    "after_staging_verification",
    "before_first_commit",
    "after_commit:1",
    "before_terminal_receipt",
)
PREJOURNAL_FAULT_BOUNDARIES = (
    "after_lock_acquisition",
    "before_journal_creation",
)
CREATION_FAULT_BOUNDARIES = (
    "after_creation_lock_acquisition",
    "before_creation_journal",
    "after_creation_journal",
    "after_workspace_creation",
    "before_creation_terminal_receipt",
)
ROLLBACK_FAULT_BOUNDARY = "after_rollback_before_receipt"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_output(*arguments: str) -> str:
    return subprocess.run(
        ["git", *arguments],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    ).stdout.strip()


def source_revision() -> str:
    candidate = os.environ.get("GITHUB_SHA", "")
    if re.fullmatch(r"[0-9a-f]{40}", candidate):
        return candidate
    return git_output("rev-parse", "HEAD")


def source_tree() -> str:
    return git_output("rev-parse", "HEAD^{tree}")


def source_dirty() -> bool:
    return bool(git_output("status", "--porcelain", "--untracked-files=all"))


@contextmanager
def held_migration_lock(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = (
        b'{"schema":"facman.workspace_migration_lock.v1",'
        b'"identity":"package-proof"}\n'
    )
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes

        create_file = ctypes.windll.kernel32.CreateFileW
        create_file.argtypes = [
            wintypes.LPCWSTR,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.LPVOID,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.HANDLE,
        ]
        create_file.restype = wintypes.HANDLE
        handle = create_file(
            str(path), 0xC0000000, 0x00000001, None, 1, 0x80, None
        )
        if handle == wintypes.HANDLE(-1).value:
            raise OSError("could not create the held migration lock")
        written = wintypes.DWORD()
        if not ctypes.windll.kernel32.WriteFile(
            handle, payload, len(payload), ctypes.byref(written), None
        ):
            ctypes.windll.kernel32.CloseHandle(handle)
            raise OSError("could not populate the held migration lock")
        try:
            yield
        finally:
            ctypes.windll.kernel32.CloseHandle(handle)
            path.unlink(missing_ok=True)
    else:
        import fcntl

        with path.open("xb+") as stream:
            stream.write(payload)
            stream.flush()
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            try:
                yield
            finally:
                fcntl.flock(stream, fcntl.LOCK_UN)
        path.unlink(missing_ok=True)


class Driver:
    def __init__(self, executable: Path, cwd: Path) -> None:
        self.executable = executable.resolve(strict=True)
        self.cwd = cwd

    def raw(
        self,
        arguments: list[str],
        *,
        expected: int = 0,
        environment: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        completed = subprocess.run(
            [str(self.executable), *arguments],
            cwd=self.cwd,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=environment,
        )
        if completed.returncode != expected:
            raise ValueError(
                f"FacMan returned {completed.returncode}, expected {expected}: "
                f"{arguments!r}; stdout={completed.stdout[-4000:]!r}; "
                f"stderr={completed.stderr[-4000:]!r}"
            )
        return completed

    def json(
        self,
        workspace: Path,
        arguments: list[str],
        *,
        expected: int = 0,
        error_code: str = "",
        environment: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        completed = self.raw(
            ["--workspace", str(workspace), *arguments, "--json"],
            expected=expected,
            environment=environment,
        )
        try:
            envelope = json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"FacMan did not return machine JSON: {completed.stdout[-4000:]!r}"
            ) from exc
        if envelope.get("schema") != "facman.transport_response.v2":
            raise ValueError(f"FacMan returned an unexpected transport schema: {envelope!r}")
        if error_code:
            error = envelope.get("error") or {}
            if error.get("code") != error_code:
                raise ValueError(
                    f"FacMan returned {error.get('code')!r}, expected {error_code!r}"
                )
            return envelope
        payload = envelope.get("payload")
        if not isinstance(payload, dict):
            raise ValueError(f"FacMan success response lacks a payload: {envelope!r}")
        return payload


def apply_arguments(plan: dict[str, Any], suffix: str) -> list[str]:
    return [
        "workspace", "migration", "apply",
        "--expected-revision", str(plan["expected_workspace_revision"]),
        "--expected-root", str(plan["expected_root_identity"]),
        "--plan-digest", str(plan["plan_digest"]),
        "--confirmation", "explicit",
        "--request-id", f"request-{suffix}",
        "--operation-id", f"operation-{suffix}",
        "--attempt-id", f"attempt-{suffix}",
        "--idempotency-key", f"idempotency-{suffix}",
    ]


def control_arguments(
    action: str,
    operation_id: str,
    revision: str,
    suffix: str,
) -> list[str]:
    return [
        "workspace", "migration", action, operation_id,
        "--expected-revision", revision,
        "--confirmation", "explicit",
        "--request-id", f"request-{suffix}",
        "--operation-id", f"operation-{suffix}",
        "--attempt-id", f"attempt-{suffix}",
        "--idempotency-key", f"idempotency-{suffix}",
    ]


def prepare_legacy(driver: Driver, workspace: Path) -> tuple[dict[str, Any], Path, Path]:
    driver.json(
        workspace,
        ["installs", "import", str(FIXTURE_INSTALL), "--id", "fixture"],
    )
    canonical = workspace / "installs/refs/fixture.json"
    legacy = workspace / "installs/installed_state/fixture.json"
    legacy.parent.mkdir(parents=True, exist_ok=True)
    canonical.replace(legacy)
    plan = driver.json(workspace, ["workspace", "migration", "plan"])
    if len(plan.get("actions", [])) != 1:
        raise ValueError("legacy package fixture did not produce exactly one known migration")
    return plan, legacy, canonical


def prove_first_run(driver: Driver, root: Path) -> None:
    workspace = root / "Fresh first run Ω"
    for arguments in (
        ["--workspace", str(workspace)],
        ["--workspace", str(workspace), "--help"],
        ["--workspace", str(workspace), "--version"],
    ):
        driver.raw(arguments)
        if workspace.exists():
            raise ValueError("startup/help/version created a workspace")
    inspected = driver.json(workspace, ["workspace", "migration", "inspect"])
    first = driver.json(workspace, ["workspace", "migration", "plan"])
    second = driver.json(workspace, ["workspace", "migration", "plan"])
    if first != second or inspected.get("state") != "migration_available":
        raise ValueError("fresh first-run inspection or planning is nondeterministic")
    applied = driver.json(workspace, apply_arguments(first, "package-first-run"))
    replayed = driver.json(workspace, apply_arguments(first, "package-first-run"))
    healthy = driver.json(workspace, ["workspace", "migration", "inspect"])
    if applied != replayed or healthy.get("state") != "healthy":
        raise ValueError("first-run creation was not healthy and exactly idempotent")


def prove_migration_and_rollback(driver: Driver, root: Path) -> None:
    workspace = root / "Known old workspace"
    plan, legacy, canonical = prepare_legacy(driver, workspace)
    if plan != driver.json(workspace, ["workspace", "migration", "plan"]):
        raise ValueError("known migration plan is not deterministic")
    unknown = workspace / "operator-owned-note.txt"
    unknown.write_text("preserve\n", encoding="utf-8")
    original = sha256(legacy)
    applied = driver.json(workspace, apply_arguments(plan, "package-known-old"))
    replayed = driver.json(workspace, apply_arguments(plan, "package-known-old"))
    if applied != replayed or not canonical.is_file() or not unknown.is_file():
        raise ValueError("known migration was not idempotent or preserved unknown content")
    rollback = control_arguments(
        "rollback",
        "operation-package-known-old",
        str(applied["resulting_workspace_revision"]),
        "package-rollback",
    )
    rolled_back = driver.json(workspace, rollback)
    if (
        rolled_back.get("state") != "rolled_back"
        or canonical.exists()
        or sha256(legacy) != original
        or not unknown.is_file()
    ):
        raise ValueError("rollback did not restore the bound original digest")
    if driver.json(workspace, rollback) != rolled_back:
        raise ValueError("rollback did not replay idempotently")


def prove_stale_and_future_refusals(driver: Driver, root: Path) -> None:
    workspace = root / "Stale plan"
    plan, _legacy, canonical = prepare_legacy(driver, workspace)
    stale = apply_arguments(plan, "package-stale")
    stale[stale.index("--expected-revision") + 1] = "0" * 64
    driver.json(
        workspace,
        stale,
        expected=1,
        error_code="workspace_migration_stale_plan",
    )
    if canonical.exists():
        raise ValueError("stale migration request produced an effect")

    future = root / "Unsupported future workspace"
    future.mkdir()
    manifest = future / "workspace.v1.json"
    manifest.write_text(
        json.dumps(
            {
                "schema": "facman.factorio.workspace.v2",
                "workspace_id": "future",
                "layout_version": 2,
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    before = sha256(manifest)
    driver.json(
        future,
        ["workspace", "migration", "inspect"],
        expected=1,
        error_code="workspace_layout_future_or_unknown",
    )
    if sha256(manifest) != before:
        raise ValueError("unsupported future workspace was mutated")


def prove_recovery_boundaries(driver: Driver, root: Path) -> None:
    for boundary in FAULT_BOUNDARIES:
        suffix = re.sub(r"[^a-z0-9]+", "-", boundary).strip("-")
        workspace = root / f"Recovery {suffix}"
        plan, _legacy, canonical = prepare_legacy(driver, workspace)
        arguments = apply_arguments(plan, f"package-{suffix}")
        environment = os.environ.copy()
        environment["FACMAN_TEST_WORKSPACE_MIGRATION_FAULT"] = boundary
        driver.json(
            workspace,
            arguments,
            expected=1,
            error_code="workspace_migration_interrupted",
            environment=environment,
        )
        operation_id = f"operation-package-{suffix}"
        inspection = driver.json(
            workspace,
            ["workspace", "migration", "operation", "inspect", operation_id],
        )
        recovered = driver.json(
            workspace,
            control_arguments(
                "recover",
                operation_id,
                str(inspection["observed_workspace_revision"]),
                f"recover-{suffix}",
            ),
        )
        if recovered.get("state") != "completed" or not canonical.is_file():
            raise ValueError(f"migration did not recover at boundary {boundary}")


def prove_prejournal_boundaries(driver: Driver, root: Path) -> None:
    for index, boundary in enumerate(PREJOURNAL_FAULT_BOUNDARIES, start=1):
        suffix = re.sub(r"[^a-z0-9]+", "-", boundary).strip("-")
        workspace = root / f"Prejournal {suffix}"
        plan, _legacy, canonical = prepare_legacy(driver, workspace)
        arguments = apply_arguments(plan, f"package-prejournal-{index}")
        environment = os.environ.copy()
        environment["FACMAN_TEST_WORKSPACE_MIGRATION_FAULT"] = boundary
        driver.json(
            workspace,
            arguments,
            expected=1,
            error_code="workspace_migration_interrupted",
            environment=environment,
        )
        journals = list(
            (workspace / "transactions/workspace-migrations").glob(
                "*.workspace-migration.v2.json"
            )
        )
        if canonical.exists() or journals:
            raise ValueError(f"pre-journal boundary {boundary} produced an effect")
        recovered = driver.json(workspace, arguments)
        if recovered.get("state") != "completed" or not canonical.is_file():
            raise ValueError(f"pre-journal boundary {boundary} was not exactly retryable")


def prove_creation_boundaries(driver: Driver, root: Path) -> None:
    for index, boundary in enumerate(CREATION_FAULT_BOUNDARIES, start=1):
        suffix = re.sub(r"[^a-z0-9]+", "-", boundary).strip("-")
        workspace = root / f"Creation {suffix}"
        plan = driver.json(workspace, ["workspace", "migration", "plan"])
        arguments = apply_arguments(plan, f"package-creation-{index}")
        environment = os.environ.copy()
        environment["FACMAN_TEST_WORKSPACE_MIGRATION_FAULT"] = boundary
        driver.json(
            workspace,
            arguments,
            expected=1,
            error_code="workspace_migration_interrupted",
            environment=environment,
        )
        if boundary in {
            "after_creation_lock_acquisition",
            "before_creation_journal",
        }:
            replanned = driver.json(
                workspace, ["workspace", "migration", "plan"]
            )
            recovered = driver.json(
                workspace,
                apply_arguments(replanned, f"package-creation-{index}-retry"),
            )
        else:
            recovered = driver.json(workspace, arguments)
        healthy = driver.json(
            workspace, ["workspace", "migration", "inspect"]
        )
        if recovered.get("state") != "completed" or healthy.get("state") != "healthy":
            raise ValueError(f"creation boundary {boundary} did not recover safely")


def prove_root_and_writer_conflicts(driver: Driver, root: Path) -> None:
    contended = root / "Concurrent writer"
    plan, _legacy, canonical = prepare_legacy(driver, contended)
    lock = contended / "transactions/workspace-migrations/workspace-migration.lock"
    with held_migration_lock(lock):
        driver.json(
            contended,
            apply_arguments(plan, "package-contended"),
            expected=1,
            error_code="workspace_migration_conflict",
        )
    if canonical.exists():
        raise ValueError("concurrent-writer refusal produced a target effect")

    substituted = root / "Root substitution"
    plan, _legacy, canonical = prepare_legacy(driver, substituted)
    displaced = root / "Displaced original root"
    substituted.replace(displaced)
    shutil.copytree(displaced, substituted)
    driver.json(
        substituted,
        apply_arguments(plan, "package-root-substitution"),
        expected=1,
        error_code="workspace_migration_stale_plan",
    )
    if canonical.exists():
        raise ValueError("replacement workspace root received a migration effect")


def prove_idempotency_and_backup_conflicts(driver: Driver, root: Path) -> None:
    idempotency = root / "Idempotency conflict"
    plan, _legacy, _canonical = prepare_legacy(driver, idempotency)
    arguments = apply_arguments(plan, "package-idempotency-conflict")
    driver.json(idempotency, arguments)
    conflicting = list(arguments)
    conflicting[conflicting.index("--plan-digest") + 1] = "0" * 64
    driver.json(
        idempotency,
        conflicting,
        expected=1,
        error_code="workspace_migration_conflict",
    )

    backup = root / "Backup corruption"
    plan, legacy, canonical = prepare_legacy(driver, backup)
    applied = driver.json(
        backup, apply_arguments(plan, "package-backup-corruption")
    )
    committed_digest = sha256(canonical)
    retained_source_digest = sha256(legacy)
    backup_file = (
        backup
        / "transactions/workspace-migrations/operation-package-backup-corruption.data/0.source.json"
    )
    backup_file.write_text("{}\n", encoding="utf-8")
    driver.json(
        backup,
        control_arguments(
            "rollback",
            "operation-package-backup-corruption",
            str(applied["resulting_workspace_revision"]),
            "package-backup-corruption-control",
        ),
        expected=1,
        error_code="workspace_migration_recovery_required",
    )
    if (
        not canonical.is_file()
        or not legacy.is_file()
        or sha256(canonical) != committed_digest
        or sha256(legacy) != retained_source_digest
    ):
        raise ValueError("corrupt backup refusal changed committed workspace state")


def prove_corrupt_evidence_refusal(driver: Driver, root: Path) -> None:
    workspace = root / "Corrupt journal"
    prepare_legacy(driver, workspace)
    journal_root = workspace / "transactions/workspace-migrations"
    journal_root.mkdir(parents=True, exist_ok=True)
    journal = journal_root / "operation-corrupt.workspace-migration.v2.json"
    journal.write_text('{"schema":"facman.workspace_migration_journal.v2"', encoding="utf-8")
    driver.json(
        workspace,
        [
            "workspace", "migration", "operation", "inspect", "operation-corrupt",
        ],
        expected=1,
        error_code="json_missing_comma",
    )


def prove_staging_corruption_refusal(driver: Driver, root: Path) -> None:
    workspace = root / "Staging corruption"
    plan, _legacy, canonical = prepare_legacy(driver, workspace)
    environment = os.environ.copy()
    environment["FACMAN_TEST_WORKSPACE_MIGRATION_FAULT"] = "after_staged_file:1"
    driver.json(
        workspace,
        apply_arguments(plan, "package-staging-corrupt"),
        expected=1,
        error_code="workspace_migration_interrupted",
        environment=environment,
    )
    data = workspace / "transactions/workspace-migrations/operation-package-staging-corrupt.data/0.target.json"
    data.write_text("{}\n", encoding="utf-8")
    inspection = driver.json(
        workspace,
        [
            "workspace", "migration", "operation", "inspect",
            "operation-package-staging-corrupt",
        ],
    )
    driver.json(
        workspace,
        control_arguments(
            "recover",
            "operation-package-staging-corrupt",
            str(inspection["observed_workspace_revision"]),
            "recover-staging-corrupt",
        ),
        expected=1,
        error_code="workspace_migration_conflict",
    )
    if canonical.exists():
        raise ValueError("corrupt staging was committed")


def prove_rollback_recovery_boundary(driver: Driver, root: Path) -> None:
    workspace = root / "Rollback recovery"
    plan, legacy, canonical = prepare_legacy(driver, workspace)
    original = sha256(legacy)
    applied = driver.json(
        workspace, apply_arguments(plan, "package-rollback-recovery")
    )
    rollback = control_arguments(
        "rollback",
        "operation-package-rollback-recovery",
        str(applied["resulting_workspace_revision"]),
        "package-rollback-recovery-control",
    )
    environment = os.environ.copy()
    environment["FACMAN_TEST_WORKSPACE_MIGRATION_FAULT"] = ROLLBACK_FAULT_BOUNDARY
    driver.json(
        workspace,
        rollback,
        expected=1,
        error_code="workspace_migration_interrupted",
        environment=environment,
    )
    inspection = driver.json(
        workspace,
        [
            "workspace", "migration", "operation", "inspect",
            "operation-package-rollback-recovery",
        ],
    )
    recovered = driver.json(
        workspace,
        control_arguments(
            "recover",
            "operation-package-rollback-recovery",
            str(inspection["observed_workspace_revision"]),
            "recover-package-rollback",
        ),
    )
    if (
        recovered.get("state") != "rolled_back"
        or canonical.exists()
        or sha256(legacy) != original
    ):
        raise ValueError("interrupted rollback did not recover to the bound original")


def prove(
    executable: Path,
    profile: str,
    package_mode: str,
) -> dict[str, Any]:
    if profile not in ACTIVE_PROFILES:
        raise ValueError(f"workspace lifecycle proof requires an active product profile: {profile}")
    if package_mode not in {"portable", "installed_stage"}:
        raise ValueError(f"unknown package mode: {package_mode}")
    if not FIXTURE_INSTALL.is_dir():
        raise ValueError(f"Factorio install fixture is missing: {FIXTURE_INSTALL}")
    executable = executable.resolve(strict=True)
    with tempfile.TemporaryDirectory(prefix="facman-package-workspace-lifecycle-") as temporary:
        root = Path(temporary)
        arbitrary_cwd = root / "Arbitrary current directory"
        arbitrary_cwd.mkdir()
        driver = Driver(executable, arbitrary_cwd)
        cases = (
            ("portable_or_installed_first_run", prove_first_run),
            ("known_migration_idempotency_and_rollback", prove_migration_and_rollback),
            ("stale_and_future_refusal", prove_stale_and_future_refusals),
            ("prejournal_interruption_and_exact_retry", prove_prejournal_boundaries),
            ("creation_interruption_and_recovery", prove_creation_boundaries),
            ("journaled_interruption_and_process_restart", prove_recovery_boundaries),
            ("root_substitution_and_concurrent_writer_refusal", prove_root_and_writer_conflicts),
            ("idempotency_and_backup_conflict_refusal", prove_idempotency_and_backup_conflicts),
            ("corrupt_journal_refusal", prove_corrupt_evidence_refusal),
            ("staging_corruption_refusal", prove_staging_corruption_refusal),
            ("rollback_interruption_recovery", prove_rollback_recovery_boundary),
        )
        completed: list[dict[str, str]] = []
        for case_id, check in cases:
            case_root = root / case_id
            case_root.mkdir()
            check(driver, case_root)
            completed.append({"id": case_id, "status": "pass"})
    return {
        "schema": "facman.workspace_lifecycle_package_proof.v1",
        "status": "pass",
        "profile_id": profile,
        "package_mode": package_mode,
        "platform": sys.platform,
        "source_revision": source_revision(),
        "source_tree": source_tree(),
        "source_dirty": source_dirty(),
        "executable_sha256": sha256(executable),
        "cases": completed,
        "fault_boundaries": [
            *PREJOURNAL_FAULT_BOUNDARIES,
            *CREATION_FAULT_BOUNDARIES,
            *FAULT_BOUNDARIES,
            ROLLBACK_FAULT_BOUNDARY,
        ],
        "authority": {
            "release": False,
            "tagging": False,
            "signing": False,
            "publication": False,
            "human_acceptance": False,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--executable", type=Path, required=True)
    parser.add_argument("--profile", choices=sorted(ACTIVE_PROFILES), required=True)
    parser.add_argument(
        "--package-mode", choices=("portable", "installed_stage"), required=True
    )
    parser.add_argument("--evidence", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        report = prove(args.executable, args.profile, args.package_mode)
        schema = json_contract.load_schema(
            ROOT
            / "contracts/schema/release/facman_workspace_lifecycle_package_proof.v1.schema.json"
        )
        problems = json_contract.validate(report, schema)
        if problems:
            raise ValueError("workspace lifecycle proof violates its schema: " + "; ".join(problems))
        evidence = args.evidence.resolve()
        evidence.parent.mkdir(parents=True, exist_ok=True)
        evidence.write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        print(f"workspace-lifecycle-package-proof: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
