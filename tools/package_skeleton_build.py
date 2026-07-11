from __future__ import annotations

import argparse
import json
import sys
import tomllib
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import owned_output, package_layout_check

DEFAULT_OUT = ROOT / "build" / "package-skeletons"
RELEASE_INDEX = ROOT / "release" / "index" / "release_index.v1.toml"


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = []
    parser = argparse.ArgumentParser(description="Materialize FacMan package layout skeletons.")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="output root for generated skeleton layouts")
    parser.add_argument("--no-clean", action="store_true", help="do not delete an existing output root first")
    args = parser.parse_args(argv)

    out_root = Path(args.out).resolve()
    try:
        built = materialize_all(out_root, clean=not args.no_clean)
    except (OSError, ValueError, tomllib.TOMLDecodeError) as exc:
        print(f"package-skeleton-build: {exc}", file=sys.stderr)
        return 1
    print(f"package-skeleton-build: ok ({len(built)} skeletons) {out_root}")
    return 0


def materialize_all(out_root: Path, clean: bool = True) -> list[Path]:
    assert_safe_output_root(out_root)
    if clean:
        owned_output.reset_owned_output_root(out_root, "package-skeletons")
    else:
        owned_output.ensure_owned_output_root(out_root, "package-skeletons")
    profiles = load_profiles()
    built: list[Path] = []
    for profile_path, profile in profiles:
        built.append(materialize_profile(out_root, profile_path, profile))
    return built


def load_profiles() -> list[tuple[Path, dict[str, Any]]]:
    release_index = load_toml(RELEASE_INDEX)
    profile_paths = release_index.get("profiles", [])
    if not isinstance(profile_paths, list) or not profile_paths:
        raise ValueError(f"{RELEASE_INDEX}: profiles must be a non-empty array")
    profiles: list[tuple[Path, dict[str, Any]]] = []
    for relative in profile_paths:
        path = ROOT / str(relative)
        profiles.append((path, load_toml(path)))
    return profiles


def materialize_profile(out_root: Path, profile_path: Path, profile: dict[str, Any]) -> Path:
    profile_id = str(profile.get("id", ""))
    if not profile_id:
        raise ValueError(f"{profile_path}: missing id")
    skeleton_root = out_root / profile_id
    skeleton_root.mkdir(parents=True, exist_ok=True)

    bundle_path = ROOT / str(profile.get("package_manifest", ""))
    bundle = package_layout_check.expand_bundle_manifest(bundle_path, load_toml(bundle_path), [])
    support = support_paths(profile)

    for relative in support.values():
        ensure_directory(skeleton_root / relative)
    ensure_platform_scaffold(skeleton_root, profile)

    components = bundle.get("components", [])
    if not isinstance(components, list):
        raise ValueError(f"{bundle_path}: components must be an array")
    component_records: list[dict[str, str]] = []
    for component in components:
        record = materialize_component(skeleton_root, component)
        component_records.append(record)

    write_support_placeholders(skeleton_root, profile, support)
    write_manifest_files(
        skeleton_root=skeleton_root,
        manifest_dir=skeleton_root / support["manifest"],
        profile_path=profile_path,
        profile=profile,
        bundle_path=bundle_path,
        bundle=bundle,
        support=support,
        component_records=component_records,
    )
    return skeleton_root


