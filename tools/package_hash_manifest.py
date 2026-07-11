from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tomllib
from pathlib import Path, PurePosixPath
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import json_contract

COMPONENT_SCHEMA = ROOT / "contracts" / "schema" / "release" / "package_components.v1.schema.json"

EXCLUDED_HASH_OUTPUTS = {
    "manifest/hashes.sha256",
}


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    parser = argparse.ArgumentParser(description="Write built package component and hash manifests.")
    parser.add_argument("--root", required=True, help="package root to scan")
    parser.add_argument("--verify", action="store_true", help="verify the existing hash manifest instead of writing it")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    if not root.is_dir():
        print(f"package-hash-manifest: missing package root: {root}", file=sys.stderr)
        return 1
    if args.verify:
        problems = verify_manifest(root)
        if problems:
            for problem in problems:
                print(f"package-hash-manifest: {problem}", file=sys.stderr)
            return 1
        print("package-hash-manifest: verify ok")
        return 0
    records = existing_component_records(root)
    write_manifests(root, records)
    print(f"package-hash-manifest: write ok ({len(records)} files)")
    return 0


def component_records_from_files(root: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = path.relative_to(root).as_posix()
        if relative in EXCLUDED_HASH_OUTPUTS or relative.endswith(".sig"):
            continue
        records.append(
            {
                "name": component_name_for(relative),
                "source_target": "package_file",
                "destination": relative,
                "kind": "support_metadata",
                "runtime_role": "documentation_only",
            }
        )
    return records


def write_manifests(root: Path, records: list[dict[str, Any]]) -> None:
    manifest = root / "manifest"
    manifest.mkdir(parents=True, exist_ok=True)
    enriched = []
    for record in expanded_component_records(root, records):
        destination = str(record["destination"])
        path = root / destination
        enriched.append(
            {
                **record,
                "destination": destination,
                "sha256": sha256(path),
                "size": path.stat().st_size,
            }
        )
    components = {
        "schema": "facman.package_components.v1",
        "components": enriched,
    }
    (manifest / "components.v1.json").write_text(
        json.dumps(components, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    component_problems = validate_component_manifest(root, components)
    if component_problems:
        raise ValueError("invalid component manifest: " + "; ".join(component_problems))
    write_hash_manifest(root)


def write_hash_manifest(root: Path) -> None:
    manifest = root / "manifest"
    manifest.mkdir(parents=True, exist_ok=True)
    hash_records = component_records_from_files(root)
    hash_lines = [
        f"{sha256(root / record['destination'])}  {record['destination']}"
        for record in hash_records
    ]
    (manifest / "hashes.sha256").write_text("\n".join(hash_lines) + "\n", encoding="utf-8")


def existing_component_records(root: Path) -> list[dict[str, Any]]:
    path = root / "manifest" / "components.v1.json"
    if not path.is_file():
        return component_records_from_files(root)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot reuse existing component manifest: {exc}") from exc
    records = data.get("components") if isinstance(data, dict) else None
    if not isinstance(records, list):
        raise ValueError("cannot reuse existing component manifest: components array is missing")
    return [
        {key: value for key, value in record.items() if key not in {"sha256", "size"}}
        for record in records
        if isinstance(record, dict)
    ]


def expanded_component_records(root: Path, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    expanded: list[dict[str, Any]] = []
    for record in sorted(records, key=lambda item: str(item.get("destination", ""))):
        destination = str(record["destination"])
        path = root / destination
        if path.is_file():
            expanded.append(record)
            continue
        if path.is_dir():
            for child in sorted(item for item in path.rglob("*") if item.is_file()):
                relative = child.relative_to(root).as_posix()
                if relative in EXCLUDED_HASH_OUTPUTS or relative.endswith(".sig"):
                    continue
                expanded.append(
                    {
                        **record,
                        "name": f"{record.get('name', 'component')}_{component_name_for(relative)}",
                        "destination": relative,
                        "container_destination": destination,
                    }
                )
            continue
        raise ValueError(f"component destination does not exist: {destination}")
    return expanded


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_manifest(root: Path) -> list[str]:
    manifest = root / "manifest" / "hashes.sha256"
    if not manifest.is_file():
        return ["missing manifest/hashes.sha256"]
    problems: list[str] = []
    declared: dict[str, str] = {}
    for line_number, line in enumerate(manifest.read_text(encoding="utf-8").splitlines(), start=1):
        if len(line) < 67 or line[64:66] != "  ":
            problems.append(f"invalid hash line {line_number}")
            continue
        expected, relative = line[:64].lower(), line[66:]
        if len(expected) != 64 or any(ch not in "0123456789abcdef" for ch in expected):
            problems.append(f"invalid SHA-256 on line {line_number}")
            continue
        if not safe_manifest_path(relative):
            problems.append(f"unsafe manifest path on line {line_number}: {relative}")
            continue
        if relative in declared:
            problems.append(f"duplicate manifest path: {relative}")
            continue
        declared[relative] = expected

    resolved_root = root.resolve()
    for relative, expected in declared.items():
        candidate = root / PurePosixPath(relative)
        if candidate.is_symlink() or not candidate.is_file():
            problems.append(f"missing or linked package file: {relative}")
            continue
        resolved = candidate.resolve()
        if resolved_root not in resolved.parents:
            problems.append(f"package file escapes root: {relative}")
            continue
        actual = sha256(candidate)
        if actual != expected:
            problems.append(f"SHA-256 mismatch: {relative}")

    actual_files = {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file()
        and path.relative_to(root).as_posix() not in EXCLUDED_HASH_OUTPUTS
        and not path.name.endswith(".sig")
    }
    declared_files = set(declared)
    for relative in sorted(actual_files - declared_files):
        problems.append(f"unhashed package file: {relative}")
    for relative in sorted(declared_files - actual_files):
        problems.append(f"manifest references missing file: {relative}")
    problems.extend(verify_component_manifest(root, declared))
    return problems


def verify_component_manifest(root: Path, declared_hashes: dict[str, str]) -> list[str]:
    path = root / "manifest" / "components.v1.json"
    if not path.is_file():
        return ["missing manifest/components.v1.json"]
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"invalid manifest/components.v1.json: {exc}"]
    return validate_component_manifest(root, data, declared_hashes)


def validate_component_manifest(
    root: Path,
    data: Any,
    declared_hashes: dict[str, str] | None = None,
) -> list[str]:
    if not isinstance(data, dict):
        return ["component manifest must be an object"]
    schema = json_contract.load_schema(COMPONENT_SCHEMA)
    problems = json_contract.validate(data, schema)
    records = data.get("components")
    if not isinstance(records, list):
        return problems

    names: set[str] = set()
    destinations: set[str] = set()
    runtime_required = 0
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            continue
        prefix = f"component[{index}]"
        name = str(record.get("name", ""))
        destination = str(record.get("destination", ""))
        role = str(record.get("runtime_role", ""))
        if name in names:
            problems.append(f"{prefix}: duplicate component name {name}")
        names.add(name)
        if destination in destinations:
            problems.append(f"{prefix}: duplicate component destination {destination}")
        destinations.add(destination)
        if not safe_manifest_path(destination):
            problems.append(f"{prefix}: unsafe component destination {destination}")
            continue
        container = record.get("container_destination")
        if container is not None and not safe_manifest_path(str(container)):
            problems.append(f"{prefix}: unsafe container destination {container}")
        if role == "runtime_required":
            runtime_required += 1
        candidate = root / PurePosixPath(destination)
        if not candidate.is_file() or candidate.is_symlink():
            problems.append(f"{prefix}: component file is missing or linked: {destination}")
            continue
        expected_digest = str(record.get("sha256", ""))
        if sha256(candidate) != expected_digest:
            problems.append(f"{prefix}: component SHA-256 mismatch: {destination}")
        if candidate.stat().st_size != record.get("size"):
            problems.append(f"{prefix}: component size mismatch: {destination}")
        if declared_hashes is not None and declared_hashes.get(destination) != expected_digest:
            problems.append(f"{prefix}: component digest disagrees with hash manifest: {destination}")

    if (root / "manifest" / "package.v1.toml").is_file() and runtime_required == 0:
        problems.append("built package must declare at least one runtime_required component")
    problems.extend(validate_profile_component_roles(root, records))
    return problems


def validate_profile_component_roles(root: Path, records: list[Any]) -> list[str]:
    package_path = root / "manifest" / "package.v1.toml"
    if not package_path.is_file():
        return []
    try:
        with package_path.open("rb") as handle:
            package = tomllib.load(handle)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        return [f"cannot read package manifest for component policy: {exc}"]
    profile_id = str(package.get("profile_id", ""))
    if profile_id not in {"windows_portable_cli_x64", "linux_portable_cli_x64"}:
        return []
    by_destination = {
        str(record.get("destination")): record
        for record in records
        if isinstance(record, dict)
    }
    problems: list[str] = []
    cli_destination = "bin/facman.exe" if profile_id == "windows_portable_cli_x64" else "bin/facman"
    cli = by_destination.get(cli_destination)
    if not isinstance(cli, dict) or cli.get("runtime_role") != "runtime_required":
        problems.append(f"{profile_id} requires {cli_destination} as runtime_required")
    if any(record.get("kind") == "runtime_library" for record in by_destination.values()):
        problems.append(f"{profile_id} must not declare shared project runtime libraries")
    for prefix in ["contracts/schema/", "content/factorio/"]:
        matching = [
            record for destination, record in by_destination.items()
            if destination.startswith(prefix)
        ]
        if not matching or any(record.get("runtime_role") != "compatibility_reference" for record in matching):
            problems.append(f"{profile_id} requires {prefix} as compatibility_reference")
    return problems


def safe_manifest_path(value: str) -> bool:
    if not value or "\\" in value or ":" in value:
        return False
    path = PurePosixPath(value)
    return not path.is_absolute() and all(part not in {"", ".", ".."} for part in path.parts)


def component_name_for(relative: str) -> str:
    return relative.replace("/", "_").replace(".", "_").replace("-", "_")


if __name__ == "__main__":
    raise SystemExit(main())
