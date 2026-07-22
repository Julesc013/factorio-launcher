# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import argparse
import hashlib
import json
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "contracts/policy/factorio/hermetic_standalone_play_2_0_77_windows_x64.v1.toml"
OUTPUT = ROOT / "contracts/generated-index/hermetic_standalone_play_policy.v1.canonical.json"
EXPECTED_DIGEST = "6fde31f26d57e23d67c01dd598cb869a4914d11711868b46d4f817709455e7a2"


def canonical_bytes() -> bytes:
    with POLICY.open("rb") as handle:
        policy = tomllib.load(handle)
    recorded = policy.pop("policy_digest", None)
    payload = json.dumps(
        policy,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    digest = hashlib.sha256(payload).hexdigest()
    if recorded != EXPECTED_DIGEST or digest != EXPECTED_DIGEST:
        raise RuntimeError(
            f"frozen policy digest mismatch: recorded={recorded} computed={digest}"
        )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check or regenerate the Gate 4A canonical policy mirror."
    )
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    expected = canonical_bytes()
    if args.write:
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT.write_bytes(expected + b"\n")
        print(f"wrote {OUTPUT.relative_to(ROOT)} ({len(expected)} canonical bytes)")
        return 0
    if not OUTPUT.is_file():
        raise RuntimeError(f"missing canonical policy mirror: {OUTPUT.relative_to(ROOT)}")
    actual = OUTPUT.read_bytes()
    if actual not in {expected, expected + b"\n"}:
        raise RuntimeError("canonical policy mirror is stale")
    print(f"PASS: canonical policy mirror {EXPECTED_DIGEST}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
