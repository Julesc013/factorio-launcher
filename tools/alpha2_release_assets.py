#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

"""Assemble the exact private-draft FacMan alpha.2 release asset inventory."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import shutil
import subprocess
import tomllib
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "release/index/alpha2_release_source.v1.toml"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def copy_exact(source: Path, destination: Path, expected: str) -> None:
    if not source.is_file() or sha256(source) != expected:
        raise ValueError(f"qualified source asset is absent or substituted: {source}")
    shutil.copy2(source, destination)


def package_map(qualification: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result = {
        str(item["id"]): item
        for item in qualification.get("packages", [])
        if isinstance(item, dict)
    }
    required = {
        "windows_cli_x64_portable",
        "windows_tui_x64_portable",
        "windows_winforms_x64_portable",
    }
    if set(result) != required:
        raise ValueError("qualification must contain the exact three portable packages")
    return result


def setup_licences(package_root: Path, output: Path) -> None:
    entries = [
        {
            "path": path.relative_to(package_root).as_posix(),
            "bytes": path.stat().st_size,
            "sha256": sha256(path),
        }
        for path in sorted((package_root / "licenses").rglob("*"))
        if path.is_file()
    ]
    if not entries:
        raise ValueError("WinForms package has no licence closure for self-setup")
    write_json(
        output,
        {
            "schema": "facman.alpha_package_licence_inventory.v1",
            "profile": "windows_x64_per_user_self_setup",
            "source_closure": "windows_legacy_winforms_x64_plus_facman_setup",
            "entries": entries,
            "authority": {"signing": False, "public_publication": False, "support": False},
        },
    )


def setup_sbom(
    output: Path,
    *,
    version: str,
    setup_exe: Path,
    payload: Path,
    source_revision: str,
    provider_revision: str,
) -> None:
    namespace_seed = hashlib.sha256(
        f"{source_revision}:{sha256(setup_exe)}:{sha256(payload)}".encode("ascii")
    ).hexdigest()
    write_json(
        output,
        {
            "spdxVersion": "SPDX-2.3",
            "dataLicense": "CC0-1.0",
            "SPDXID": "SPDXRef-DOCUMENT",
            "name": f"FacMan {version} Windows x64 per-user self-setup",
            "documentNamespace": f"https://github.com/Julesc013/factorio-launcher/sbom/{namespace_seed}",
            "creationInfo": {
                "creators": ["Tool: tools/alpha2_release_assets.py"],
                "created": "2026-08-31T00:00:00Z",
            },
            "packages": [
                {
                    "name": "FacMan self-setup executable",
                    "SPDXID": "SPDXRef-Package-FacManSetup",
                    "versionInfo": version,
                    "downloadLocation": "NOASSERTION",
                    "filesAnalyzed": False,
                    "licenseConcluded": "MIT",
                    "licenseDeclared": "MIT",
                    "checksums": [{"algorithm": "SHA256", "checksumValue": sha256(setup_exe)}],
                },
                {
                    "name": "FacMan self-setup payload",
                    "SPDXID": "SPDXRef-Package-FacManPayload",
                    "versionInfo": version,
                    "downloadLocation": "NOASSERTION",
                    "filesAnalyzed": False,
                    "licenseConcluded": "MIT",
                    "licenseDeclared": "MIT",
                    "checksums": [{"algorithm": "SHA256", "checksumValue": sha256(payload)}],
                    "externalRefs": [
                        {
                            "referenceCategory": "OTHER",
                            "referenceType": "facman:universal-setup-revision",
                            "referenceLocator": provider_revision,
                        }
                    ],
                },
            ],
        },
    )


def _artifact(path: Path, artifact_id: str) -> dict[str, Any]:
    return {
        "id": artifact_id,
        "filename": path.name,
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
        "signed": False,
        "public": False,
    }


def assemble(qualification_root: Path, output: Path) -> dict[str, Any]:
    with SOURCE.open("rb") as stream:
        source = tomllib.load(stream)
    version = str(source["version"])
    tag = str(source["tag"])
    qualification_path = qualification_root / "three-root-qualification.v1.json"
    qualification = load_json(qualification_path)
    if qualification.get("schema") != "facman.alpha2_three_root_qualification.v1":
        raise ValueError("wrong alpha.2 qualification schema")
    if qualification.get("status") != "pass" or qualification.get("mismatch_count") != 0:
        raise ValueError("alpha.2 qualification is not passing and byte-identical")
    if qualification.get("version") != version or qualification.get("root_count") != 3:
        raise ValueError("alpha.2 qualification has the wrong version or root count")
    source_revision = str(qualification["source_revision"])
    source_tree = str(qualification["source_tree"])
    if git("rev-parse", "HEAD") != source_revision or git("status", "--porcelain"):
        raise ValueError("asset assembly requires the clean exact qualified source checkout")
    if git("cat-file", "-t", tag) != "tag":
        raise ValueError("alpha.2 tag must be an annotated tag")
    if git("rev-parse", f"{tag}^{{}}") != source_revision:
        raise ValueError("alpha.2 tag does not target the qualified source revision")
    tag_object = git("rev-parse", tag)

    output = output.resolve()
    if output.exists():
        raise ValueError(f"output root must be new: {output}")
    output.mkdir(parents=True)
    root1 = qualification_root / "root1"
    packages = package_map(qualification)
    for package_id, record in packages.items():
        filename = str(record["filename"])
        package_root = root1 / "packages" / str(record["profile"])
        copy_exact(root1 / "dist" / filename, output / filename, str(record["archive_sha256"]))
        copy_exact(
            package_root / "manifest/sbom.spdx.v2.3.json",
            output / f"{filename}.sbom.spdx.v2.3.json",
            str(record["sbom_sha256"]),
        )
        copy_exact(
            root1 / "dist" / f"{filename}.provenance.v1.json",
            output / f"{filename}.provenance.v1.json",
            str(record["provenance_sha256"]),
        )
        copy_exact(
            root1 / "dist" / f"{filename}.licence-inventory.v1.json",
            output / f"{filename}.licence-inventory.v1.json",
            str(record["licence_inventory_sha256"]),
        )

    setup = qualification["self_setup"]
    setup_root = root1 / "self-setup-dist"
    setup_exe = setup_root / str(setup["setup_executable"]["filename"])
    payload = setup_root / str(setup["payload"]["filename"])
    setup_record = setup_root / f"facman-{version}-self-setup-package.v1.json"
    copy_exact(setup_exe, output / setup_exe.name, str(setup["setup_executable"]["sha256"]))
    copy_exact(payload, output / payload.name, str(setup["payload"]["sha256"]))
    copy_exact(setup_record, output / setup_record.name, str(setup["record_sha256"]))

    setup_stem = f"facman-{version}-windows-x64-self-setup"
    setup_sbom(
        output / f"{setup_stem}.sbom.spdx.v2.3.json",
        version=version,
        setup_exe=output / setup_exe.name,
        payload=output / payload.name,
        source_revision=source_revision,
        provider_revision=str(setup["universal_setup_revision"]),
    )
    setup_licences(
        root1 / "packages/windows_legacy_winforms_x64",
        output / f"{setup_stem}.licence-inventory.v1.json",
    )
    setup_provenance_path = output / f"{setup_stem}.provenance.v1.json"
    write_json(
        setup_provenance_path,
        {
            "schema": "facman.self_setup_provenance.v1",
            "version": version,
            "source_revision": source_revision,
            "source_tree": source_tree,
            "universal_setup_revision": setup["universal_setup_revision"],
            "portable_input": setup["portable_input"],
            "setup_executable": setup["setup_executable"],
            "payload": setup["payload"],
            "qualification_sha256": sha256(qualification_path),
            "fresh_root_count": 3,
            "byte_identical": True,
            "lifecycle": "pass_in_every_root",
            "authority": {
                "signing": False,
                "public_publication": False,
                "support": False,
                "factorio_execution": False,
            },
        },
    )

    limitations = output / f"facman-{version}-known-limitations.md"
    limitations.write_text(
        f"# FacMan {version} known limitations\n\n"
        + "".join(f"- {item}\n" for item in source["known_limitations"]),
        encoding="utf-8",
        newline="\n",
    )

    artifact_records = []
    for item in source["artifact"]:
        artifact_records.append(_artifact(output / str(item["filename"]), str(item["id"])))
    candidate_path = output / f"facman-{version}-candidate.v1.json"
    candidate = {
        "schema": "facman.alpha2_release_candidate.v1",
        "candidate_id": f"facman-{version}-windows-x64-portable-and-self-setup",
        "version": version,
        "release_class": "alpha",
        "status": "qualified_private_draft_candidate",
        "source": {"revision": source_revision, "tree": source_tree, "clean": True},
        "providers": packages["windows_winforms_x64_portable"]["providers"],
        "artifacts": artifact_records,
        "qualification": {
            "receipt_sha256": sha256(qualification_path),
            "comparison_table_sha256": qualification["comparison_table_sha256"],
            "root_count": 3,
            "mismatch_count": 0,
            "portable_runtime": "pass_in_every_root",
            "self_setup_lifecycle": "pass_in_every_root",
        },
        "authority": {
            "public_publication": False,
            "signing": False,
            "support": False,
            "factorio_execution": False,
            "human_verdict": False,
        },
    }
    write_json(candidate_path, candidate)

    tag_receipt_path = output / f"facman-{version}-tag-receipt.v1.json"
    write_json(
        tag_receipt_path,
        {
            "schema": "facman.alpha2_tag_receipt.v1",
            "tag": tag,
            "tag_object_sha": tag_object,
            "source_revision": source_revision,
            "source_tree": source_tree,
            "candidate_sha256": sha256(candidate_path),
            "qualification_sha256": sha256(qualification_path),
            "observed_at": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "intended_release": "private_draft_prerelease",
            "authority": {"public_publication": False, "signing": False, "support": False},
        },
    )

    checksums = output / f"facman-{version}-checksums.txt"
    inventory_without_checksums = sorted(path for path in output.iterdir() if path.is_file())
    checksums.write_text(
        "".join(f"{sha256(path)}  {path.name}\n" for path in inventory_without_checksums),
        encoding="utf-8",
        newline="\n",
    )
    expected = set(source["inventory"]["assets"])
    observed = {path.name for path in output.iterdir() if path.is_file()}
    if observed != expected or len(observed) != int(source["asset_count"]):
        raise ValueError(
            f"asset inventory mismatch: missing={sorted(expected - observed)}, "
            f"unexpected={sorted(observed - expected)}"
        )
    receipt = {
        "schema": "facman.alpha2_asset_set.v1",
        "version": version,
        "tag": tag,
        "source_revision": source_revision,
        "source_tree": source_tree,
        "asset_count": len(observed),
        "assets": {path.name: sha256(path) for path in sorted(output.iterdir()) if path.is_file()},
        "status": "complete_private_draft_asset_set",
    }
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return receipt


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    value.add_argument("--qualification-root", type=Path, required=True)
    value.add_argument("--out", type=Path, required=True)
    return value


def main() -> int:
    args = parser().parse_args()
    assemble(args.qualification_root.resolve(strict=True), args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
