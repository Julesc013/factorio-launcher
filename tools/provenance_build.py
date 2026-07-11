from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tomllib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import json_contract

SPDX_SCHEMA = ROOT / "contracts/schema/release/spdx_document.v2.3.schema.json"
PROVENANCE_SCHEMA = ROOT / "contracts/schema/release/build_provenance.v1.schema.json"
DEPENDENCY_LOCK = ROOT / "release/index/dependency_lock.v1.toml"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify FacMan unsigned artifact provenance.")
    parser.add_argument("--provenance", required=True)
    parser.add_argument("--artifact", required=True)
    parser.add_argument("--package-root", required=True)
    args = parser.parse_args(argv)
    problems = verify_artifact_provenance(
        Path(args.provenance).resolve(),
        Path(args.artifact).resolve(),
        Path(args.package_root).resolve(),
    )
    if problems:
        for problem in problems:
            print(f"provenance-verify: {problem}", file=sys.stderr)
        return 1
    print("provenance-verify: ok")
    return 0


def write_package_sbom(package_root: Path, build_info: dict[str, Any]) -> Path:
    source_revision = str(build_info["source_revisions"]["factorio_launcher"])
    profile_id = str(build_info["profile_id"])
    dependencies = load_dependencies()
    packages = [
        spdx_package(
            "facman",
            "FacMan",
            str(build_info["canonical_version"]),
            "https://github.com/Julesc013/factorio-launcher",
            "MIT",
            source_revision,
        )
    ]
    for component_id in ("universal_launcher", "universal_setup", "miniz"):
        component = dependencies[component_id]
        packages.append(
            spdx_package(
                component_id,
                display_name(component_id),
                str(component["version"]),
                source_location(component_id, component),
                str(component.get("license", "NOASSERTION")),
                str(component["pin"]),
                purl=(
                    f"pkg:github/richgel999/miniz@{component['version']}"
                    if component_id == "miniz"
                    else None
                ),
            )
        )
    document = {
        "spdxVersion": "SPDX-2.3",
        "dataLicense": "CC0-1.0",
        "SPDXID": "SPDXRef-DOCUMENT",
        "name": f"FacMan {profile_id} package SBOM",
        "documentNamespace": (
            "https://github.com/Julesc013/factorio-launcher/spdx/"
            f"{source_revision}/{profile_id}"
        ),
        "creationInfo": {
            "created": str(build_info["source_timestamp_utc"]),
            "creators": ["Tool: FacMan provenance_build.py"],
            "comment": "Timestamp policy: source_commit_utc; unsigned build evidence.",
        },
        "packages": packages,
        "relationships": [
            {
                "spdxElementId": "SPDXRef-DOCUMENT",
                "relationshipType": "DESCRIBES",
                "relatedSpdxElement": "SPDXRef-Package-facman",
            },
            *[
                {
                    "spdxElementId": "SPDXRef-Package-facman",
                    "relationshipType": "DEPENDS_ON",
                    "relatedSpdxElement": f"SPDXRef-Package-{component_id.replace('_', '-')}",
                }
                for component_id in ("universal_launcher", "universal_setup", "miniz")
            ],
        ],
    }
    validate_or_raise(document, SPDX_SCHEMA, "SPDX document")
    destination = package_root / "manifest" / "sbom.spdx.v2.3.json"
    destination.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return destination


