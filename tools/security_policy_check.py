# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    problems: list[str] = []
    product_path = ROOT / "content" / "factorio" / "product" / "factorio.product.toml"
    redaction_path = ROOT / "content" / "factorio" / "policy" / "redaction.toml"
    account_path = ROOT / "content" / "factorio" / "policy" / "account_secrets.toml"
    redaction_contract_path = ROOT / "contracts" / "policy" / "redaction" / "factorio.v1.toml"

    with product_path.open("rb") as handle:
        product = tomllib.load(handle)
    boundaries = product.get("boundaries", {})
    required_false = [
        "bundles_factorio_binaries",
        "repairs_foreign_installs",
        "uninstalls_foreign_installs",
        "uses_official_branding",
    ]
    for key in required_false:
        if boundaries.get(key) is not False:
            problems.append(f"{product_path}: {key} must be false")

    with redaction_path.open("rb") as handle:
        redaction = tomllib.load(handle)
    redact_keys = set(redaction.get("redact_keys", []))
    for key in ["token", "password", "secret"]:
        if key not in redact_keys:
            problems.append(f"{redaction_path}: missing redact key {key}")

    with account_path.open("rb") as handle:
        account = tomllib.load(handle)
    if account.get("store_passwords") is not False:
        problems.append(f"{account_path}: store_passwords must be false")
    if account.get("store_tokens_in_manifest") is not False:
        problems.append(f"{account_path}: store_tokens_in_manifest must be false")

    with redaction_contract_path.open("rb") as handle:
        redaction_contract = tomllib.load(handle)
    if redaction_contract.get("schema") != "facman.redaction.factorio.v1":
        problems.append(f"{redaction_contract_path}: invalid schema")
    for key in ["allow_credentials_in_manifests", "allow_credentials_in_logs"]:
        if redaction_contract.get(key) is not False:
            problems.append(f"{redaction_contract_path}: {key} must be false")
    for key in ["credential_store_required", "export_redaction_required"]:
        if redaction_contract.get(key) is not True:
            problems.append(f"{redaction_contract_path}: {key} must be true")
    forbidden = set(redaction_contract.get("forbidden_plaintext_fields", []))
    for key in ["password", "token", "secret"]:
        if key not in forbidden:
            problems.append(f"{redaction_contract_path}: missing forbidden plaintext field {key}")

    if problems:
        for problem in problems:
            print(f"security-check: {problem}", file=sys.stderr)
        return 1
    print("security-check: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
