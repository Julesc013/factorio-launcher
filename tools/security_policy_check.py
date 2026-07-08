from __future__ import annotations

import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    problems: list[str] = []
    product_path = ROOT / "factorio" / "product" / "factorio.product.toml"
    redaction_path = ROOT / "factorio" / "product" / "policy" / "redaction.toml"
    account_path = ROOT / "factorio" / "product" / "policy" / "account-secrets.toml"

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

    if problems:
        for problem in problems:
            print(f"security-check: {problem}", file=sys.stderr)
        return 1
    print("security-check: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
