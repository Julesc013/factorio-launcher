# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.release_compiler.canonical import canonical_bytes
from tools.release_compiler.compiler import INPUT_FILES, OUTPUT_FILES, load_inputs, resolve
from tools.release_compiler.outputs import validate_resolution
from tools import provider_pin_reconciliation


INPUT_ROOT = ROOT / "release" / "index"
TARGETS = (
    "linux_portable_cli_x64",
    "macos_portable_cli_x64",
    "windows_portable_cli_x64",
)
TECHNICAL_PREVIEW_TARGETS = ("windows_winforms_technical_preview_x64",)
ALL_TARGETS = (*TARGETS, *TECHNICAL_PREVIEW_TARGETS)
ARCHITECTURE_EQUIVALENTS = {"x64": "x86_64", "x86_64": "x86_64"}
FORMAT_EQUIVALENTS = {"zip": "portable_zip", "tar_gz": "tarball"}
INDEXED_INPUTS = {
    "release_model_version": "release/index/version.v2.toml",
    "release_model_product": "release/index/product.v2.toml",
    "release_model_components": "release/index/components.v2.toml",
    "release_model_targets": "release/index/targets.v2.toml",
    "release_model_artifacts": "release/index/artifacts.v2.toml",
    "release_model_providers": "release/index/providers.lock.v2.toml",
    "release_model_support": "release/index/support.v2.toml",
    "release_model_factorio_compatibility": "release/index/factorio_compatibility.v1.toml",
    "release_model_channels": "release/index/channels.v1.toml",
    "release_model_trust": "release/index/trust.v1.toml",
    "release_model_toolchains": "release/toolchain.lock",
}
PROVIDER_STATES = {
    "universal_launcher": (
        "canonical_main_experimental_session_subset_consumer_qualified",
        "accepted_exact_main_session_provider",
    ),
    "universal_setup": (
        "canonical_main_sdk_qualified",
        "accepted_non_authorizing_input",
    ),
}


def _toml(path: Path) -> dict[str, object]:
    with path.open("rb") as handle:
        return tomllib.load(handle)


def detect() -> list[str]:
    problems: list[str] = []
    for filename in (*INPUT_FILES, "../toolchain.lock"):
        if not (INPUT_ROOT / filename).is_file():
            problems.append(f"missing release compiler input: {filename}")
    release_index = _toml(INPUT_ROOT / "release_index.v1.toml")
    for key, expected in INDEXED_INPUTS.items():
        if release_index.get(key) != expected:
            problems.append(f"release index does not bind {key} to {expected}")
    try:
        inputs = load_inputs(INPUT_ROOT, ROOT)
    except (OSError, ValueError, tomllib.TOMLDecodeError) as exc:
        return [str(exc)]
    model_targets = {
        str(item["id"]): item
        for item in inputs.model["targets"].get("target", [])
        if isinstance(item, dict)
    }
    if set(model_targets) != set(ALL_TARGETS):
        problems.append(f"resolved target set differs from admitted compiler targets: {sorted(model_targets)}")

    for target_id in ALL_TARGETS:
        try:
            first = resolve(inputs, target_id)
            second = resolve(inputs, target_id)
            validate_resolution(first, ROOT)
        except (OSError, ValueError) as exc:
            problems.append(f"{target_id}: {exc}")
            continue
        if canonical_bytes(first) != canonical_bytes(second):
            problems.append(f"{target_id}: repeated resolution is not byte deterministic")
        if set(first) != set(OUTPUT_FILES):
            problems.append(
                f"{target_id}: resolution does not emit ten canonical records plus root and runtime projection"
            )
        if first["qualification_plan"].get("qualified") is not False:
            problems.append(f"{target_id}: package-preview target must remain unqualified")
        if any(claim.get("established") for claim in first["claims"].get("claims", [])):
            problems.append(f"{target_id}: release claims cannot be established without evidence")
        for artifact in first["authority"].get("artifacts", []):
            for capability in artifact.get("capabilities", []):
                if capability.get("currently_authorized") is not False:
                    problems.append(
                        f"{target_id}: {capability.get('id')} cannot be currently authorized"
                    )
        if target_id in TARGETS:
            problems.extend(_profile_drift(target_id, model_targets[target_id], first))

    for provider in inputs.model["providers"].get("provider", []):
        provider_id = provider.get("id", "<provider>")
        expected_maturity, expected_adoption = PROVIDER_STATES.get(
            str(provider_id), (None, None)
        )
        if provider.get("maturity") != expected_maturity:
            problems.append(f"{provider_id}: provider maturity differs from accepted evidence")
        if provider.get("consumption_mode") != "source":
            problems.append(f"{provider_id}: source closure must remain the default consumption mode")
        if provider.get("package_identity_kind") != "canonical_sdk_package_set":
            problems.append(f"{provider_id}: provider package family is not the accepted SDK set")
        if provider.get("sdk_adoption") != expected_adoption:
            problems.append(f"{provider_id}: provider SDK adoption state is not exact")
    problems.extend(provider_pin_reconciliation.validate(ROOT))
    return problems


def _profile_drift(
    target_id: str,
    target: dict[str, object],
    outputs: dict[str, dict[str, object]],
) -> list[str]:
    profile_path = ROOT / "release" / "profiles" / target_id / "profile.toml"
    if not profile_path.is_file():
        return [f"{target_id}: legacy package profile projection is missing"]
    profile = _toml(profile_path)
    problems = []
    comparisons = {
        "target_os": (profile.get("target_os"), target.get("os")),
        "minimum_os": (profile.get("minimum_os"), target.get("minimum_host")),
    }
    profile_arch = ARCHITECTURE_EQUIVALENTS.get(str(profile.get("target_arch")))
    comparisons["target_arch"] = (profile_arch, target.get("architecture"))
    for field, (legacy, canonical) in comparisons.items():
        if legacy != canonical:
            problems.append(f"{target_id}: legacy {field}={legacy!r} differs from v2 {canonical!r}")
    artifacts = outputs["package_plan"].get("artifacts", [])
    if len(artifacts) != 1:
        problems.append(f"{target_id}: first public target must resolve exactly one artifact")
    else:
        package_type = FORMAT_EQUIVALENTS.get(str(artifacts[0].get("format")))
        if package_type not in profile.get("package_types", []):
            problems.append(
                f"{target_id}: legacy profile does not project resolved format {package_type!r}"
            )
    return problems


def main() -> int:
    problems = detect()
    if problems:
        for problem in problems:
            print(f"release-resolution-check: {problem}", file=sys.stderr)
        return 1
    print(
        "release-resolution-check: ok "
        f"({len(ALL_TARGETS)} targets, {len(OUTPUT_FILES)} records per target)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
