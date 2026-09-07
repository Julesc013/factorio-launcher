# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

"""Verify explicit local source custody without granting stable/provider authority."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

import jsonschema

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from tools import provider_source_bytes  # noqa: E402

SCHEMA = ROOT / "contracts/schema/release/provider_local_source_custody.v1.schema.json"
LIMIT = 262144
REMOTE = "https://github.com/Julesc013/universal-setup.git"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON field: {key}")
        result[key] = value
    return result


def load_record(path: Path) -> dict:
    with path.open("rb") as stream:
        raw = stream.read(LIMIT + 1)
    if len(raw) > LIMIT:
        raise ValueError("local source custody record exceeds its observation limit")
    value = json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs)
    if not isinstance(value, dict):
        raise ValueError("local source custody must be a JSON object")
    return value


def git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-c", f"safe.directory={root.as_posix()}", "-c", "core.fsmonitor=false", *args],
        cwd=root, capture_output=True, text=True, encoding="utf-8", check=False,
    )
    if result.returncode:
        raise ValueError(f"local provider Git observation failed: {result.stderr.strip()}")
    return result.stdout.strip()


def validate(
    custody: Path, expected_sha256: str, root: Path, commit: str,
    tree: str, remote: str, source_ref: str, observation: dict | None = None,
) -> dict:
    if not re.fullmatch(r"[0-9a-f]{64}", expected_sha256):
        raise ValueError("local custody requires an exact reviewed SHA256")
    custody = custody.resolve(strict=True)
    provider_source_bytes.reject_indirection(root.absolute())
    root = root.resolve(strict=True)
    if custody.is_relative_to(root) or custody.is_relative_to(ROOT):
        raise ValueError("local custody must remain outside provider and consumer sources")
    # Hash the same bounded bytes that are parsed, not a second pathname read.
    with custody.open("rb") as stream:
        raw = stream.read(LIMIT + 1)
    if len(raw) > LIMIT or hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise ValueError("local custody bytes differ from the explicit reviewed digest")
    data = json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs)
    jsonschema.Draft202012Validator(load_record(SCHEMA)).validate(data)
    expected = {"commit": commit, "tree": tree, "ref": source_ref,
                "remote": remote, "repository": "Julesc013/universal-setup"}
    if data["source"] != expected or remote != REMOTE:
        raise ValueError("local custody does not match the selected provider lock")
    receipt_path = Path(data["review"]["receipt"])
    if not receipt_path.is_absolute():
        raise ValueError("local review receipt must be an explicit absolute path")
    with receipt_path.open("rb") as stream:
        receipt_raw = stream.read(LIMIT + 1)
    if (len(receipt_raw) > LIMIT or
            hashlib.sha256(receipt_raw).hexdigest() != data["review"]["sha256"]):
        raise ValueError("local review receipt bytes differ from their bound digest")
    review = json.loads(receipt_raw.decode("utf-8"), object_pairs_hook=_pairs)
    if (not isinstance(review, dict) or
            review.get("schema") != "facman.provider-checkpoint-root-review.v1" or
            review.get("result") != "pass" or review.get("clean") is not True or
            review.get("commit") != commit or review.get("tree") != tree or
            not isinstance(review.get("authority"), dict) or
            set(review["authority"]) != {"consumer_qualification", "provider_adoption", "publication"} or
            any(value is not False for value in review["authority"].values())):
        raise ValueError("local review receipt does not bind the non-authorizing checkpoint")
    if git(root, "rev-parse", "--show-prefix"):
        raise ValueError("local provider path must be the exact Git root")
    if git(root, "config", "--get-all", "remote.origin.url") != remote:
        raise ValueError("local provider origin differs from custody")
    if git(root, "symbolic-ref", "-q", "HEAD") != source_ref:
        raise ValueError("local provider must remain on the exact reviewed task ref")
    if (git(root, "rev-parse", "HEAD") != commit or
            git(root, "rev-parse", "HEAD^{tree}") != tree or
            git(root, "rev-parse", source_ref + "^{commit}") != commit):
        raise ValueError("actual local provider HEAD/tree/ref differs from custody")
    # A clean status can conceal altered bytes under assume-unchanged or skip-worktree.
    # Sparse directory entries also lack a fully observed source checkout. Only ordinary
    # cached tracked entries are admitted; this observation grants no atomic build lease.
    for flag in ("-v", "-f"):
        tracked = git(root, "ls-files", flag, "-z", "--sparse")
        if not tracked or any(not row.startswith("H ") for row in tracked.split("\0") if row):
            raise ValueError("local provider source has flagged or sparse tracked entries")
    physical = provider_source_bytes.observe(root, commit)
    if git(root, "status", "--porcelain=v1", "--untracked-files=all",
           "--ignore-submodules=none"):
        raise ValueError("local provider source is dirty")
    if observation is not None:
        observation.update(physical)
    return data


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--custody", type=Path, required=True)
    parser.add_argument("--sha256", required=True)
    parser.add_argument("--root", type=Path, required=True)
    for name in ("commit", "tree", "remote", "ref"):
        parser.add_argument("--" + name, required=True)
    args = parser.parse_args()
    try:
        validate(args.custody, args.sha256, args.root, args.commit,
                 args.tree, args.remote, args.ref)
    except (ValueError, OSError, jsonschema.ValidationError) as error:
        print(f"local-source-custody: {error}", file=sys.stderr)
        return 1
    print("reviewed_local_checkpoint")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
