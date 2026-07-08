from __future__ import annotations

from typing import Any

REQUIRED_PRODUCT_KEYS = {"product_id", "display_name", "binding", "capabilities"}


def validate_product_manifest(manifest: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    missing = sorted(REQUIRED_PRODUCT_KEYS - set(manifest))
    if missing:
        problems.append(f"missing product keys: {', '.join(missing)}")
    if manifest.get("product_id") != "factorio":
        problems.append("product_id must be factorio")
    if not isinstance(manifest.get("capabilities"), list):
        problems.append("capabilities must be a list")
    boundaries = manifest.get("boundaries", {})
    if boundaries.get("bundles_factorio_binaries") is not False:
        problems.append("product boundary must not bundle Factorio binaries")
    if boundaries.get("repairs_foreign_installs") is not False:
        problems.append("product boundary must not repair foreign installs")
    return problems

