# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

"""Deterministic, non-authorizing assurance for canonical v2 candidates."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any

from tools import json_contract, provenance_build

from .canonical import pretty_json
from .compiler import OUTPUT_FILES
from .outputs import load_resolution
from .packages import (
    MAX_MANIFEST_SIZE,
    _open_stable_file,
    _require_directory,
    _require_unchanged,
    _stable_digest,
    inspect_package,
    verify_package,
)
from .staging import STAGE_MANIFEST_PATH, load_stage_manifest, verify_stage


ROOT = Path(__file__).resolve().parents[2]
SPDX_SCHEMA = ROOT / "contracts/schema/release/spdx_document.v2.3.repository_identity.v1.schema.json"
PROVENANCE_SCHEMA = ROOT / "contracts/schema/release/canonical_candidate_provenance.v1.schema.json"
DEPENDENCY_LOCK = ROOT / "release/index/dependency_lock.v1.toml"
SUPPORTED_TARGET = "windows_winforms_technical_preview_x64"
SUPPORTED_ARTIFACT = "windows_winforms_technical_preview_zip"
SUPPORTED_ADAPTER = "portable_zip"
LICENCES = (
    ("facman", "licenses/LICENSE", "MIT"),
    ("third_party_notices", "licenses/THIRD_PARTY_NOTICES.md", "NOASSERTION"),
    ("universal_launcher", "licenses/UniversalLauncher.txt", "MIT"),
    ("universal_setup", "licenses/UniversalSetup.txt", "MIT"),
    ("miniz", "licenses/Miniz.txt", "MIT"),
    ("picojson", "licenses/PicoJSON.txt", "BSD-2-Clause"),
)
RUNTIME_REQUIRED_PATHS = (
    "bin/FacMan.WinForms.exe",
    "bin/facman.exe",
    "manifest/resolution/release-resolution-set.v1.json",
    "manifest/resolution/runtime-release-metadata.v1.json",
    STAGE_MANIFEST_PATH,
)


def assure_candidate(
    resolution_root: Path,
    artifact_id: str,
    stage_root: Path,
    archive: Path,
    output_root: Path,
) -> tuple[Path, Path]:
    """Write deterministic SPDX and provenance for one exact canonical candidate."""
    archive_path = Path(os.path.abspath(archive))
    stage_path = Path(os.path.abspath(stage_root))
    output_path = Path(os.path.abspath(output_root))
    if output_path == stage_path or stage_path in output_path.parents:
        raise ValueError("candidate assurance output directory must be outside the verified stage")

    sbom = output_path / f"{archive_path.name}.sbom.spdx.v2.3.json"
    provenance = output_path / f"{archive_path.name}.provenance.v1.json"
    documents = _candidate_documents(
        resolution_root,
        artifact_id,
        stage_path,
        archive_path,
        sbom.name,
    )
    rendered = {
        sbom: pretty_json(documents["sbom"]).encode("utf-8"),
        provenance: pretty_json(documents["provenance"]).encode("utf-8"),
    }
    existing = [str(path) for path in rendered if os.path.lexists(path)]
    if existing:
        raise ValueError("candidate assurance output already exists: " + ", ".join(existing))

    output_path.mkdir(parents=True, exist_ok=True)
    _require_directory(output_path)
    published: list[Path] = []
    temporaries: list[Path] = []
    try:
        for destination, content in rendered.items():
            descriptor, temporary_name = tempfile.mkstemp(
                prefix=".facman-assurance-", suffix=".json", dir=output_path
            )
            temporary = Path(temporary_name)
            temporaries.append(temporary)
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            try:
                os.link(temporary, destination)
            except FileExistsError as exc:
                raise ValueError(f"candidate assurance output already exists: {destination}") from exc
            published.append(destination)
            temporary.unlink()
        verify_candidate_assurance(
            resolution_root,
            artifact_id,
            stage_path,
            archive_path,
            sbom,
            provenance,
        )
        published.clear()
        return sbom, provenance
    finally:
        for path in published:
            path.unlink(missing_ok=True)
        for path in temporaries:
            path.unlink(missing_ok=True)


def verify_candidate_assurance(
    resolution_root: Path,
    artifact_id: str,
    stage_root: Path,
    archive: Path,
    sbom_path: Path,
    provenance_path: Path,
) -> dict[str, Any]:
    """Recompute and verify exact candidate assurance without trusting sidecar claims."""
    expected_sbom_name = f"{Path(archive).name}.sbom.spdx.v2.3.json"
    expected_provenance_name = f"{Path(archive).name}.provenance.v1.json"
    if Path(sbom_path).name != expected_sbom_name:
        raise ValueError("candidate SPDX filename differs from the exact archive identity")
    if Path(provenance_path).name != expected_provenance_name:
        raise ValueError("candidate provenance filename differs from the exact archive identity")
    expected = _candidate_documents(
        resolution_root,
        artifact_id,
        Path(stage_root),
        Path(archive),
        expected_sbom_name,
    )
    actual_sbom = _load_json(Path(sbom_path), "candidate SPDX")
    actual_provenance = _load_json(Path(provenance_path), "candidate provenance")
    _validate(actual_sbom, SPDX_SCHEMA, "candidate SPDX")
    _validate(actual_provenance, PROVENANCE_SCHEMA, "candidate provenance")
    if actual_sbom != expected["sbom"]:
        raise ValueError("candidate SPDX differs from the exact canonical stage and archive")
    if actual_provenance != expected["provenance"]:
        raise ValueError("candidate provenance differs from the exact canonical stage and archive")
    return {
        "schema": "facman.canonical_candidate_assurance_verification.v1",
        "artifact_id": artifact_id,
        "stage_digest": actual_provenance["stage"]["stage_digest"],
        "archive_sha256": actual_provenance["artifact"]["sha256"],
        "sbom_sha256": actual_provenance["manifests"]["sbom"]["sha256"],
        "native_admission_ready": actual_provenance["runtime_verifier"][
            "native_admission_ready"
        ],
        "verified": True,
    }


def _candidate_documents(
    resolution_root: Path,
    artifact_id: str,
    stage_root: Path,
    archive: Path,
    sbom_name: str,
) -> dict[str, dict[str, Any]]:
    outputs = load_resolution(Path(resolution_root))
    artifact = _artifact(outputs, artifact_id)
    _require_supported_candidate(outputs, artifact_id, artifact)
    stage_verification = verify_stage(Path(resolution_root), artifact_id, Path(stage_root))
    package_verification = verify_package(Path(resolution_root), artifact_id, Path(archive))
    for field in ("resolution_digest", "resolution_root_digest", "stage_digest"):
        if package_verification[field] != stage_verification[field]:
            raise ValueError(f"candidate archive differs from exact stage identity: {field}")

    expected_name = str(artifact["filename"])
    if Path(archive).name != expected_name:
        raise ValueError("candidate archive filename differs from the resolution")
    inspection = inspect_package(Path(archive))
    expected_format = "zip" if artifact["format"] == "zip" else "tar"
    if inspection["format"] != expected_format:
        raise ValueError("candidate archive format differs from the resolution")
    entries = {str(item["path"]): item for item in inspection["entries"]}
    manifest = load_stage_manifest(Path(stage_root))
    if manifest["stage_digest"] != stage_verification["stage_digest"]:
        raise ValueError("candidate stage identity changed during assurance construction")
    stage_entries = {str(item["path"]): item for item in manifest["entries"]}
    licences = _licence_records(stage_entries)
    _require_runtime_closure(outputs, artifact_id, entries)
    _require_closed_authority(outputs, artifact_id)

    composition = outputs["composition"]
    source = composition["source_observation"]
    dependencies = provenance_build.load_dependencies()
    sbom = _spdx_document(composition, source, dependencies, manifest["stage_digest"])
    _validate(sbom, SPDX_SCHEMA, "candidate SPDX")
    sbom_bytes = pretty_json(sbom).encode("utf-8")

    source_eligible = bool(source["release_eligible"])
    provenance = {
        "schema": "facman.canonical_candidate_provenance.v1",
        "status": "pass",
        "claim": "canonical_candidate_closure_recorded",
        "authenticity": "publisher_authenticity_not_proven",
        "artifact": {
            "id": artifact_id,
            "name": Path(archive).name,
            "format": inspection["format"],
            "size": Path(archive).stat().st_size,
            "sha256": str(inspection["container_sha256"]),
            "inventory_digest": inspection["inventory_digest"],
        },
        "stage": {
            "manifest": STAGE_MANIFEST_PATH,
            "manifest_sha256": entries[STAGE_MANIFEST_PATH]["sha256"],
            "stage_digest": manifest["stage_digest"],
            "entry_count": stage_verification["entry_count"],
        },
        "resolution": {
            "target_id": composition["target_id"],
            "resolution_digest": composition["resolution_digest"],
            "root_digest": outputs["resolution_set"]["root_digest"],
            "source_observation_digest": source["observation_digest"],
        },
        "source": {
            "repository": source["repository"],
            "revision": source["commit"],
            "tree": source["tree"],
            "dirty": source["dirty"],
            "release_eligible": source_eligible,
            "providers": [
                {"id": item["id"], "revision": item["commit"], "tree": item["tree"]}
                for item in sorted(source["providers"], key=lambda row: str(row["id"]))
            ],
        },
        "manifests": {
            "dependency_lock": {
                "path": "release/index/dependency_lock.v1.toml",
                "sha256": _stable_digest(DEPENDENCY_LOCK),
            },
            "resolution_set": _entry_ref(
                entries, f"manifest/resolution/{OUTPUT_FILES['resolution_set']}"
            ),
            "runtime_metadata": _entry_ref(
                entries, f"manifest/resolution/{OUTPUT_FILES['runtime_metadata']}"
            ),
            "sbom": {"path": sbom_name, "sha256": _sha256_bytes(sbom_bytes)},
        },
        "licences": licences,
        "runtime_verifier": {
            "contract": "facman.runtime_package_verifier.canonical_stage.v1",
            "closure_basis": "facman.stage_manifest.v1",
            "backend_path": "bin/facman.exe",
            "required_paths": list(RUNTIME_REQUIRED_PATHS),
            "static_closure_verified": True,
            "target_supported": True,
            "source_release_eligible": source_eligible,
            "native_admission_ready": source_eligible,
            "native_execution": "not_run",
        },
        "toolchain": composition["toolchain"],
        "authority": {
            "product_authority_granted": False,
            "factorio_execution_authorized": False,
            "setup_mutation_authorized": False,
            "supported": False,
        },
        "signed": False,
        "published": False,
    }
    _validate(provenance, PROVENANCE_SCHEMA, "candidate provenance")
    return {"sbom": sbom, "provenance": provenance}


def _artifact(outputs: dict[str, dict[str, Any]], artifact_id: str) -> dict[str, Any]:
    matches = [
        item for item in outputs["package_plan"]["artifacts"] if item.get("id") == artifact_id
    ]
    if len(matches) != 1:
        raise ValueError(f"resolution does not select artifact {artifact_id!r}")
    return matches[0]


def _require_supported_candidate(
    outputs: dict[str, dict[str, Any]], artifact_id: str, artifact: dict[str, Any]
) -> None:
    if (
        outputs["composition"].get("target_id") != SUPPORTED_TARGET
        or artifact_id != SUPPORTED_ARTIFACT
        or artifact.get("adapter") != SUPPORTED_ADAPTER
        or artifact.get("format") != "zip"
    ):
        raise ValueError("canonical candidate assurance supports only the WinForms Technical Preview ZIP")


def _require_runtime_closure(
    outputs: dict[str, dict[str, Any]], artifact_id: str, entries: dict[str, dict[str, Any]]
) -> None:
    missing = sorted(set(RUNTIME_REQUIRED_PATHS) - set(entries))
    if missing:
        raise ValueError(f"candidate archive omits runtime-verifier paths: {missing}")
    runtime = outputs["runtime_metadata"]
    entrypoints = {str(item["path"]) for item in runtime["entrypoints"]}
    if not {"bin/facman.exe", "bin/FacMan.WinForms.exe"}.issubset(entrypoints):
        raise ValueError("runtime metadata omits the CLI or WinForms entrypoint")
    artifacts = [
        item for item in runtime["authority"]["artifacts"] if item.get("artifact_id") == artifact_id
    ]
    if len(artifacts) != 1:
        raise ValueError("runtime metadata omits the exact candidate authority record")


def _require_closed_authority(
    outputs: dict[str, dict[str, Any]], artifact_id: str
) -> None:
    authority = outputs["authority"]
    if authority.get("product_authority_granted") is not False:
        raise ValueError("candidate assurance refuses granted product authority")
    artifacts = [item for item in authority["artifacts"] if item.get("artifact_id") == artifact_id]
    if len(artifacts) != 1:
        raise ValueError("candidate assurance requires one exact artifact authority record")
    for capability in artifacts[0]["capabilities"]:
        if capability.get("currently_authorized") is not False:
            raise ValueError("candidate assurance refuses an authorized payload capability")
        if capability.get("enabled_by_default") is not False:
            raise ValueError("candidate assurance refuses a default-enabled payload capability")


def _licence_records(entries: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    dependencies = provenance_build.load_dependencies()
    records = []
    for component_id, path, spdx in LICENCES:
        entry = entries.get(path)
        if entry is None or entry.get("owner") != "legal_notices":
            raise ValueError(f"candidate stage omits resolution-owned licence: {path}")
        dependency = dependencies.get(component_id)
        if dependency is not None:
            if dependency.get("license") != spdx:
                raise ValueError(f"candidate stage licence identity differs from dependency lock: {path}")
        records.append(
            {
                "component_id": component_id,
                "path": path,
                "spdx": spdx,
                "size": entry["size"],
                "sha256": entry["sha256"],
            }
        )
    return records


def _spdx_document(
    composition: dict[str, Any],
    source: dict[str, Any],
    dependencies: dict[str, dict[str, Any]],
    stage_digest: str,
) -> dict[str, Any]:
    revision = str(source["commit"])
    packages = [
        provenance_build.spdx_package(
            "facman",
            "FacMan",
            str(composition["product_version"]),
            f"https://github.com/{provenance_build.FACMAN_IDENTITY.canonical_slug}",
            "MIT",
            revision,
        )
    ]
    provider_revisions = {
        str(item["id"]): str(item["source_revision"]) for item in composition["providers"]
    }
    for component_id in ("universal_launcher", "universal_setup", "miniz", "picojson"):
        component = dependencies[component_id]
        pin = provider_revisions.get(component_id, str(component["pin"]))
        packages.append(
            provenance_build.spdx_package(
                component_id,
                provenance_build.display_name(component_id),
                str(component["version"]),
                provenance_build.source_location(component_id, component),
                str(component["license"]),
                pin,
                purl=(
                    f"pkg:github/richgel999/miniz@{component['version']}"
                    if component_id == "miniz"
                    else f"pkg:github/kazuho/picojson@{component['version']}"
                    if component_id == "picojson"
                    else None
                ),
            )
        )
    return {
        "spdxVersion": "SPDX-2.3",
        "dataLicense": "CC0-1.0",
        "SPDXID": "SPDXRef-DOCUMENT",
        "name": f"FacMan {composition['target_id']} canonical candidate SBOM",
        "documentNamespace": (
            f"https://github.com/{provenance_build.FACMAN_IDENTITY.canonical_slug}/spdx/"
            f"{revision}/{composition['target_id']}/{stage_digest}"
        ),
        "creationInfo": {
            "created": provenance_build.source_commit_timestamp(revision),
            "creators": ["Tool: FacMan facman-release assure-candidate"],
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
                    "relatedSpdxElement": f"SPDXRef-Package-{item.replace('_', '-')}",
                }
                for item in ("universal_launcher", "universal_setup", "miniz", "picojson")
            ],
        ],
    }


def _entry_ref(entries: dict[str, dict[str, Any]], path: str) -> dict[str, str]:
    if path not in entries:
        raise ValueError(f"candidate archive omits bound manifest: {path}")
    return {"path": path, "sha256": str(entries[path]["sha256"])}


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _load_json(path: Path, label: str) -> dict[str, Any]:
    handle, before = _open_stable_file(Path(os.path.abspath(path)))
    try:
        with handle:
            raw = handle.read(MAX_MANIFEST_SIZE + 1)
            after = os.fstat(handle.fileno())
        _require_unchanged(Path(os.path.abspath(path)), before, after)
        if len(raw) > MAX_MANIFEST_SIZE:
            raise ValueError(f"{label} exceeds the assurance read limit")
        value = json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{label} is malformed: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object")
    return value


def _validate(value: dict[str, Any], schema_path: Path, label: str) -> None:
    problems = json_contract.validate(value, json_contract.load_schema(schema_path))
    if problems:
        raise ValueError(f"{label} violates its contract: " + "; ".join(problems))
