from __future__ import annotations

from typing import Any


def make_install_ref(
    *,
    install_id: str,
    source: str,
    ownership: str,
    version: str | None,
    channel: str | None,
    platform_name: str,
    executable: str,
    app_dir: str,
    capabilities: list[str],
    verification: dict[str, Any],
) -> dict[str, Any]:
    return {
        "install_id": install_id,
        "product_id": "factorio",
        "source": source,
        "ownership": ownership,
        "version": version,
        "channel": channel,
        "platform": platform_name,
        "executable": executable,
        "app_dir": app_dir,
        "capabilities": capabilities,
        "verification": verification,
    }

