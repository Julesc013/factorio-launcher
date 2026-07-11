from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    problems: list[str] = []
    diagnostics_path = ROOT / "runtime/factorio/diagnostics/flb_factorio_diagnostics.cpp"
    cli_path = ROOT / "apps/cli/command_dispatch.cpp"
    application_path = ROOT / "runtime/factorio/application/flb_factorio_application.cpp"
    binding_path = ROOT / "runtime/factorio/binding/flb_api.c"
    diagnostics = diagnostics_path.read_text(encoding="utf-8")
    cli = cli_path.read_text(encoding="utf-8")
    application = application_path.read_text(encoding="utf-8")
    binding = binding_path.read_text(encoding="utf-8")
    binding += (ROOT / "runtime/core/generated/command_catalog.h").read_text(encoding="utf-8")

    required_diagnostics = [
        "stable_read_relative(",
        "CreateFileW(",
        "FILE_FLAG_OPEN_REPARSE_POINT",
        "nNumberOfLinks != 1",
        "dwVolumeSerialNumber",
        "nFileIndexHigh",
        "openat(",
        "O_NOFOLLOW",
        "fstat(",
        "st_dev",
        "st_ino",
        "st_nlink != 1",
        "write_to_new_owned_staging(",
        "commit_owned_staged_file_no_clobber(",
        "tx::begin(",
        "archive::inspect_archive(",
        "manifest_content != manifest",
        "facman.diagnostic_export.v1",
        "sha256-pseudonymous",
        "unknown_format",
    ]
    for anchor in required_diagnostics:
        if anchor not in diagnostics:
            problems.append(f"diagnostic implementation missing safety anchor: {anchor}")

    for anchor in [
        "write_diagnostic_stored_zip_quarantined",
        "write_diagnostic_bundle(",
        "recursive_directory_iterator",
    ]:
        if anchor in cli:
            problems.append(f"CLI retains migrated diagnostic backend behavior: {anchor}")
    if '"diagnostics.export"' not in cli or "route_factorio_command(" not in cli:
        problems.append("CLI diagnostic export does not normalize into the authoritative route")
    if "diagnostic_export_not_safe" in cli:
        problems.append("CLI still quarantines diagnostic export after the complete safety route")
    if "diagnostic_operations::export_bundle(" not in application:
        problems.append("typed application operation does not own diagnostic export")
    if '"diagnostics.export"' not in binding or "diagnostic_bundle_export.v1.schema.json" not in binding:
        problems.append("registered diagnostic descriptor is missing or has stale schema metadata")

    for relative in [
        "contracts/command/factorio/diagnostics.export.v1.toml",
        "contracts/schema/factorio/diagnostic_bundle_export.v1.schema.json",
        "contracts/schema/factorio/diagnostic_file_read_report.v1.schema.json",
        "contracts/schema/factorio/diagnostic_omission_report.v1.schema.json",
        "tests/test_diagnostic_export.py",
    ]:
        if not (ROOT / relative).is_file():
            problems.append(f"missing diagnostic proof file: {relative}")

    if problems:
        for problem in problems:
            print(f"diagnostic-export-check: {problem}", file=sys.stderr)
        return 1
    print("diagnostic-export-check: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
