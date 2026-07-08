from __future__ import annotations

SECRET_WORDS = ("token", "password", "secret", "session", "rcon_password")


def redact_mapping(data: dict[str, object]) -> dict[str, object]:
    redacted: dict[str, object] = {}
    for key, value in data.items():
        if any(word in key.lower() for word in SECRET_WORDS):
            redacted[key] = "[REDACTED]"
        else:
            redacted[key] = value
    return redacted

