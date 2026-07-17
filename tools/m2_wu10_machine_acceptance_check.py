# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

"""Independent M2 synthetic-portable evidence verifier.

This module intentionally uses only the Python standard library and does not
import Universal Setup, the acceptance runner, or FacMan runtime code.  The
policy-only path is safe on every platform.  Live verification is restricted
to the frozen Windows acceptance root and derives EvidencePass from retained
bytes rather than trusting success fields emitted by the runner. The later
result record may say MachinePass only after it also binds every required local
and hosted exact-head validation gate.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
import zipfile
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "contracts/policy/m2_synthetic_portable_acceptance_policy.v1.json"
POLICY_REPOSITORY_PATH = "contracts/policy/m2_synthetic_portable_acceptance_policy.v1.json"
VERIFIER_REPOSITORY_PATH = "tools/m2_wu10_machine_acceptance_check.py"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
REVISION_RE = re.compile(r"^[0-9a-f]{40}$")
RUN_ID_RE = re.compile(r"^m2wu10-[0-9]{8}-[0-9]{2}$")
INTERRUPTION_RUN_ID_RE = re.compile(r"^m2wu10-[0-9]{8}-[0-9]{2}-interruptions$")

EXPECTED_POLICY_TOP_LEVEL = {
    "schema", "policy_id", "status", "scope", "revision_binding",
    "synthetic_archive", "retained_lifecycle", "interruption_recovery",
    "required_validation", "technical_acceptance", "authority_on_machine_pass",
    "required_negative_controls",
}
EXPECTED_AUTHORITY = {
    "local_managed_portable_setup": "candidate",
    "verified_launcher_handoff": "candidate",
    "facman_local_managed_setup_candidate": True,
    "factorio_archive_acceptance": False,
    "existing_factorio_mutation": False,
    "existing_installation_adoption": False,
    "steam_mutation": False,
    "steam_cloud_mutation": False,
    "network": False,
    "credentials": False,
    "registry": False,
    "shortcuts": False,
    "elevation": False,
    "system_wide_installation": False,
    "run_execute": False,
    "h1_inference": "none",
    "signing": False,
    "publication": False,
}
EXPECTED_NEGATIVE_CONTROLS = [
    "alter_acceptance_summary",
    "alter_synthetic_archive",
    "alter_evidence_packet",
    "break_audit_chain_linkage",
    "add_reparse_point",
    "add_unexpected_retained_file",
    "change_expected_tree_counts",
    "recreate_moved_product",
    "remove_installed_product",
    "target_outside_acceptance_root",
    "change_provider_revision",
    "promote_excluded_authority",
]
FORBIDDEN_EXECUTABLE_SUFFIXES = {
    ".app", ".bat", ".bin", ".cmd", ".com", ".dll", ".dylib", ".exe",
    ".jar", ".msi", ".ps1", ".scr", ".sh", ".so",
}
EXECUTABLE_MAGICS = (
    b"MZ", b"\x7fELF", b"\xfe\xed\xfa\xce", b"\xce\xfa\xed\xfe",
    b"\xfe\xed\xfa\xcf", b"\xcf\xfa\xed\xfe", b"\xca\xfe\xba\xbe",
)


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_policy(path: Path = POLICY_PATH) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("machine acceptance policy must be an object")
    return value


def _exact_keys(value: Any, expected: set[str], label: str, problems: list[str]) -> bool:
    if not isinstance(value, dict):
        problems.append(f"{label} must be an object")
        return False
    if set(value) != expected:
        problems.append(f"{label} members changed")
        return False
    return True


def validate_policy(policy: dict[str, Any]) -> list[str]:
    """Validate the frozen authority policy without evaluating any run."""
    problems: list[str] = []
    _exact_keys(policy, EXPECTED_POLICY_TOP_LEVEL, "policy", problems)
    if [policy.get("schema"), policy.get("policy_id"), policy.get("status")] != [
        "factorio.m2_synthetic_portable_acceptance_policy.v1",
        "facman.m2.synthetic_portable_acceptance.v1",
        "frozen_criteria_no_result",
    ]:
        problems.append("policy identity or no-result state changed")

    scope = policy.get("scope", {})
    if scope != {
        "acceptance_root": r"D:\FacMan-Live-Acceptance\M2",
        "root_requirement": "new_exclusive_disposable_children_only",
        "target_class": "operator_acceptance",
        "archive_kind": "non_executable_synthetic_zip",
        "real_factorio_allowed": False,
        "existing_installation_allowed": False,
    }:
        problems.append("synthetic acceptance scope changed")
    revisions = policy.get("revision_binding", {})
    if revisions != {
        "universal_setup_runner": "3f8489275077347c2918f3bb03614ec6431362ff",
        "factorio_launcher_consumer": "accepted_policy_revision",
        "verifier": "accepted_policy_revision",
        "result": "separate_later_revision",
    }:
        problems.append("policy revision separation changed")

    archive = policy.get("synthetic_archive", {})
    expected_archive_entries = [
        ("product/README.txt", "85b5051362ff0e52688756d1054f0a0857a4334f97408c737b704e1ab887a9ba", 48),
        ("product/config/settings.ini", "839de304a01dfeac9ae13fc74dff983142b97cc5fba70fa4881fa29857741033", 29),
        ("product/data/payload.dat", "3b631c7346704df508f535d800fe5f052d5ef39b026885937e221bb81aa729d9", 18),
    ]
    archive_entries = archive.get("entries", []) if isinstance(archive, dict) else []
    if (
        not isinstance(archive, dict)
        or archive.get("sha256") != "02bed514abfac0145cb8e57008aeff3f2107715ea8a3f57ebed78ce456b2ddbf"
        or archive.get("contains_executable_code") is not False
        or [(item.get("path"), item.get("sha256"), item.get("size_bytes")) for item in archive_entries
            if isinstance(item, dict)] != expected_archive_entries
    ):
        problems.append("non-executable synthetic archive contract changed")

    lifecycle = policy.get("retained_lifecycle", {})
    expected_steps = [
        ["install_plan", "reviewed"], ["install_apply", "completed"],
        ["install_verify", "pass"], ["damage_verify", "expected_fail"],
        ["repair", "pass"], ["same_volume_move", "pass_old_root_retained"],
        ["cross_volume_move", "not_attempted_no_second_authorized_volume"],
        ["uninstall_with_foreign_content", "refused_and_retained"],
        ["operator_exact_foreign_file_removal", "completed_by_runner_not_setup"],
        ["clean_uninstall", "pass"],
    ]
    if not isinstance(lifecycle, dict) or [
        lifecycle.get("file_count"), lifecycle.get("directory_count"),
        lifecycle.get("total_bytes"), lifecycle.get("reparse_point_count"),
    ] != [26, 14, 40105, 0]:
        problems.append("retained tree identity changed")
    if isinstance(lifecycle, dict) and (
        lifecycle.get("steps") != expected_steps
        or lifecycle.get("evidence_operations") != ["install_local", "repair", "move", "uninstall"]
        or lifecycle.get("audit_operations") != ["install_local", "install_local", "repair", "move", "uninstall"]
        or lifecycle.get("audit_event_count") != 5
        or lifecycle.get("installed_product") != "present_exact_owned_closure"
        or lifecycle.get("moved_product") != "absent_after_clean_uninstall"
        or lifecycle.get("operator_note") != "absent"
        or lifecycle.get("committed_closure") != "removed"
        or lifecycle.get("recovery_status") != "not_required"
    ):
        problems.append("retained lifecycle requirements changed")

    interruption = policy.get("interruption_recovery", {})
    if interruption != {
        "schema": "usk.interruption_acceptance_summary.v1",
        "case_count": 11,
        "unchanged": 1,
        "rolled_back": 4,
        "completed": 3,
        "recovery_required": 3,
        "journal_count": 14,
        "fresh_rerun_required": True,
    }:
        problems.append("interruption and recovery criteria changed")
    required_validation = policy.get("required_validation", {})
    if required_validation != {
        "exact_head_required": True,
        "local": [
            "policy_only", "negative_controls", "strict", "native_ctest",
            "python_unittest", "required_package_proof", "reproducible_workspace",
        ],
        "hosted": [
            "windows_native_package", "linux", "macos", "sanitizers",
            "bounded_fuzzers", "coverage", "codeql", "schema",
            "security_policy", "release_policy",
        ],
    }:
        problems.append("required local or hosted validation gates changed")
    technical = policy.get("technical_acceptance", {})
    if technical != {
        "requirement": "required",
        "success_result": "MachinePass",
        "human_review": "not_required_for_synthetic_non_executable_lane",
        "current_result_recorded": False,
    }:
        problems.append("MachinePass or no-result policy state changed")
    if policy.get("authority_on_machine_pass") != EXPECTED_AUTHORITY:
        problems.append("MachinePass authority boundary changed")
    if policy.get("required_negative_controls") != EXPECTED_NEGATIVE_CONTROLS:
        problems.append("required negative-control set changed")
    if any(key in policy for key in ("result", "verified_at", "evidence_digest")):
        problems.append("policy revision must not record a current acceptance result")
    return problems


def _is_reparse_or_link(path: Path) -> bool:
    try:
        info = path.stat(follow_symlinks=False)
    except OSError:
        return True
    attributes = getattr(info, "st_file_attributes", 0)
    return stat.S_ISLNK(info.st_mode) or bool(attributes & getattr(os, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))


def _inventory(root: Path) -> tuple[list[Path], list[Path], list[str]]:
    files: list[Path] = []
    directories: list[Path] = []
    problems: list[str] = []
    if not root.is_dir() or _is_reparse_or_link(root):
        return files, directories, [f"acceptance root is missing, linked, or reparse-backed: {root}"]
    for current, names, filenames in os.walk(root, followlinks=False):
        current_path = Path(current)
        safe_names: list[str] = []
        for name in sorted(names):
            path = current_path / name
            directories.append(path)
            if _is_reparse_or_link(path):
                problems.append(f"retained tree contains a link or reparse point: {path}")
            else:
                safe_names.append(name)
        names[:] = safe_names
        for name in sorted(filenames):
            path = current_path / name
            files.append(path)
            if _is_reparse_or_link(path) or not path.is_file():
                problems.append(f"retained tree contains a linked or unsupported file: {path}")
    return files, directories, problems


def _relative(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _safe_relative(value: str) -> bool:
    path = PurePosixPath(value.replace("\\", "/"))
    return bool(value) and not path.is_absolute() and ".." not in path.parts and "." not in path.parts


def _within(root: Path, candidate: Path) -> bool:
    try:
        root_value = os.path.normcase(str(root.resolve(strict=False)))
        candidate_value = os.path.normcase(str(candidate.resolve(strict=False)))
        return os.path.commonpath([root_value, candidate_value]) == root_value
    except (OSError, ValueError):
        return False


def _declared_path(value: Any, run_root: Path, label: str, problems: list[str]) -> Path | None:
    if not isinstance(value, str) or not value:
        problems.append(f"{label} is not an absolute path")
        return None
    path = Path(value)
    if not path.is_absolute() or not _within(run_root, path):
        problems.append(f"{label} escapes the accepted run root")
        return None
    return path


def _load_canonical_json(
    path: Path,
    label: str,
    problems: list[str],
    *,
    require_canonical: bool = True,
) -> dict[str, Any] | None:
    try:
        raw = path.read_bytes()
        value = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        problems.append(f"{label} is unreadable JSON: {exc}")
        return None
    if not isinstance(value, dict):
        problems.append(f"{label} must be a JSON object")
        return None
    if require_canonical and raw not in {
        canonical_bytes(value), canonical_bytes(value) + b"\n",
        canonical_bytes(value) + b"\r\n",
    }:
        problems.append(f"{label} is not canonical JSON")
    return value


def _digest_without(value: dict[str, Any], key: str) -> str:
    payload = dict(value)
    payload.pop(key, None)
    return sha256_bytes(canonical_bytes(payload))


def _snapshot(root: Path) -> str:
    if not root.exists():
        return sha256_bytes(canonical_bytes({"entries": [], "state": "nonexistent"}))
    entries: list[dict[str, Any]] = []
    files, directories, problems = _inventory(root)
    if problems:
        raise ValueError("; ".join(problems))
    for path in directories:
        entries.append({"relative_path": _relative(path, root), "type": "directory"})
    for path in files:
        entries.append({
            "relative_path": _relative(path, root), "sha256": sha256_file(path),
            "size_bytes": path.stat().st_size, "type": "file",
        })
    entries.sort(key=lambda item: item["relative_path"])
    return sha256_bytes(canonical_bytes({"entries": entries, "state": "directory"}))


def _expected_paths(run_id: str) -> tuple[set[str], set[str]]:
    audit = f"audit.synthetic.m2.{run_id}"
    packet_root = "setup-state/evidence/packets"
    state_root = "setup-state/state"
    files = {
        "acceptance-summary.json", "synthetic-product.zip",
        "installed-product/README.txt", "installed-product/config/settings.ini",
        "installed-product/data/payload.dat", "setup-state/.usk-owned-root.v1.json",
        *(f"setup-state/audit/chains/{audit}/{index:020d}.event.json" for index in range(5)),
        *(f"{packet_root}/evidence.{operation}.{run_id}.json" for operation in ("install", "repair", "move", "uninstall")),
        *(f"{state_root}/installed/synthetic.m2.{run_id}.tx.{operation}.{run_id}.json"
          for operation in ("install", "repair", "move")),
        f"{state_root}/installed/synthetic.m2.{run_id}.tx.uninstall.clean.{run_id}.json",
        *(f"{state_root}/ownership/ownership.synthetic.m2.{run_id}.tx.{operation}.{run_id}.json"
          for operation in ("install", "repair", "move")),
        *(f"{state_root}/transactions/tx.{operation}.{run_id}.journal.json"
          for operation in ("install", "repair", "move")),
        f"{state_root}/transactions/tx.uninstall.clean.{run_id}.journal.json",
    }
    directories = {
        "installed-product", "installed-product/config", "installed-product/data",
        "setup-state", "setup-state/audit", "setup-state/audit/chains",
        f"setup-state/audit/chains/{audit}", "setup-state/evidence",
        "setup-state/evidence/packets", "setup-state/staging", "setup-state/state",
        "setup-state/state/installed", "setup-state/state/ownership",
        "setup-state/state/transactions",
    }
    return files, directories


def _verify_archive(path: Path, policy: dict[str, Any], problems: list[str]) -> dict[str, Any]:
    archive_policy = policy["synthetic_archive"]
    digest = sha256_file(path) if path.is_file() else ""
    if digest != archive_policy["sha256"]:
        problems.append("synthetic archive digest differs from frozen policy")
    observed: list[dict[str, Any]] = []
    try:
        with zipfile.ZipFile(path, "r") as archive:
            for info in sorted(archive.infolist(), key=lambda item: item.filename):
                name = info.filename
                if not _safe_relative(name) or name.endswith("/"):
                    problems.append(f"synthetic archive contains unsafe or unexpected entry: {name}")
                    continue
                unix_mode = (info.external_attr >> 16) & 0xFFFF
                if stat.S_IFMT(unix_mode) == stat.S_IFLNK:
                    problems.append(f"synthetic archive contains a link: {name}")
                data = archive.read(info)
                suffix = PurePosixPath(name).suffix.lower()
                if suffix in FORBIDDEN_EXECUTABLE_SUFFIXES or any(data.startswith(magic) for magic in EXECUTABLE_MAGICS):
                    problems.append(f"synthetic archive contains executable content: {name}")
                observed.append({"path": name, "sha256": sha256_bytes(data), "size_bytes": len(data)})
    except (OSError, zipfile.BadZipFile, RuntimeError) as exc:
        problems.append(f"synthetic archive is unreadable: {exc}")
    if observed != archive_policy["entries"]:
        problems.append("synthetic archive entry closure differs from frozen policy")
    return {"sha256": digest, "entries": observed, "contains_executable_code": False}


def _journal_digest(transitions: Iterable[dict[str, Any]]) -> str:
    chunks: list[bytes] = []
    for item in transitions:
        from_value = item.get("from")
        chunks.append(
            str(item.get("sequence")).encode("utf-8") + b"\0"
            + (b"" if from_value is None else str(from_value).encode("utf-8")) + b"\0"
            + str(item.get("to")).encode("utf-8") + b"\0"
            + str(item.get("recorded_at")).encode("utf-8") + b"\n"
        )
    return sha256_bytes(b"".join(chunks))


def _verify_journal(
    path: Path,
    run_root: Path,
    problems: list[str],
    *,
    require_completed: bool = True,
) -> dict[str, Any] | None:
    # Universal Setup journals use a deterministic native field order rather
    # than sorted-key canonical JSON. Their authority comes from the parsed
    # schema, transition chain, contained roots, and recomputed journal digest,
    # all of which are checked below.
    document = _load_canonical_json(
        path, f"journal {path.name}", problems, require_canonical=False,
    )
    if document is None:
        return None
    transitions = document.get("transitions")
    if document.get("schema") != "usk.transaction_journal.v1" or not isinstance(transitions, list) or not transitions:
        problems.append(f"journal {path.name} has an unexpected schema or empty transition chain")
        return document
    prior: str | None = None
    expected_states = ["created", "validated", "planned", "staging", "staged", "verified", "committing", "committed", "completed"]
    observed_states: list[str] = []
    transaction_id = document.get("transaction_id")
    for index, item in enumerate(transitions):
        if not isinstance(item, dict):
            problems.append(f"journal {path.name} transition {index} is not an object")
            continue
        observed_states.append(str(item.get("to")))
        if (
            item.get("sequence") != index or item.get("from") != prior
            or item.get("transition_id") != f"{transaction_id}.{index}"
            or item.get("durable_before_external_visibility") is not True
        ):
            problems.append(f"journal {path.name} transition chain is invalid at {index}")
        prior = item.get("to")
    if require_completed:
        if observed_states != expected_states or document.get("current_state") != "completed":
            problems.append(f"journal {path.name} does not prove the complete durable lifecycle")
    elif document.get("current_state") != prior:
        problems.append(f"journal {path.name} current state differs from its transition chain")
    if document.get("journal_digest") != _journal_digest(transitions):
        problems.append(f"journal {path.name} digest does not match its transition bytes")
    roots = document.get("roots")
    if not isinstance(roots, list) or len(roots) != 4:
        problems.append(f"journal {path.name} must bind exactly four roots")
    else:
        roles: set[str] = set()
        for item in roots:
            if not isinstance(item, dict):
                problems.append(f"journal {path.name} root entry is invalid")
                continue
            role = item.get("role")
            if not isinstance(role, str) or role in roles:
                problems.append(f"journal {path.name} root roles are invalid")
            roles.add(str(role))
            _declared_path(item.get("root"), run_root, f"journal {path.name} {role} root", problems)
        if roles != {"target", "staging", "setup_state", "audit"}:
            problems.append(f"journal {path.name} root authority set changed")
    return document


def _verify_revision_binding(policy_revision: str, policy: dict[str, Any], problems: list[str]) -> None:
    if not REVISION_RE.fullmatch(policy_revision):
        problems.append("accepted policy revision is not an exact Git SHA")
        return
    for repository_path, local_path, label in (
        (POLICY_REPOSITORY_PATH, POLICY_PATH, "policy"),
        (VERIFIER_REPOSITORY_PATH, Path(__file__).resolve(), "verifier"),
    ):
        try:
            frozen = subprocess.run(
                ["git", "show", f"{policy_revision}:{repository_path}"], cwd=ROOT,
                check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            ).stdout
            local = local_path.read_bytes()
        except (OSError, subprocess.CalledProcessError) as exc:
            problems.append(f"cannot resolve frozen {label} at accepted policy revision: {exc}")
            continue
        if frozen.replace(b"\r\n", b"\n") != local.replace(b"\r\n", b"\n"):
            problems.append(f"local {label} differs from accepted policy revision")
    if policy.get("revision_binding", {}).get("verifier") != "accepted_policy_revision":
        problems.append("policy no longer binds the verifier to the accepted policy revision")


def verify_evidence(
    policy: dict[str, Any],
    acceptance_root: Path,
    run_id: str,
    interruption_run_id: str,
    policy_revision: str,
    runner_revision: str,
    verifier_revision: str,
    verified_at: str,
    *,
    test_mode: bool = False,
    enforce_frozen_policy: bool = True,
) -> tuple[dict[str, Any] | None, list[str]]:
    """Derive an EvidencePass observation from retained bytes.

    test_mode exists only for unit tests and is not exposed by the CLI.
    """
    problems = validate_policy(policy) if enforce_frozen_policy else []
    if not test_mode:
        if os.name != "nt":
            problems.append("live M2 machine acceptance is restricted to Windows")
        if os.path.normcase(str(acceptance_root.resolve(strict=False))) != os.path.normcase(
            str(Path(policy.get("scope", {}).get("acceptance_root", "")).resolve(strict=False))
        ):
            problems.append("live verification root differs from the frozen authorized root")
        _verify_revision_binding(policy_revision, policy, problems)
    if not RUN_ID_RE.fullmatch(run_id):
        problems.append("lifecycle run id is invalid")
    if not INTERRUPTION_RUN_ID_RE.fullmatch(interruption_run_id):
        problems.append("interruption run id is invalid")
    if not REVISION_RE.fullmatch(runner_revision) or runner_revision != policy.get("revision_binding", {}).get("universal_setup_runner"):
        problems.append("runner revision differs from frozen policy")
    if not REVISION_RE.fullmatch(verifier_revision) or verifier_revision != policy_revision:
        problems.append("verifier revision must equal the accepted policy revision")
    try:
        parsed_time = datetime.fromisoformat(verified_at.replace("Z", "+00:00"))
        if parsed_time.tzinfo is None:
            raise ValueError("timezone required")
    except ValueError:
        problems.append("verified_at must be a timezone-aware ISO-8601 timestamp")

    run_root = acceptance_root / run_id
    interruption_root = acceptance_root / interruption_run_id
    if not _within(acceptance_root, run_root) or not _within(acceptance_root, interruption_root):
        problems.append("acceptance run roots escape the authorized root")
    files, directories, inventory_problems = _inventory(run_root)
    problems.extend(inventory_problems)
    lifecycle = policy.get("retained_lifecycle", {})
    observed_file_paths = {_relative(path, run_root) for path in files}
    observed_directory_paths = {_relative(path, run_root) for path in directories}
    expected_files, expected_directories = _expected_paths(run_id)
    if observed_file_paths != expected_files:
        problems.append("retained lifecycle file set differs from the frozen exact closure")
    if observed_directory_paths != expected_directories:
        problems.append("retained lifecycle directory set differs from the frozen exact closure")
    observed_bytes = sum(path.stat().st_size for path in files if path.is_file())
    if [len(files), len(directories), observed_bytes] != [
        lifecycle.get("file_count"), lifecycle.get("directory_count"), lifecycle.get("total_bytes"),
    ]:
        problems.append("retained lifecycle counts or total bytes differ from frozen policy")

    summary_path = run_root / "acceptance-summary.json"
    archive_path = run_root / "synthetic-product.zip"
    summary = _load_canonical_json(summary_path, "acceptance summary", problems)
    archive_observation = _verify_archive(archive_path, policy, problems)
    product_root = run_root / "installed-product"
    moved_root = run_root / "moved-product"
    if not product_root.is_dir():
        problems.append("installed-product is missing")
    if moved_root.exists():
        problems.append("moved-product must be absent after clean uninstall")
    if (product_root / "operator-note.txt").exists() or (moved_root / "operator-note.txt").exists():
        problems.append("temporary foreign-content file is present")
    product_files = []
    for expected in lifecycle.get("product_files", []):
        path = product_root / expected["path"]
        observed = {
            "path": expected["path"],
            "sha256": sha256_file(path) if path.is_file() else "",
            "size_bytes": path.stat().st_size if path.is_file() else -1,
        }
        product_files.append(observed)
    if product_files != lifecycle.get("product_files"):
        problems.append("retained harmless product closure differs from frozen policy")
    closure_snapshot = _snapshot(product_root) if product_root.is_dir() else ""
    absent_snapshot = _snapshot(moved_root)

    expected_steps = lifecycle.get("steps")
    if summary is not None:
        if summary.get("schema") != "usk.m2_live_acceptance_summary.v1" or summary.get("run_id") != run_id:
            problems.append("acceptance summary identity changed")
        summary_root = _declared_path(summary.get("run_root"), run_root, "summary run_root", problems)
        if summary_root is not None and summary_root.resolve(strict=False) != run_root.resolve(strict=False):
            problems.append("acceptance summary run_root is not the exact selected run")
        archive_summary = summary.get("archive", {})
        if not isinstance(archive_summary, dict) or archive_summary.get("sha256") != archive_observation["sha256"] or archive_summary.get("contains_executable_code") is not False:
            problems.append("acceptance summary archive binding changed")
        if isinstance(archive_summary, dict):
            summary_archive = _declared_path(archive_summary.get("path"), run_root, "summary archive path", problems)
            if summary_archive is not None and summary_archive.resolve(strict=False) != archive_path.resolve(strict=False):
                problems.append("acceptance summary archive path is not the retained synthetic archive")
        revisions = summary.get("source_revisions", {})
        if revisions != {"consumer": policy_revision, "universal_setup": runner_revision}:
            problems.append("acceptance summary source revisions do not bind policy and runner")
        observed_steps = [[item.get("name"), item.get("status")] for item in summary.get("steps", []) if isinstance(item, dict)]
        if observed_steps != expected_steps:
            problems.append("acceptance summary lifecycle sequence changed")
        if summary.get("authority") != {
            "acceptance_root": acceptance_root.as_posix(),
            "operator_verdict": "pending",
            "ordinary_live_apply_promoted": False,
            "run_execute_authorized": False,
        }:
            problems.append("runner summary attempted to promote excluded authority")

    marker = _load_canonical_json(run_root / "setup-state/.usk-owned-root.v1.json", "setup-owned root marker", problems)
    if marker is not None and marker.get("schema") != "usk.setup_owned_root.v1":
        problems.append("setup-owned root marker schema changed")
    if marker is not None and marker.get("acceptance_root") != acceptance_root.as_posix():
        problems.append("setup-owned root marker escapes the acceptance root")

    state_root = run_root / "setup-state/state"
    operations = ["install", "repair", "move", "uninstall"]
    journal_names = {
        "install": f"tx.install.{run_id}.journal.json",
        "repair": f"tx.repair.{run_id}.journal.json",
        "move": f"tx.move.{run_id}.journal.json",
        "uninstall": f"tx.uninstall.clean.{run_id}.journal.json",
    }
    plan_ids = {
        "install": f"plan.install.{run_id}",
        "repair": f"plan.repair.{run_id}",
        "move": f"plan.move.{run_id}",
        "uninstall": f"plan.uninstall.clean.{run_id}",
    }
    journals: dict[str, dict[str, Any]] = {}
    for operation in operations:
        journal = _verify_journal(state_root / "transactions" / journal_names[operation], run_root, problems)
        if journal is not None:
            journals[operation] = journal
            expected_operation = "install_local" if operation == "install" else operation
            if (
                journal.get("operation") != expected_operation
                or journal.get("plan_id") != plan_ids.get(operation)
            ):
                problems.append(f"{operation} journal operation or plan identity changed")

    ownership_names = {
        operation: f"ownership.synthetic.m2.{run_id}.tx.{operation}.{run_id}.json"
        for operation in ("install", "repair", "move")
    }
    ownerships: dict[str, dict[str, Any]] = {}
    expected_owned_files = lifecycle.get("product_files")
    for operation, name in ownership_names.items():
        document = _load_canonical_json(state_root / "ownership" / name, f"{operation} ownership", problems)
        if document is None:
            continue
        if document.get("manifest_digest") != _digest_without(document, "manifest_digest"):
            problems.append(f"{operation} ownership digest does not match canonical bytes")
        files_value = document.get("files", [])
        observed_owned = [
            {"path": item.get("relative_path"), "sha256": item.get("sha256"), "size_bytes": item.get("size_bytes")}
            for item in files_value if isinstance(item, dict)
        ]
        if observed_owned != expected_owned_files or document.get("directories") != [
            {"relative_path": "config"}, {"relative_path": "data"},
        ]:
            problems.append(f"{operation} ownership closure differs from retained product bytes")
        _declared_path(document.get("target_root"), run_root, f"{operation} ownership target", problems)
        expected_target = moved_root if operation == "move" else product_root
        if Path(str(document.get("target_root"))).resolve(strict=False) != expected_target.resolve(strict=False):
            problems.append(f"{operation} ownership target is not the expected lifecycle root")
        ownerships[operation] = document

    installed_names = {
        "install": f"synthetic.m2.{run_id}.tx.install.{run_id}.json",
        "repair": f"synthetic.m2.{run_id}.tx.repair.{run_id}.json",
        "move": f"synthetic.m2.{run_id}.tx.move.{run_id}.json",
        "uninstall": f"synthetic.m2.{run_id}.tx.uninstall.clean.{run_id}.json",
    }
    installed: dict[str, dict[str, Any]] = {}
    expected_lifecycle = {"install": "installed", "repair": "verified", "move": "move_pending_acceptance", "uninstall": "retired"}
    for operation, name in installed_names.items():
        document = _load_canonical_json(state_root / "installed" / name, f"{operation} installed state", problems)
        if document is None:
            continue
        if (
            document.get("schema") != "usk.installed_state.v1"
            or document.get("lifecycle_status") != expected_lifecycle[operation]
            or document.get("source_archive_digest") != archive_observation["sha256"]
            or document.get("setup_abi", {}).get("provider_revision") != runner_revision
        ):
            problems.append(f"{operation} installed state identity changed")
        _declared_path(document.get("target_root"), run_root, f"{operation} installed target", problems)
        expected_target = moved_root if operation in {"move", "uninstall"} else product_root
        if Path(str(document.get("target_root"))).resolve(strict=False) != expected_target.resolve(strict=False):
            problems.append(f"{operation} installed target is not the expected retained lifecycle root")
        owner_key = "move" if operation == "uninstall" else operation
        owner = ownerships.get(owner_key)
        if owner is not None and document.get("ownership_manifest_digest") != owner.get("manifest_digest"):
            problems.append(f"{operation} installed state does not bind its ownership manifest")
        installed[operation] = document

    audit_chain_id = f"audit.synthetic.m2.{run_id}"
    audit_root = run_root / "setup-state/audit/chains" / audit_chain_id
    audit_events: list[dict[str, Any]] = []
    previous: str | None = None
    for index in range(5):
        path = audit_root / f"{index:020d}.event.json"
        event = _load_canonical_json(path, f"audit event {index}", problems)
        if event is None:
            continue
        if (
            event.get("schema") != "usk.audit_event.v1" or event.get("sequence") != index
            or event.get("event_id") != f"{audit_chain_id}.{index}"
            or event.get("audit_chain_id") != audit_chain_id
            or event.get("previous_event_digest") != previous
            or event.get("event_digest") != _digest_without(event, "event_digest")
            or event.get("status") != "pass"
        ):
            problems.append(f"audit chain event {index} is invalid")
        previous = event.get("event_digest")
        audit_events.append(event)
    if [event.get("operation") for event in audit_events] != lifecycle.get("audit_operations"):
        problems.append("audit operation sequence changed")

    packet_root = run_root / "setup-state/evidence/packets"
    packet_file_operations = {"install": "install_local", "repair": "repair", "move": "move", "uninstall": "uninstall"}
    packet_observations: list[dict[str, Any]] = []
    packet_documents: dict[str, dict[str, Any]] = {}
    for operation in operations:
        path = packet_root / f"evidence.{operation}.{run_id}.json"
        packet = _load_canonical_json(path, f"{operation} evidence packet", problems)
        if packet is None:
            continue
        if packet.get("packet_digest") != _digest_without(packet, "packet_digest"):
            problems.append(f"{operation} evidence packet digest differs from canonical payload")
        expected_packet_id = f"evidence.{operation}.{run_id}"
        revisions = {item.get("repository_id"): item.get("revision") for item in packet.get("source_revisions", []) if isinstance(item, dict)}
        if (
            packet.get("schema") != "usk.live_target_evidence_packet.v1"
            or packet.get("packet_id") != expected_packet_id
            or packet.get("plan", {}).get("operation") != packet_file_operations[operation]
            or packet.get("archive", {}).get("sha256") != archive_observation["sha256"]
            or packet.get("setup_abi", {}).get("provider_revision") != runner_revision
            or revisions != {"product_consumer": policy_revision, "universal_setup": runner_revision}
            or packet.get("target", {}).get("target_class") != policy.get("scope", {}).get("target_class")
            or packet.get("operator_verdict") != {
                "recorded_at": None, "recorded_by": None, "statement_digest": None,
                "status": "pending", "verdict": None,
            }
            or packet.get("recovery", {}).get("status") != "not_required"
        ):
            problems.append(f"{operation} evidence packet identity or authority changed")
        closure = packet.get("committed_closure", {})
        expected_removed = operation == "uninstall"
        if not isinstance(closure, dict) or [
            closure.get("status"), closure.get("file_count"), closure.get("byte_count"),
        ] != (["removed", 0, 0] if expected_removed else ["committed", 3, 95]):
            problems.append(f"{operation} evidence packet closure changed")
        capabilities = packet.get("filesystem", {}).get("capabilities", {})
        if capabilities != {
            "local": True, "no_mount_redirection": True,
            "no_replace_commit": True, "stable_ancestors": True,
        }:
            problems.append(f"{operation} evidence packet filesystem containment changed")
        journal = journals.get(operation)
        if journal is not None:
            if packet.get("recovery", {}).get("journal_digest") != journal.get("journal_digest"):
                problems.append(f"{operation} packet does not bind the verified journal")
            if packet.get("plan", {}).get("plan_digest") != journal.get("plan_digest"):
                problems.append(f"{operation} packet plan does not bind the verified journal")
        packet_observations.append({
            "operation": packet_file_operations[operation], "relative_path": _relative(path, run_root),
            "file_sha256": sha256_file(path), "packet_digest": packet.get("packet_digest"),
            "plan_digest": packet.get("plan", {}).get("plan_digest"),
        })
        packet_documents[operation] = packet

    state_mapping = {"install": 1, "repair": 2, "move": 3, "uninstall": 4}
    owner_mapping = {"install": "install", "repair": "repair", "move": "move", "uninstall": "move"}
    for operation, audit_index in state_mapping.items():
        packet = packet_documents.get(operation)
        state = installed.get(operation)
        owner = ownerships.get(owner_mapping[operation])
        if packet is None or state is None or owner is None or audit_index >= len(audit_events):
            continue
        packet_state = packet.get("state", {})
        if packet_state != {
            "audit_chain_id": audit_chain_id,
            "audit_head_digest": audit_events[audit_index].get("event_digest"),
            "installed_state_digest": sha256_bytes(canonical_bytes(state)),
            "ownership_digest": owner.get("manifest_digest"),
        }:
            problems.append(f"{operation} packet state does not bind independently verified state")
        journal = journals.get(operation)
        if journal is not None and (
            audit_events[audit_index].get("plan_id") != journal.get("plan_id")
            or audit_events[audit_index].get("transaction_id") != journal.get("transaction_id")
        ):
            problems.append(f"{operation} audit event does not bind the verified transaction")

    if packet_documents:
        install_snapshots = packet_documents.get("install", {}).get("snapshots", {})
        repair_snapshots = packet_documents.get("repair", {}).get("snapshots", {})
        move_snapshots = packet_documents.get("move", {}).get("snapshots", {})
        uninstall_snapshots = packet_documents.get("uninstall", {}).get("snapshots", {})
        if install_snapshots != {"pre_target_digest": absent_snapshot, "post_target_digest": closure_snapshot}:
            problems.append("install packet snapshots do not derive from retained closure")
        if repair_snapshots.get("post_target_digest") != closure_snapshot or repair_snapshots.get("pre_target_digest") == closure_snapshot:
            problems.append("repair packet does not prove detected damage followed by exact closure")
        if move_snapshots != {"pre_target_digest": absent_snapshot, "post_target_digest": closure_snapshot}:
            problems.append("move packet snapshots do not derive from retained closure")
        if uninstall_snapshots != {"pre_target_digest": closure_snapshot, "post_target_digest": absent_snapshot}:
            problems.append("uninstall packet snapshots do not derive clean removal")
    if summary is not None:
        observed_summary_packets = summary.get("evidence_packets")
        expected_summary_packets = [
            {
                "packet_digest": packet_documents[operation].get("packet_digest"),
                "packet_id": packet_documents[operation].get("packet_id"),
            }
            for operation in operations if operation in packet_documents
        ]
        if observed_summary_packets != expected_summary_packets:
            problems.append("acceptance summary does not bind the independently verified packets")

    interruption_files, _, interruption_inventory_problems = _inventory(interruption_root)
    problems.extend(interruption_inventory_problems)
    interruption_summary_path = interruption_root / "interruption-summary.json"
    interruption = _load_canonical_json(interruption_summary_path, "interruption summary", problems)
    interruption_policy = policy.get("interruption_recovery", {})
    if interruption is not None and interruption != {
        "automation_created_verdict": False,
        "case_count": interruption_policy.get("case_count"),
        "completed": interruption_policy.get("completed"),
        "operator_verdict": "pending",
        "recovery_required": interruption_policy.get("recovery_required"),
        "rolled_back": interruption_policy.get("rolled_back"),
        "run_id": interruption_run_id,
        "schema": interruption_policy.get("schema"),
        "unchanged": interruption_policy.get("unchanged"),
    }:
        problems.append("fresh interruption summary differs from frozen 11-case matrix")
    interruption_journals = [path for path in interruption_files if path.name.endswith(".journal.json")]
    if len(interruption_journals) != interruption_policy.get("journal_count"):
        problems.append("fresh interruption corpus must retain exactly 14 transaction journals")
    for path in interruption_journals:
        _verify_journal(path, interruption_root, problems, require_completed=False)

    if problems:
        return None, problems
    evidence = {
        "acceptance_root": acceptance_root.as_posix(),
        "run_id": run_id,
        "interruption_run_id": interruption_run_id,
        "summary_sha256": sha256_file(summary_path),
        "archive": archive_observation,
        "retained_tree": {
            "file_count": len(files), "directory_count": len(directories),
            "total_bytes": observed_bytes, "reparse_point_count": 0,
        },
        "product_files": product_files,
        "evidence_packets": packet_observations,
        "audit": {"chain_id": audit_chain_id, "event_count": len(audit_events), "head_digest": previous},
        "final_state": {
            "installed_product": "present_exact_owned_closure",
            "moved_product": "absent_after_clean_uninstall",
            "committed_closure": "removed",
            "recovery_status": "not_required",
        },
        "interruption_recovery": {
            "summary_sha256": sha256_file(interruption_summary_path),
            "case_count": interruption.get("case_count"),
            "journal_count": len(interruption_journals),
        },
    }
    evidence_digest = sha256_bytes(canonical_bytes(evidence))
    result = {
        "schema": "factorio.m2_machine_acceptance_observation.v1",
        "work_unit": "M2-WU10-AUTOMATED-ACCEPTANCE-RESULT-01",
        "technical_acceptance": {
            "policy_id": policy["policy_id"], "result": "EvidencePass",
            "policy_revision": policy_revision, "runner_revision": runner_revision,
            "verifier_revision": verifier_revision, "verified_at": verified_at,
            "evidence_digest": evidence_digest,
        },
        "evidence": evidence,
        "human_review": {
            "requirement": "not_required_for_synthetic_non_executable_lane",
            "result": "not_required",
        },
        "authority": policy["authority_on_machine_pass"],
    }
    return result, []


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify frozen M2 synthetic acceptance evidence.")
    parser.add_argument("--policy-only", action="store_true", help="Validate the frozen policy without evaluating evidence.")
    parser.add_argument("--run-id")
    parser.add_argument("--interruption-run-id")
    parser.add_argument("--policy-revision")
    parser.add_argument("--runner-revision")
    parser.add_argument("--verifier-revision")
    parser.add_argument("--verified-at")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    policy = load_policy()
    if args.policy_only:
        problems = validate_policy(policy)
        if problems:
            for problem in problems:
                print(f"m2-wu10-machine-acceptance-check: {problem}", file=sys.stderr)
            return 1
        print("m2-wu10-machine-acceptance-check: ok (frozen policy; no result recorded)")
        return 0
    required = {
        "--run-id": args.run_id,
        "--interruption-run-id": args.interruption_run_id,
        "--policy-revision": args.policy_revision,
        "--runner-revision": args.runner_revision,
        "--verifier-revision": args.verifier_revision,
        "--verified-at": args.verified_at,
    }
    missing = [name for name, value in required.items() if not value]
    if missing:
        parser.error("live verification requires " + ", ".join(missing))
    result, problems = verify_evidence(
        policy, Path(policy["scope"]["acceptance_root"]), args.run_id,
        args.interruption_run_id, args.policy_revision, args.runner_revision,
        args.verifier_revision, args.verified_at,
    )
    if problems:
        for problem in problems:
            print(f"m2-wu10-machine-acceptance-check: {problem}", file=sys.stderr)
        return 1
    assert result is not None
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output is not None:
        if args.output.exists():
            print("m2-wu10-machine-acceptance-check: output already exists", file=sys.stderr)
            return 1
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8", newline="\n")
    else:
        print(rendered, end="")
    print("m2-wu10-machine-acceptance-check: EvidencePass", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
