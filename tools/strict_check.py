from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import (
    aide_target_truth_check,
    aide_queue_state_check,
    alpha_vertical_slice_check,
    application_handler_check,
    apps_boundary_check,
    archive_core_check,
    critical_io_check,
    ci_proof_check,
    client_cli_boundary_check,
    cmake_architecture_check,
    command_contract_check,
    diagnostic_export_check,
    discovery_golden_check,
    frontend_contract_check,
    frontend_parity_check,
    frontend_transport_truth_check,
    generated_catalog_check,
    gui_surface_check,
    language_runtime_policy_check,
    local_lock_check,
    manual_json_check,
    modset_route_check,
    save_transfer_route_check,
    package_check,
    package_layout_check,
    package_manifest_check,
    package_skeleton_check,
    provenance_check,
    refusal_contract_check,
    refusal_golden_check,
    release_contract_check,
    release_readiness_check,
    schema_validate,
    security_policy_check,
    source_format_check,
    structure_policy_check,
    transaction_recovery_check,
    target_dependency_check,
    ui_accessibility_check,
    workspace_contract_check,
    workspace_store_check,
    version_truth_check,
)


def main() -> int:
    checks: list[tuple[str, Callable[[], int]]] = [
        ("aide-target-truth", aide_target_truth_check.main),
        ("aide-queue-state", aide_queue_state_check.main),
        ("apps-boundary", apps_boundary_check.main),
        ("manual-json", manual_json_check.main),
        ("critical-io", critical_io_check.main),
        ("generated-catalog", generated_catalog_check.main),
        ("version-truth", version_truth_check.main),
        ("target-dependency", target_dependency_check.main),
        ("client-cli-boundary", client_cli_boundary_check.main),
        ("cmake-architecture", cmake_architecture_check.main),
        ("archive-core", archive_core_check.main),
        ("ci-proof", ci_proof_check.main),
        ("structure", structure_policy_check.main),
        ("workspace-contract", workspace_contract_check.main),
        ("workspace-store", workspace_store_check.main),
        ("schema", schema_validate.main),
        ("security", security_policy_check.main),
        ("source-format", source_format_check.main),
        ("ui-accessibility", ui_accessibility_check.main),
        ("package", package_check.main),
        ("package-layout", package_layout_check.main),
        ("package-manifest", package_manifest_check.main),
        ("package-skeleton", package_skeleton_check.main),
        ("provenance", provenance_check.main),
        ("gui-surface", gui_surface_check.main),
        ("language-runtime-policy", language_runtime_policy_check.main),
        ("local-lock", local_lock_check.main),
        ("modset-route", modset_route_check.main),
        ("save-transfer-route", save_transfer_route_check.main),
        ("transaction-recovery", transaction_recovery_check.main),
        ("diagnostic-export", diagnostic_export_check.main),
        ("command-contract", command_contract_check.main),
        ("frontend-contract", frontend_contract_check.main),
        ("frontend-parity", frontend_parity_check.main),
        ("frontend-transport-truth", frontend_transport_truth_check.main),
        ("alpha-vertical-slice", alpha_vertical_slice_check.main),
        ("application-handler", application_handler_check.main),
        ("refusal-contract", refusal_contract_check.main),
        ("refusal-golden", refusal_golden_check.main),
        ("discovery-golden", discovery_golden_check.main),
        ("release-readiness", release_readiness_check.main),
        ("release-contract", release_contract_check.main),
    ]
    failed: list[str] = []
    for name, check in checks:
        if check() != 0:
            failed.append(name)
    if failed:
        print(f"strict-check: failed checks: {', '.join(failed)}", file=sys.stderr)
        return 1
    print("strict-check: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
