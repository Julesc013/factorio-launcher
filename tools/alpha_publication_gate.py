# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

"""Fail-closed preflight for the manual FacMan alpha publication workflow."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import tomllib
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import alpha_release_source_check, json_contract

SOURCE_PATH = ROOT / "release/index/alpha_release_source.v1.toml"
TRAIN_PATH = ROOT / "release/index/version_train.v1.toml"
CHANNELS_PATH = ROOT / "release/index/channels.v1.toml"
CANDIDATE_SCHEMA = ROOT / "contracts/schema/release/release_candidate.v1.schema.json"
LEDGER_SCHEMA = ROOT / "contracts/schema/release/release_ledger_entry.v1.schema.json"
HUMAN_SCHEMA = ROOT / "contracts/schema/release/human_test_receipt.v1.schema.json"
TAG_RECEIPT_SCHEMA = ROOT / "contracts/schema/release/alpha_tag_receipt.v1.schema.json"
PUBLICATION_AUTHORITY_SCHEMA = (
    ROOT / "contracts/schema/release/alpha_publication_authority.v1.schema.json"
)


def _toml(path: Path) -> dict[str, Any]:
    with path.open("rb") as handle:
        value = tomllib.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a TOML table")
    return value


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode:
        raise ValueError(result.stderr.strip() or f"git {' '.join(args)} failed")
    return result.stdout.strip()


def _schema_problems(value: dict[str, Any], path: Path, label: str) -> list[str]:
    return [
        f"{label} schema rejection: {problem}"
        for problem in json_contract.validate(value, json_contract.load_schema(path))
    ]


def validate_source(source_revision: str | None = None) -> list[str]:
    problems = alpha_release_source_check.validate()
    if source_revision is not None:
        if not re.fullmatch(r"[0-9a-f]{40}", source_revision):
            problems.append("source revision must be one exact lowercase 40-hex commit")
        else:
            try:
                if _git("rev-parse", "HEAD") != source_revision:
                    problems.append("workflow checkout does not match the requested source revision")
                if _git("status", "--porcelain"):
                    problems.append("release-source checkout is dirty")
            except ValueError as exc:
                problems.append(f"release-source Git identity cannot be verified: {exc}")
    return problems


def _checksum_problems(asset_root: Path, checksums: Path, expected: set[str]) -> list[str]:
    problems: list[str] = []
    entries: dict[str, str] = {}
    for raw in checksums.read_text(encoding="utf-8").splitlines():
        match = re.fullmatch(r"([0-9a-f]{64})  ([^/\\]+)", raw)
        if not match:
            problems.append(f"checksum manifest has a malformed line: {raw!r}")
            continue
        digest, name = match.groups()
        if name in entries:
            problems.append(f"checksum manifest repeats {name}")
        entries[name] = digest
    checksummed = expected - {checksums.name}
    if set(entries) != checksummed:
        problems.append("checksum manifest does not bind every non-self alpha asset exactly once")
    for name, expected_digest in entries.items():
        path = asset_root / name
        if path.is_file() and _sha256(path) != expected_digest:
            problems.append(f"checksum mismatch for {name}")
    return problems


def validate_publish(
    *,
    source_revision: str,
    asset_root: Path,
    route_receipt_sha256: str,
    publication_authority_sha256: str,
) -> list[str]:
    problems = validate_source(source_revision)
    try:
        source = _toml(SOURCE_PATH)
        train = _toml(TRAIN_PATH)
        channels = _toml(CHANNELS_PATH)
    except (OSError, ValueError, tomllib.TOMLDecodeError) as exc:
        return problems + [f"publication policy cannot be read: {exc}"]

    for field in ("version_allocation_authorized", "tag_creation_authorized"):
        if train.get(field) is not True:
            problems.append(f"release source must retain active bounded {field}")
    if train.get("publication_authorized") is not False:
        problems.append("release source must retain closed standing publication_authorized")
    standing_authority = train.get("authority", {})
    expected_authority = {
        "version_allocation": True,
        "tag_creation": True,
        "signing": False,
        "publication": False,
        "withdrawal": False,
        "stable_promotion": False,
    }
    if standing_authority != expected_authority:
        problems.append("release source standing authority exceeds bounded alpha tags")
    alpha_class = next(
        (
            item for item in train.get("release_class", [])
            if isinstance(item, dict) and item.get("id") == "alpha"
        ),
        {},
    )
    if alpha_class.get("currently_authorized") is not True:
        problems.append("release source must retain an active bounded alpha tag class")
    alpha_channel = next(
        (
            item for item in channels.get("channel", [])
            if isinstance(item, dict) and item.get("id") == "alpha"
        ),
        {},
    )
    if alpha_channel.get("publication_authorized") is not False:
        problems.append("release source must retain a closed standing alpha channel")
    else:
        problems.append("alpha GitHub prerelease publication is inactive")

    tag = source.get("tag", {}).get("name", "")
    tag_ref = f"refs/tags/{tag}"
    tag_probe = subprocess.run(
        ["git", "show-ref", "--verify", "--quiet", tag_ref],
        cwd=ROOT,
        check=False,
    )
    if tag_probe.returncode not in (0, 1):
        problems.append("alpha tag existence cannot be verified")
    elif tag_probe.returncode == 0:
        try:
            if _git("cat-file", "-t", tag_ref) != "tag":
                problems.append("existing alpha tag is not an annotated tag object")
            if _git("rev-list", "-n", "1", tag_ref) != source_revision:
                problems.append("existing alpha tag does not point to the exact source")
        except ValueError as exc:
            problems.append(f"existing alpha tag cannot be verified: {exc}")

    assets = {
        str(item["id"]): item
        for item in source.get("assets", [])
        if isinstance(item, dict)
    }
    expected_names = {
        str(item["filename"])
        for item in assets.values()
        if item.get("milestone") != "beta_only"
    }
    if not asset_root.is_dir():
        return problems + ["publication requires the downloaded exact asset directory"]
    observed_names = {path.name for path in asset_root.iterdir() if path.is_file()}
    if observed_names != expected_names:
        problems.append("publication asset inventory differs from the tagless manifest")
    missing = [name for name in expected_names if not (asset_root / name).is_file()]
    if missing:
        return problems + [f"publication assets are missing: {sorted(missing)}"]

    candidate_name = str(assets["candidate_record"]["filename"])
    ledger_name = str(assets["public_release_ledger_entry"]["filename"])
    route_name = str(assets["route_receipt"]["filename"])
    authority_name = str(assets["publication_authority_receipt"]["filename"])
    tag_receipt_name = str(assets["tag_receipt"]["filename"])
    checksums_name = str(assets["checksums"]["filename"])
    candidate = _json(asset_root / candidate_name)
    ledger = _json(asset_root / ledger_name)
    route = _json(asset_root / route_name)
    tag_receipt = _json(asset_root / tag_receipt_name)
    publication_authority = _json(asset_root / authority_name)
    problems.extend(_schema_problems(candidate, CANDIDATE_SCHEMA, "candidate"))
    problems.extend(_schema_problems(ledger, LEDGER_SCHEMA, "ledger entry"))
    problems.extend(_schema_problems(route, HUMAN_SCHEMA, "route receipt"))
    problems.extend(_schema_problems(tag_receipt, TAG_RECEIPT_SCHEMA, "tag receipt"))
    problems.extend(
        _schema_problems(
            publication_authority,
            PUBLICATION_AUTHORITY_SCHEMA,
            "publication authority receipt",
        )
    )

    if candidate.get("version") != source.get("version") or candidate.get("release_class") != "alpha":
        problems.append("candidate does not carry the allocated alpha.1 identity")
    if candidate.get("status") != "qualified":
        problems.append("candidate is not qualified")
    if candidate.get("source", {}).get("revision") != source_revision:
        problems.append("candidate source differs from the exact alpha tag")
    if any(
        item.get("result") != "pass"
        for item in candidate.get("three_key", {}).values()
        if isinstance(item, dict)
    ):
        problems.append("candidate does not carry three passing independent decisions")
    if any(value is not False for value in candidate.get("authority", {}).values()):
        problems.append("candidate record improperly grants authority")

    package_records = {
        str(item["id"]): item
        for item in source.get("package", [])
        if isinstance(item, dict)
    }
    package_sha256s = {
        str(item["filename"]): _sha256(asset_root / str(item["filename"]))
        for item in package_records.values()
    }
    candidate_artifacts = {
        item.get("name"): item.get("sha256")
        for item in candidate.get("artifacts", [])
        if isinstance(item, dict)
    }
    if candidate_artifacts != package_sha256s:
        problems.append("candidate record does not bind the exact three-package set")
    route_package = package_records.get(str(source.get("route_candidate_package", "")), {})
    route_package_name = str(route_package.get("filename", ""))
    package_sha256 = package_sha256s.get(route_package_name, "")
    if route.get("result") != "Pass":
        problems.append("alpha publication requires a passing exact route receipt")
    route_candidate = route.get("candidate", {})
    if route_candidate.get("source_revision") != source_revision:
        problems.append("route receipt source differs from the alpha source")
    if route_candidate.get("package_sha256") != package_sha256:
        problems.append("route receipt package differs from the alpha package")
    if _sha256(asset_root / route_name) != route_receipt_sha256:
        problems.append("route receipt digest differs from the explicitly reviewed digest")
    if any(value is not False for value in route.get("authority", {}).values()):
        problems.append("route receipt improperly grants release authority")

    if _sha256(asset_root / authority_name) != publication_authority_sha256:
        problems.append("publication authority receipt differs from the explicitly reviewed digest")
    authority_binding = {
        "version": source.get("version"),
        "tag": tag,
        "source_revision": source_revision,
        "package_sha256": package_sha256,
        "route_receipt_sha256": route_receipt_sha256,
    }
    for field, expected in authority_binding.items():
        if publication_authority.get(field) != expected:
            problems.append(f"publication authority receipt has the wrong {field}")

    if tag_receipt.get("source_revision") != source_revision:
        problems.append("tag receipt source differs from the alpha source")
    if tag_receipt.get("candidate_sha256") != _sha256(asset_root / candidate_name):
        problems.append("tag receipt candidate digest differs from the exact candidate")

    if ledger.get("version") != source.get("version") or ledger.get("source", {}).get("revision") != source_revision:
        problems.append("ledger entry does not bind the exact alpha source")
    if ledger.get("human_receipt") is not None:
        problems.append("alpha ledger entry must not claim the later beta human receipt")
    if ledger.get("support_class") != "unsupported_public_alpha":
        problems.append("alpha ledger support class is not unsupported_public_alpha")
    if any(value is not False for value in ledger.get("authority", {}).values()):
        problems.append("ledger entry improperly grants authority")

    problems.extend(
        _checksum_problems(
            asset_root,
            asset_root / checksums_name,
            expected_names - {authority_name},
        )
    )
    limitations = (asset_root / str(assets["known_limitations"]["filename"])).read_text(encoding="utf-8").lower()
    for anchor in ("unsupported", "unsigned", "human", "beta", "factorio 2.1.14"):
        if anchor not in limitations:
            problems.append(f"known limitations omit required disclosure: {anchor}")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--operation", choices=("qualify", "publish"), default="qualify")
    parser.add_argument("--source-revision")
    parser.add_argument("--asset-root", type=Path)
    parser.add_argument("--route-receipt-sha256")
    parser.add_argument("--publication-authority-sha256")
    args = parser.parse_args(argv)

    if args.operation == "qualify":
        problems = validate_source(args.source_revision)
        success = "release source is valid; all release effects remain closed"
    elif (
        args.source_revision is None
        or args.asset_root is None
        or args.route_receipt_sha256 is None
        or args.publication_authority_sha256 is None
    ):
        problems = [
            "publish requires source revision, asset root, reviewed route receipt digest, "
            "and reviewed publication authority receipt digest"
        ]
        success = ""
    else:
        problems = validate_publish(
            source_revision=args.source_revision,
            asset_root=args.asset_root,
            route_receipt_sha256=args.route_receipt_sha256,
            publication_authority_sha256=args.publication_authority_sha256,
        )
        success = "exact alpha publication inputs and separate authority are valid"
    if problems:
        for problem in problems:
            print(f"alpha-publication-gate: {problem}", file=sys.stderr)
        return 1
    print(f"alpha-publication-gate: ok ({success})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
