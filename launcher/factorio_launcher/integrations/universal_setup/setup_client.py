from __future__ import annotations


class SetupMutationDisabled(RuntimeError):
    """Raised when an install mutation is requested before setup integration."""


def require_setup_integration(action: str) -> None:
    raise SetupMutationDisabled(
        f"{action} is disabled: managed install mutation belongs to universal setup"
    )

