# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REQUIRED_FILES = {
    "docs/architecture/archive-stable-lifetime.v1.md",
    "runtime/archive/fl_archive.h",
    "runtime/archive/fl_archive_platform.cpp",
    "runtime/archive/fl_archive_policy.cpp",
    "runtime/archive/fl_archive_reader.cpp",
    "runtime/archive/fl_archive_writer.cpp",
    "tests/native/fl_archive_core_smoke.cpp",
    "tests/native/fl_archive_metadata_fuzz.cpp",
    "tests/native/fl_archive_plan_fuzz.cpp",
    "tests/test_archive_core.py",
}

REQUIRED_READER_ANCHORS = {
    "archive_multidisk_unsupported",
    "archive_entry_encrypted",
    "archive_extra_malformed",
    "archive_entry_ranges_overlap",
    "archive_descriptor_mismatch",
    "archive_local_central_mismatch",
    "archive_crc_or_size_verification_failed",
}

REQUIRED_POLICY_ANCHORS = {
    "archive_path_absolute",
    "archive_path_backslash",
    "archive_path_ads_or_drive",
    "archive_path_windows_reserved",
    "archive_entry_symlink",
    "archive_entry_unsupported_file_type",
    "archive_path_case_collision",
    "archive_path_unicode_normalization_collision",
    "archive_path_file_directory_collision",
    "archive_compression_ratio_limit",
}


def validate() -> list[str]:
    problems: list[str] = []
    for relative in sorted(REQUIRED_FILES):
        if not (ROOT / relative).is_file():
            problems.append(f"missing archive-core file: {relative}")

    reader = (ROOT / "runtime/archive/fl_archive_reader.cpp").read_text(encoding="utf-8")
    policy = (ROOT / "runtime/archive/fl_archive_policy.cpp").read_text(encoding="utf-8")
    writer = (ROOT / "runtime/archive/fl_archive_writer.cpp").read_text(encoding="utf-8")
    cmake = (ROOT / "runtime/archive/CMakeLists.txt").read_text(encoding="utf-8")
    for anchor in sorted(REQUIRED_READER_ANCHORS):
        if anchor not in reader:
            problems.append(f"archive reader is missing refusal anchor: {anchor}")
    for anchor in sorted(REQUIRED_POLICY_ANCHORS):
        if anchor not in policy:
            problems.append(f"archive policy is missing refusal anchor: {anchor}")
    for anchor in (
        "ReaderState",
        "verify_contents_impl",
        "open_miniz_reader(file",
    ):
        if anchor not in reader:
            problems.append(f"archive reader is missing stable-lifetime anchor: {anchor}")
    for anchor in (
        "create_owned_staging_root",
        "inspect_archive(output_path",
        "verify_all(verified",
        "mz_zip_writer_add_read_buf_callback",
        "sources.at(entry.archive_path)",
    ):
        if anchor not in writer:
            problems.append(f"archive writer is missing staging/streaming anchor: {anchor}")
    if "add_library(facman_archive_static STATIC" not in cmake:
        problems.append("CMake does not define the production archive static library")

    header = (ROOT / "runtime/archive/fl_archive.h").read_text(encoding="utf-8")
    for consumer_policy in (
        "ModArchivePolicy",
        "SaveArchivePolicy",
        "InstanceTransferPolicy",
        "DiagnosticBundlePolicy",
        "PackageArchivePolicy",
    ):
        if consumer_policy not in header:
            problems.append(f"archive core is missing consumer policy: {consumer_policy}")

    legacy_locations: list[str] = []
    for path in ROOT.rglob("*"):
        if not path.is_file() or path.suffix not in {".c", ".cpp", ".h", ".hpp"}:
            continue
        relative = path.relative_to(ROOT).as_posix()
        if relative.startswith(("build/", "external/", ".aide/")):
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if (
            "read_stored_zip(" in text
            or "write_stored_zip(" in text
            or "write_diagnostic_stored_zip_quarantined(" in text
        ):
            legacy_locations.append(relative)
    expected_legacy_locations: list[str] = []
    if sorted(set(legacy_locations)) != expected_legacy_locations:
        problems.append(
            "legacy ZIP helpers are forbidden after diagnostic migration: "
            + ", ".join(sorted(set(legacy_locations)))
        )
    return problems


def main() -> int:
    problems = validate()
    if problems:
        for problem in problems:
            print(f"archive-core-check: {problem}", file=sys.stderr)
        return 1
    print("archive-core-check: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
