# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RECORD = ROOT / "tests/fixtures/m2_wu10/operator-acceptance.pending.v1.json"
EXPECTED_SETUP_REVISION = "3f8489275077347c2918f3bb03614ec6431362ff"
EXPECTED_FACMAN_BASELINE = "384c2569c84696c5fce02802684e30fad44f9ee0"
EXPECTED_OPERATIONS = {"install_local", "repair", "move", "uninstall"}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def is_reparse_point(path: Path) -> bool:
    attributes = getattr(path.stat(follow_symlinks=False), "st_file_attributes", 0)
    return path.is_symlink() or bool(attributes & getattr(os, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))


def validate_record(document: dict[str, object]) -> list[str]:
    problems: list[str] = []
    if document.get("schema") != "factorio.m2_operator_acceptance_record.v1":
        problems.append("unexpected operator acceptance schema")
    if document.get("status") != "machine_evidence_ready_pending_operator_verdict":
        problems.append("machine record must remain pending before the operator decision")
    run = document.get("acceptance_run", {})
    if not isinstance(run, dict):
        return problems + ["acceptance_run must be an object"]
    if run.get("acceptance_root") != r"D:\FacMan-Live-Acceptance\M2":
        problems.append("acceptance record must bind only the authorized root")
    revisions = run.get("source_revisions", {})
    if not isinstance(revisions, dict) or revisions != {
        "universal_setup": EXPECTED_SETUP_REVISION,
        "factorio_launcher": EXPECTED_FACMAN_BASELINE,
    }:
        problems.append("acceptance run source revisions changed")
    archive = run.get("synthetic_archive", {})
    if not isinstance(archive, dict) or archive.get("contains_executable_code") is not False:
        problems.append("acceptance archive must remain explicitly non-executable")
    retained = run.get("retained_tree", {})
    if not isinstance(retained, dict) or retained.get("reparse_point_count") != 0:
        problems.append("acceptance tree must contain no reparse points")
    packets = run.get("evidence_packets", [])
    if not isinstance(packets, list) or {packet.get("operation") for packet in packets if isinstance(packet, dict)} != EXPECTED_OPERATIONS:
        problems.append("acceptance record must bind exactly install, repair, move, and uninstall packets")
    if len(packets) != 4:
        problems.append("acceptance record must bind exactly four evidence packets")
    final_state = run.get("final_state", {})
    if not isinstance(final_state, dict) or {
        "committed_closure": final_state.get("committed_closure"),
        "recovery_status": final_state.get("recovery_status"),
        "old_root": final_state.get("old_root"),
        "current_root": final_state.get("current_root"),
    } != {
        "committed_closure": "removed",
        "recovery_status": "not_required",
        "old_root": "retained_for_review",
        "current_root": "removed_by_clean_uninstall",
    }:
        problems.append("acceptance final state changed")
    recovery = document.get("interruption_recovery", {})
    if not isinstance(recovery, dict) or [
        recovery.get("case_count"), recovery.get("unchanged"), recovery.get("rolled_back"),
        recovery.get("completed"), recovery.get("recovery_required"), recovery.get("operator_verdict"),
    ] != [11, 1, 4, 3, 3, "pending"]:
        problems.append("accepted interruption and recovery proof changed")
    review = document.get("operator_review", {})
    if not isinstance(review, dict) or review != {
        "allowed_verdicts": ["Pass", "Fail", "Inconclusive"],
        "operator_verdict": "pending",
        "automation_can_record_operator_verdict": False,
        "recorded_at": None,
        "recorded_by": None,
        "statement_digest": None,
    }:
        problems.append("automation must preserve a separate pending human verdict")
    authority = document.get("authority", {})
    if not isinstance(authority, dict) or authority != {
        "ordinary_live_apply": "unavailable_pending_operator_acceptance",
        "factorio_archive_acceptance": "unavailable",
        "existing_factorio_mutation": False,
        "steam_mutation": False,
        "network": False,
        "registry": False,
        "elevation": False,
        "run_execute": False,
        "h1_inference": "none",
        "publication": False,
    }:
        problems.append("operator acceptance authority boundary changed")
    lock = tomllib.loads((ROOT / "release/index/workspace_lock.v1.toml").read_text(encoding="utf-8"))
    pins = {item["id"]: item["pin"] for item in lock.get("component", [])}
    if pins.get("universal_setup") != EXPECTED_SETUP_REVISION:
        problems.append("workspace lock no longer matches the reviewed Setup provider")
    return problems


