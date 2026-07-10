from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


EXCLUDED_HASH_OUTPUTS = {
    "manifest/hashes.sha256",
}


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    parser = argparse.ArgumentParser(description="Write built package component and hash manifests.")
    parser.add_argument("--root", required=True, help="package root to scan")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    if not root.is_dir():
        print(f"package-hash-manifest: missing package root: {root}", file=sys.stderr)
        return 1
    records = component_records_from_files(root)
    write_manifests(root, records)
    print(f"package-hash-manifest: ok ({len(records)} files)")
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
                "kind": "package_file",
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
    hash_records = component_records_from_files(root)
    hash_lines = [
        f"{sha256(root / record['destination'])}  {record['destination']}"
        for record in hash_records
    ]
    (manifest / "hashes.sha256").write_text("\n".join(hash_lines) + "\n", encoding="utf-8")


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


def component_name_for(relative: str) -> str:
    return relative.replace("/", "_").replace(".", "_").replace("-", "_")


if __name__ == "__main__":
    raise SystemExit(main())
