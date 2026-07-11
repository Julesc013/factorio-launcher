from __future__ import annotations

from typing import Any


def allowed_dependencies(profile: dict[str, Any]) -> set[str]:
    proof = profile.get("proof", {})
    values = proof.get("allowed_system_dependencies", []) if isinstance(proof, dict) else []
    return {str(value) for value in values}