def write_artifact_provenance(
    package_root: Path,
    artifact: Path,
) -> Path:
    build_info = load_json(package_root / "manifest/build_info.v1.json")
    source_revisions = build_info["source_revisions"]
    ci = ci_identity(str(source_revisions["factorio_launcher"]))
    report = {
        "schema": "facman.build_provenance.v1",
        "status": "pass",
        "claim": "provenance_recorded",
        "authenticity": "publisher_authenticity_not_proven",
        "profile_id": build_info["profile_id"],
        "artifact": {
            "name": artifact.name,
            "size": artifact.stat().st_size,
            "sha256": sha256(artifact),
        },
        "source_revisions": source_revisions,
        "source_state": {
            "dirty": build_info["source_dirty"],
            "sha256": build_info["source_state_sha256"],
        },
        "workspace_lock": digest_ref(
            package_root,
            package_root / "release/index/workspace_lock.v1.toml",
        ),
        "manifests": {
            "components": digest_ref(
                package_root,
                package_root / "manifest/components.v1.json",
            ),
            "hashes": digest_ref(
                package_root,
                package_root / "manifest/hashes.sha256",
            ),
            "sbom": digest_ref(
                package_root,
                package_root / "manifest/sbom.spdx.v2.3.json",
            ),
        },
        "toolchain": build_info["toolchain"],
        "ci": ci,
        "timestamp": {
            "policy": "source_commit_utc",
            "value": build_info["source_timestamp_utc"],
        },
        "signed": False,
        "published": False,
    }
    validate_or_raise(report, PROVENANCE_SCHEMA, "build provenance")
    destination = artifact.with_name(artifact.name + ".provenance.v1.json")
    destination.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    problems = verify_artifact_provenance(destination, artifact, package_root)
    if problems:
        raise ValueError("generated provenance failed verification: " + "; ".join(problems))
    return destination


def verify_artifact_provenance(
    provenance_path: Path,
    artifact: Path,
    package_root: Path,
) -> list[str]:
    try:
        report = load_json(provenance_path)
        schema = json_contract.load_schema(PROVENANCE_SCHEMA)
        problems = json_contract.validate(report, schema)
        build_info = load_json(package_root / "manifest/build_info.v1.json")
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return [str(exc)]
    artifact_record = report.get("artifact", {})
    if artifact_record.get("name") != artifact.name:
        problems.append("artifact name disagrees with provenance")
    if artifact.is_file():
        if artifact_record.get("size") != artifact.stat().st_size:
            problems.append("artifact size disagrees with provenance")
        if artifact_record.get("sha256") != sha256(artifact):
            problems.append("artifact digest disagrees with provenance")
    else:
        problems.append("artifact is missing")
    if report.get("source_revisions") != build_info.get("source_revisions"):
        problems.append("source revisions disagree with build information")
    expected_source_state = {
        "dirty": build_info.get("source_dirty"),
        "sha256": build_info.get("source_state_sha256"),
    }
    if report.get("source_state") != expected_source_state:
        problems.append("source tree state disagrees with build information")
    if report.get("toolchain") != build_info.get("toolchain"):
        problems.append("toolchain disagrees with build information")
    expected_timestamp = {
        "policy": "source_commit_utc",
        "value": build_info.get("source_timestamp_utc"),
    }
    if report.get("timestamp") != expected_timestamp:
        problems.append("timestamp policy or value disagrees with build information")
    expected_refs = {
        "workspace_lock": package_root / "release/index/workspace_lock.v1.toml",
        "components": package_root / "manifest/components.v1.json",
        "hashes": package_root / "manifest/hashes.sha256",
        "sbom": package_root / "manifest/sbom.spdx.v2.3.json",
    }
    actual_workspace = report.get("workspace_lock", {})
    check_digest_ref(actual_workspace, expected_refs["workspace_lock"], package_root, problems)
    manifests = report.get("manifests", {})
    for key in ("components", "hashes", "sbom"):
        check_digest_ref(manifests.get(key, {}), expected_refs[key], package_root, problems)
    try:
        sbom = load_json(expected_refs["sbom"])
        problems.extend(json_contract.validate(sbom, json_contract.load_schema(SPDX_SCHEMA)))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        problems.append(f"cannot validate package SPDX document: {exc}")
    ci = report.get("ci", {})
    source_sha = str(build_info.get("source_revisions", {}).get("factorio_launcher", ""))
    if ci.get("source_sha") != source_sha:
        problems.append("CI source SHA disagrees with the packaged source revision")
    if ci.get("provider") == "github_actions":
        for key in ("run_id", "run_attempt", "workflow", "repository"):
            if ci.get(key) in {"", "not_applicable", None}:
                problems.append(f"GitHub Actions provenance is missing {key}")
    elif ci.get("provider") == "local":
        if any(ci.get(key) != "not_applicable" for key in ("run_id", "run_attempt", "workflow")):
            problems.append("local provenance contains a false CI run identity")
    return problems


