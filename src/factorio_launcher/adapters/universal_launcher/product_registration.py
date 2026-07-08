from __future__ import annotations

from factorio_launcher.factorio.binding.product_manifest import load_product_manifest


def product_registration() -> dict[str, object]:
    manifest = load_product_manifest()
    return {
        "product_id": manifest["product_id"],
        "display_name": manifest["display_name"],
        "binding": manifest["binding"],
        "capabilities": manifest["capabilities"],
    }