def materialize_component(skeleton_root: Path, component: dict[str, Any]) -> dict[str, str]:
    name = str(component.get("name", ""))
    source_target = str(component.get("source_target", ""))
    destination = package_layout_check.normalize_layout_path(str(component.get("destination", "")))
    if not name or not destination:
        raise ValueError(f"component must include name and destination: {component}")

    destination_path = skeleton_root / destination
    is_tree_component = destination.endswith("/") or source_target in {"contracts/schema", "content/factorio"}
    if is_tree_component:
        ensure_directory(destination_path)
        placeholder = destination_path / ".skeleton-placeholder"
        placeholder.write_text(f"FacMan package skeleton directory for {name}.\n", encoding="utf-8")
        placeholder_relative = placeholder.relative_to(skeleton_root).as_posix()
    else:
        ensure_directory(destination_path.parent)
        placeholder = destination_path.with_name(f"{destination_path.name}.placeholder")
        placeholder.write_text(
            "\n".join(
                [
                    "FacMan package skeleton placeholder.",
                    "real_artifact = false",
                    f"component = {name}",
                    f"source_target = {source_target}",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        placeholder_relative = placeholder.relative_to(skeleton_root).as_posix()

    return {
        "name": name,
        "source_target": source_target,
        "destination": destination,
        "placeholder": placeholder_relative,
    }


def support_paths(profile: dict[str, Any]) -> dict[str, str]:
    target_os = str(profile.get("target_os", ""))
    required_components = table(profile.get("required_components"))
    contracts = str(required_components.get("contracts", profile.get("contracts_path", "contracts/schema")))
    content = str(required_components.get("content", profile.get("content_path", "content/factorio")))
    if target_os == "macos" and "gui" in table(profile.get("frontends")):
        base = "FacMan.app/Contents/Resources"
        return {
            "contracts": contracts,
            "content": content,
            "docs": f"{base}/docs",
            "licenses": f"{base}/licenses",
            "release": f"{base}/release",
            "manifest": f"{base}/manifest",
        }
    if target_os == "linux":
        base = "usr/share/facman"
        return {
            "contracts": contracts,
            "content": content,
            "docs": f"{base}/docs",
            "licenses": f"{base}/licenses",
            "release": f"{base}/release",
            "manifest": f"{base}/manifest",
        }
    return {
        "contracts": contracts,
        "content": content,
        "docs": "docs",
        "licenses": "licenses",
        "release": "release",
        "manifest": "manifest",
    }


def ensure_platform_scaffold(skeleton_root: Path, profile: dict[str, Any]) -> None:
    target_os = str(profile.get("target_os", ""))
    if target_os == "windows":
        ensure_directory(skeleton_root / "bin")
    elif target_os == "macos" and "gui" in table(profile.get("frontends")):
        ensure_directory(skeleton_root / "FacMan.app" / "Contents" / "MacOS")
        ensure_directory(skeleton_root / "FacMan.app" / "Contents" / "Frameworks")
    elif target_os == "macos":
        ensure_directory(skeleton_root / "bin")
    elif target_os == "linux":
        ensure_directory(skeleton_root / "usr" / "bin")
        ensure_directory(skeleton_root / "usr" / "lib")
        ensure_directory(skeleton_root / "usr" / "share" / "facman")
    elif target_os == "portable":
        ensure_directory(skeleton_root / "bin")
        ensure_directory(skeleton_root / "lib")


def write_support_placeholders(skeleton_root: Path, profile: dict[str, Any], support: dict[str, str]) -> None:
    for label, relative in support.items():
        directory = skeleton_root / relative
        ensure_directory(directory)
        marker = directory / ".skeleton-placeholder"
        if not marker.exists():
            marker.write_text(f"FacMan {label} skeleton directory.\n", encoding="utf-8")
    licenses_dir = skeleton_root / support["licenses"]
    for license_name in string_list(profile.get("licenses")):
        license_leaf = Path(license_name).name
        (licenses_dir / f"{license_leaf}.placeholder").write_text(
            "FacMan package skeleton license placeholder.\n",
            encoding="utf-8",
        )


def write_manifest_files(
    skeleton_root: Path,
    manifest_dir: Path,
    profile_path: Path,
    profile: dict[str, Any],
    bundle_path: Path,
    bundle: dict[str, Any],
    support: dict[str, str],
    component_records: list[dict[str, str]],
) -> None:
    ensure_directory(manifest_dir)
    skeleton_manifest = {
        "schema": "facman.package_skeleton.v1",
        "profile_id": profile["id"],
        "real_artifact": False,
        "purpose": "layout validation only",
        "release_profile": profile_path.relative_to(ROOT).as_posix(),
        "package_manifest": bundle_path.relative_to(ROOT).as_posix(),
        "package_type": bundle.get("package_type"),
        "target_os": profile.get("target_os"),
        "target_arch": profile.get("target_arch"),
        "install_modes": profile.get("install_modes", []),
        "entrypoints": table(profile.get("entrypoints")),
        "support_paths": support,
        "capabilities": table(profile.get("capabilities")),
        "component_destinations": [record["destination"] for record in component_records],
    }
    (manifest_dir / "skeleton.v1.json").write_text(
        json.dumps(skeleton_manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (manifest_dir / "package.v1.toml").write_text(
        "\n".join(
            [
                'schema = "facman.package_skeleton_manifest.v1"',
                f'profile_id = "{profile["id"]}"',
                f'package_manifest = "{bundle_path.relative_to(ROOT).as_posix()}"',
                f'frontend_manifest = "{profile["frontend_manifest"]}"',
                f'support_matrix = "{profile["support_matrix"]}"',
                "real_artifact = false",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (manifest_dir / "components.v1.toml").write_text(render_components_toml(component_records), encoding="utf-8")


def render_components_toml(component_records: list[dict[str, str]]) -> str:
    lines = ['schema = "facman.package_skeleton_components.v1"', ""]
    for record in component_records:
        lines.append("[[component]]")
        for key in ["name", "source_target", "destination", "placeholder"]:
            lines.append(f'{key} = "{escape_toml(record[key])}"')
        lines.append("")
    return "\n".join(lines)


def assert_safe_output_root(out_root: Path) -> None:
    resolved = out_root.resolve()
    repo_root = ROOT.resolve()
    if resolved == repo_root:
        raise ValueError("refusing to delete repository root")
    if repo_root in resolved.parents and "build" not in resolved.parts:
        raise ValueError(f"refusing to clean non-build repository path: {resolved}")


def ensure_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def load_toml(path: Path) -> dict[str, Any]:
    with path.open("rb") as handle:
        return tomllib.load(handle)


def table(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def escape_toml(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
