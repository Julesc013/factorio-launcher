# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT
"""Bind supplied-package resource observations to actual candidate asset closure."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path, PurePosixPath
from typing import Any

from tools import json_contract
from tools.package import candidate_evidence as candidate
from tools.package.payload_equivalence import FileIdentity, inventory_digest

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = "facman.resource_candidate_qualification.v1"
MANIFEST = "resource-candidate-qualification.v1.json"
MAX_FILE_BYTES = 64 * 1024 * 1024
MAX_TOTAL_BYTES = 512 * 1024 * 1024
MAX_FILES = 4096
MODES = {"portable": "portable", "installed": "installed_stage"}
CASES = {
    "original_identity", "relocated_identity", "export_members",
    "existing_output_refusal", "missing_resource_refusal",
    "truncated_resource_refusal", "foreign_resource_refusal",
    "no_display_terminal", "original_unchanged",
}
LAYOUTS = {
    "windows": ("bin/facman.exe", "facman.resources", "manifest/package.v1.toml"),
    "linux": ("facman", "share/facman/facman.resources",
              "share/facman/manifest/product-stage.v1.json"),
    "macos": ("Contents/Helpers/facman", "Contents/Resources/facman.resources",
              "Contents/Resources/manifest/product-stage.v1.json"),
}
PROOF_AUTHORITY = {key: False for key in (
    "release", "tagging", "signing", "publication", "human_acceptance", "game", "live_installation")}
SUCCESS_COMMANDS = {
    "original_list", "original_verify", "relocated_list", "relocated_verify",
    "original_help", "original_version", "relocated_help", "relocated_version", "export",
    "missing_help", "missing_version", "truncated_help", "truncated_version",
    "standalone_foreign", "foreign_help", "foreign_version",
}
REFUSAL_COMMANDS = {"existing_output", "missing", "truncated", "foreign"}
AUTHORITY = dict(candidate.AUTHORITY, human_acceptance=False, game=False,
                 live_installation=False)


def safe_name(value: Any) -> str:
    if (not isinstance(value, str) or not value or len(value) > 1024
            or "\\" in value or ":" in value or "\x00" in value):
        raise ValueError("noncanonical resource artifact path")
    path = PurePosixPath(value)
    if path.is_absolute() or path.as_posix() != value or any(
            part in {".", "..", ""} for part in path.parts):
        raise ValueError("unsafe resource artifact path")
    return value


def linked(path: Path) -> bool:
    return path.is_symlink() or bool(getattr(path, "is_junction", lambda: False)())


def admitted_root(path: Path) -> Path:
    """Reject linked ancestry and checkout effects before resolving any member."""
    value = Path(os.path.abspath(path))
    for parent in (value, *value.parents):
        if linked(parent):
            raise ValueError("linked resource evidence ancestry")
    value = value.resolve()
    if value == ROOT or value.is_relative_to(ROOT):
        raise ValueError("resource evidence must be outside the source checkout")
    return value


def regular(root: Path, relative: str) -> Path:
    relative = safe_name(relative)
    path = root
    if linked(root):
        raise ValueError("linked resource evidence root")
    for part in PurePosixPath(relative).parts:
        path = path / part
        if linked(path):
            raise ValueError("linked resource evidence member")
    stat = path.stat()
    if not path.is_file() or stat.st_nlink != 1 or not 0 <= stat.st_size <= MAX_FILE_BYTES:
        raise ValueError("resource evidence file is missing, linked or over budget")
    return path


def read_bytes(path: Path) -> bytes:
    with path.open("rb") as stream:
        data = stream.read(MAX_FILE_BYTES + 1)
    if len(data) > MAX_FILE_BYTES:
        raise ValueError("resource evidence read budget exhausted")
    return data


def record(path: Path, name: str) -> dict[str, Any]:
    data = read_bytes(path)
    return {"path": name, "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest()}


def read_json(path: Path) -> Any:
    return json.loads(read_bytes(path))


def validate_inventory(value: Any, platform: str) -> tuple[dict, str]:
    if not isinstance(value, list) or not 1 <= len(value) <= 65536:
        raise ValueError("bounded complete resource input inventory required")
    indexed: dict[str, Any] = {}
    identities = []
    total = 0
    for item in value:
        if (not isinstance(item, dict) or set(item) != {"path", "size", "sha256", "mode"}
                or type(item["size"]) is not int or not 0 <= item["size"] <= 512 * 1024 * 1024
                or type(item["mode"]) is not int or not 0 <= item["mode"] <= 0o7777):
            raise ValueError("invalid resource inventory entry")
        name = safe_name(item["path"])
        digest = item["sha256"]
        if (not isinstance(digest, str) or len(digest) != 64
                or any(c not in "0123456789abcdef" for c in digest) or name in indexed):
            raise ValueError("invalid or duplicate resource inventory identity")
        total += item["size"]
        if total > 2 * 1024 * 1024 * 1024:
            raise ValueError("resource inventory byte budget exhausted")
        indexed[name] = item
        normalized = "FacMan.app/" + name if platform == "macos" else name
        identities.append(FileIdentity(normalized, item["size"], digest, item["mode"]))
    return indexed, inventory_digest(identities, include_posix_mode=platform != "windows")


def proof_files(parent: Path, receipt_name: str, platform: str, mode: str,
                bundle: dict, equivalence: dict) -> tuple[dict, dict[str, dict]]:
    receipt_path = regular(parent, receipt_name)
    value = read_json(receipt_path)
    schema = json_contract.load_schema(
        ROOT / "contracts/schema/release/facman_resource_package_proof.v1.schema.json")
    problems = json_contract.validate(value, schema)
    if (not isinstance(value, dict) or value.get("authority") != PROOF_AUTHORITY
            or any(flag is not False for flag in value.get("authority", {}).values())):
        problems.append("resource proof authority differs")
    if problems:
        raise ValueError("resource proof schema: " + "; ".join(problems[:5]))
    expected_platform = {"windows": "win32", "linux": "linux", "macos": "darwin"}[platform]
    if (value["status"] != "pass" or value["failure"] is not None
            or value["profile_id"] != platform + "_product_x64"
            or value["package_mode"] != mode or value["platform"] != expected_platform
            or value["source_revision"] != bundle["source_revision"]
            or value["source_tree"] != bundle["source_tree"]
            or value["source_dirty"] is not False or value["original_unchanged"] is not True
            or value["input_provenance"] != "supplied_path_not_producer_attested"):
        raise ValueError("resource proof does not bind the exact clean candidate")
    cases = value["cases"]
    if (len(cases) != len(CASES) or {case["id"] for case in cases} != CASES
            or any(case["status"] != "pass" for case in cases)):
        raise ValueError("resource proof case closure is incomplete")
    files = {receipt_name: record(receipt_path, receipt_name)}
    if len(value["artifacts"]) > MAX_FILES:
        raise ValueError("resource artifact count exhausted")
    for item in value["artifacts"]:
        name = safe_name(item["path"])
        if name in files or record(regular(parent, name), name) != item:
            raise ValueError("resource raw artifact identity differs or duplicates")
        files[name] = item
    required_artifacts = [value["proof_source_artifact"]]
    command_ids = {row["id"] for row in value["commands"]}
    if (command_ids != SUCCESS_COMMANDS | REFUSAL_COMMANDS
            or len(command_ids) != len(value["commands"])):
        raise ValueError("resource command evidence is missing or duplicated")
    for command in value["commands"]:
        if (command["timed_out"] or command["output_limit_exceeded"]
                or command["error"] is not None or type(command["exit_code"]) is not int
                or command["exit_code"] != int(command["id"] in REFUSAL_COMMANDS)):
            raise ValueError("resource command did not complete within its bounds")
        required_artifacts.extend((command["stdout"], command["stderr"]))
    if any(safe_name(name) not in files for name in required_artifacts):
        raise ValueError("resource command or source raw artifact is missing")
    observed = value["input"]
    if not isinstance(observed, dict):
        raise ValueError("complete resource input binding required")
    inventory_name = safe_name(observed["inventory_artifact"])
    if (inventory_name not in files
            or files[inventory_name]["sha256"] != observed["inventory_sha256"]):
        raise ValueError("resource inventory artifact is not bound")
    inventory, stage_digest = validate_inventory(
        read_json(regular(parent, inventory_name)), platform)
    if (stage_digest != equivalence["canonical_stage_digest"]
            or len(inventory) != equivalence["canonical_file_count"]):
        raise ValueError("resource inventory differs from the produced asset payload")
    for role, expected_path in zip(("executable", "resource", "manifest"), LAYOUTS[platform]):
        item = observed[role]
        source = inventory.get(expected_path)
        if (source is None or item != {"path": expected_path, "bytes": source["size"],
                                      "sha256": source["sha256"]}):
            raise ValueError("resource executable/pack/manifest role differs from payload")
    if value["executable_sha256"] != observed["executable"]["sha256"]:
        raise ValueError("resource executable binding differs")
    return {"platform": platform, "package_mode": mode,
            "receipt": record(receipt_path, platform + "/" + receipt_name),
            "canonical_stage_digest": stage_digest,
            "executable_sha256": value["executable_sha256"]}, files


def observations(bundle_root: Path, inputs: Path) -> tuple[dict, dict[str, dict], dict]:
    bundle_root, inputs = admitted_root(bundle_root), admitted_root(inputs)
    bundle = candidate.verify_bundle(bundle_root)
    rows = []
    files: dict[str, dict] = {}
    total = 0
    for platform in candidate.ASSET_SUFFIXES:
        equivalence = candidate.read_json(bundle_root / f"{platform}-payload-equivalence.v1.json")
        for spelling, mode in MODES.items():
            name = f"{platform}-{spelling}-resource-package.v1.json"
            row, members = proof_files(inputs / platform, name, platform, mode, bundle, equivalence)
            rows.append(row)
            for relative, item in members.items():
                path = platform + "/" + relative
                if path in files:
                    raise ValueError("resource companion artifact path collision")
                files[path] = dict(item, path=path)
                total += item["bytes"]
                if len(files) > MAX_FILES or total > MAX_TOTAL_BYTES:
                    raise ValueError("resource companion evidence budget exhausted")
    return bundle, files, {"proofs": rows}


def companion_record(bundle_root: Path, bundle: dict, files: dict, details: dict) -> dict:
    return {
        "schema": SCHEMA, "status": "pass",
        "candidate_bundle": candidate.file_record(bundle_root / "product-candidate-bundle.v1.json"),
        "source_revision": bundle["source_revision"], "source_tree": bundle["source_tree"],
        "github": bundle["github"], "assets": bundle["assets"],
        "proofs": details["proofs"], "files": [files[name] for name in sorted(files)],
        "authority": AUTHORITY,
    }


def tree_files(root: Path) -> set[str]:
    found: set[str] = set()
    stack = [root]
    nodes = 0
    while stack:
        folder = stack.pop()
        for entry in os.scandir(folder):
            path = Path(entry.path)
            nodes += 1
            if nodes > MAX_FILES * 2 or linked(path):
                raise ValueError("resource companion traversal is linked or over budget")
            if entry.is_dir(follow_symlinks=False):
                stack.append(path)
            elif entry.is_file(follow_symlinks=False):
                found.add(path.relative_to(root).as_posix())
            else:
                raise ValueError("resource companion contains a special file")
    return found


def verify(root: Path, bundle_root: Path) -> dict:
    root, bundle_root = admitted_root(root), admitted_root(bundle_root)
    if linked(root) or not root.is_dir():
        raise ValueError("resource companion root is missing or linked")
    bundle, files, details = observations(bundle_root, root / "proofs")
    expected = companion_record(bundle_root, bundle, files, details)
    manifest = regular(root, MANIFEST)
    if read_bytes(manifest) != (json.dumps(expected, indent=2, sort_keys=True) + "\n").encode():
        raise ValueError("resource companion binding or canonical record differs")
    if tree_files(root) != {MANIFEST, *("proofs/" + name for name in files)}:
        raise ValueError("resource companion file closure differs")
    return expected


def build(bundle_root: Path, inputs: Path, output: Path) -> Path:
    bundle_root, inputs, output = (admitted_root(path) for path in (bundle_root, inputs, output))
    if any(output == source or output.is_relative_to(source) or source.is_relative_to(output)
           for source in (bundle_root, inputs)):
        raise ValueError("resource companion output overlaps an input")
    bundle, files, details = observations(bundle_root, inputs)
    if output.exists() or linked(output):
        raise ValueError("resource companion output must be new")
    output.mkdir(parents=True)
    for name, item in files.items():
        source = regular(inputs, name)
        destination = output / "proofs" / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("xb") as stream:
            stream.write(read_bytes(source))
        if record(destination, name) != item:
            raise ValueError("resource evidence changed while copying; output retained")
    manifest = output / MANIFEST
    with manifest.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(companion_record(bundle_root, bundle, files, details),
                                indent=2, sort_keys=True) + "\n")
    verify(output, bundle_root)
    return manifest