def source_commit_timestamp(revision: str) -> str:
    completed = subprocess.run(
        ["git", "show", "-s", "--format=%cI", revision],
        cwd=ROOT,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if completed.returncode != 0 or not completed.stdout.strip():
        raise ValueError(f"cannot read source commit timestamp for {revision}")
    parsed = datetime.fromisoformat(completed.stdout.strip().replace("Z", "+00:00"))
    return parsed.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_dependencies() -> dict[str, dict[str, Any]]:
    with DEPENDENCY_LOCK.open("rb") as handle:
        data = tomllib.load(handle)
    return {
        str(component["id"]): component
        for component in data.get("component", [])
        if isinstance(component, dict) and component.get("id")
    }


def spdx_package(
    component_id: str,
    name: str,
    version: str,
    location: str,
    license_id: str,
    pin: str,
    purl: str | None = None,
) -> dict[str, Any]:
    package = {
        "SPDXID": f"SPDXRef-Package-{component_id.replace('_', '-')}",
        "name": name,
        "versionInfo": version,
        "downloadLocation": location,
        "filesAnalyzed": False,
        "licenseConcluded": license_id,
        "licenseDeclared": license_id,
        "copyrightText": "NOASSERTION",
        "packageComment": f"Source revision or pin: {pin}; unsigned evidence.",
    }
    if purl:
        package["externalRefs"] = [
            {
                "referenceCategory": "PACKAGE-MANAGER",
                "referenceType": "purl",
                "referenceLocator": purl,
            }
        ]
    return package


def display_name(component_id: str) -> str:
    return {
        "universal_launcher": "Universal Launcher",
        "universal_setup": "Universal Setup",
        "miniz": "Miniz",
    }[component_id]


def source_location(component_id: str, component: dict[str, Any]) -> str:
    return {
        "universal_launcher": "https://github.com/Julesc013/universal-launcher",
        "universal_setup": "https://github.com/Julesc013/universal-setup",
        "miniz": str(component["source"]),
    }[component_id]


def ci_identity(source_revision: str) -> dict[str, str]:
    if os.environ.get("GITHUB_ACTIONS") == "true":
        source_sha = os.environ.get("GITHUB_SHA", "").lower()
        if source_sha != source_revision:
            raise ValueError("GitHub source SHA disagrees with packaged source revision")
        return {
            "provider": "github_actions",
            "run_id": os.environ.get("GITHUB_RUN_ID", ""),
            "run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT", ""),
            "workflow": os.environ.get("GITHUB_WORKFLOW", ""),
            "repository": os.environ.get("GITHUB_REPOSITORY", ""),
            "source_sha": source_sha,
        }
    return {
        "provider": "local",
        "run_id": "not_applicable",
        "run_attempt": "not_applicable",
        "workflow": "not_applicable",
        "repository": "Julesc013/factorio-launcher",
        "source_sha": source_revision,
    }


def digest_ref(root: Path, path: Path) -> dict[str, str]:
    return {
        "path": path.relative_to(root).as_posix(),
        "sha256": sha256(path),
    }


def check_digest_ref(
    record: Any,
    path: Path,
    root: Path,
    problems: list[str],
) -> None:
    expected_path = path.relative_to(root).as_posix()
    if not isinstance(record, dict) or record.get("path") != expected_path:
        problems.append(f"manifest reference path disagrees: {expected_path}")
        return
    if not path.is_file() or record.get("sha256") != sha256(path):
        problems.append(f"manifest digest disagrees: {expected_path}")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected a JSON object")
    return value


def validate_or_raise(value: dict[str, Any], schema_path: Path, label: str) -> None:
    schema = json_contract.load_schema(schema_path)
    problems = json_contract.validate(value, schema)
    if problems:
        raise ValueError(f"{label} violates its contract: " + "; ".join(problems))


if __name__ == "__main__":
    raise SystemExit(main())