def validate_live_root(document: dict[str, object]) -> list[str]:
    problems: list[str] = []
    run = document["acceptance_run"]
    assert isinstance(run, dict)
    run_root = Path(str(run["acceptance_root"])) / str(run["run_id"])
    if not run_root.is_dir():
        return [f"retained acceptance run is missing: {run_root}"]
    summary_path = run_root / str(run["summary_relative_path"])
    archive = run["synthetic_archive"]
    assert isinstance(archive, dict)
    archive_path = run_root / str(archive["relative_path"])
    if not summary_path.is_file() or sha256(summary_path) != run["summary_sha256"]:
        problems.append("retained acceptance summary digest differs from the bound record")
    if not archive_path.is_file() or sha256(archive_path) != archive["sha256"]:
        problems.append("retained synthetic archive digest differs from the bound record")
    if summary_path.is_file():
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        if summary.get("status") != "automated_findings_complete_pending_operator_verdict":
            problems.append("retained summary no longer preserves the pending verdict")
        if summary.get("authority") != {
            "acceptance_root": "D:/FacMan-Live-Acceptance/M2",
            "operator_verdict": "pending",
            "ordinary_live_apply_promoted": False,
            "run_execute_authorized": False,
        }:
            problems.append("retained summary authority boundary changed")
    packets = run["evidence_packets"]
    assert isinstance(packets, list)
    for packet in packets:
        assert isinstance(packet, dict)
        path = run_root / str(packet["relative_path"])
        if not path.is_file() or sha256(path) != packet["file_sha256"]:
            problems.append(f"retained {packet['operation']} evidence packet digest changed")
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("packet_digest") != packet["packet_digest"] or payload.get("operator_verdict", {}).get("status") != "pending":
            problems.append(f"retained {packet['operation']} packet identity or verdict changed")
    entries = list(run_root.rglob("*"))
    files = [path for path in entries if path.is_file()]
    directories = [path for path in entries if path.is_dir()]
    retained = run["retained_tree"]
    assert isinstance(retained, dict)
    if [len(files), len(directories), sum(path.stat().st_size for path in files)] != [
        retained["file_count"], retained["directory_count"], retained["total_bytes"],
    ]:
        problems.append("retained acceptance tree count or byte identity changed")
    if any(is_reparse_point(path) for path in [run_root, *entries]):
        problems.append("retained acceptance tree contains a link or reparse point")
    if not (run_root / "installed-product").is_dir() or (run_root / "moved-product").exists():
        problems.append("retained move/uninstall roots no longer match the reviewed final state")
    if (run_root / "installed-product/operator-note.txt").exists() or (run_root / "moved-product/operator-note.txt").exists():
        problems.append("temporary foreign-content review file was not removed")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate the pending M2-WU10 operator acceptance record.")
    parser.add_argument("--require-live-root", action="store_true", help="Also verify the retained authorized Windows run.")
    args = parser.parse_args(argv)
    document = json.loads(RECORD.read_text(encoding="utf-8"))
    problems = validate_record(document)
    if args.require_live_root:
        problems.extend(validate_live_root(document))
    if problems:
        for problem in problems:
            print(f"m2-wu10-operator-acceptance-check: {problem}", file=sys.stderr)
        return 1
    scope = "record and retained live root" if args.require_live_root else "record"
    print(f"m2-wu10-operator-acceptance-check: ok ({scope}; human verdict pending)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
