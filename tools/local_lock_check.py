from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def validate() -> list[str]:
    problems: list[str] = []
    header = (ROOT / "runtime/base/fl_local_operation_lock.h").read_text(encoding="utf-8")
    source = (ROOT / "runtime/base/fl_local_operation_lock.cpp").read_text(encoding="utf-8")
    launch_header = (ROOT / "runtime/factorio/launch/flb_factorio_launch_plan.h").read_text(
        encoding="utf-8"
    )
    launch = (ROOT / "runtime/factorio/launch/flb_factorio_launch_plan.cpp").read_text(
        encoding="utf-8"
    )
    recovery = (ROOT / "runtime/transaction/fl_transaction.cpp").read_text(encoding="utf-8")
    native_test = (ROOT / "tests/native/facman_isolation_lock_smoke.cpp").read_text(
        encoding="utf-8"
    )
    for anchor in (
        "class StableLocalLock",
        "identity_matches_path",
        "remove_exact",
        "unsupported_filesystem",
    ):
        if anchor not in header:
            problems.append(f"stable lock interface anchor missing: {anchor}")
    for anchor in (
        "CreateFileW(",
        "FILE_SHARE_READ",
        "SetFileInformationByHandle(",
        "GetFileInformationByHandle(",
        "DRIVE_REMOTE",
        "::flock(",
        "O_NOFOLLOW",
        "::lstat(",
        "MNT_LOCAL",
        "unreviewed Linux filesystem type",
        "st_nlink != 1",
    ):
        if anchor not in source:
            problems.append(f"stable lock platform proof anchor missing: {anchor}")
    if "stable_handle" not in launch_header or "identity" not in launch_header:
        problems.append("run lock does not retain stable handle and identity")
    for consumer, text in (("run", launch), ("recovery", recovery)):
        if "StableLocalLock" not in text or "remove_exact(" not in text:
            problems.append(f"{consumer} lock does not consume the stable local lock")
    if "write_text_new_atomic(lock_path" in recovery or "fs::remove(lock.path" in launch:
        problems.append("legacy pathname-only lock lifecycle returned")
    for anchor in (
        "create_hard_link",
        "removed_while_held",
        "locks-renamed",
        "run_lock_unsafe",
    ):
        if anchor not in native_test:
            problems.append(f"hostile lock regression anchor missing: {anchor}")
    return problems


def main() -> int:
    problems = validate()
    if problems:
        for problem in problems:
            print(f"local-lock-check: {problem}", file=sys.stderr)
        return 1
    print("local-lock-check: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
