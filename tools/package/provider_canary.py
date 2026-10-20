# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

"""Select one exact provider revision for non-adopted package custody."""

from __future__ import annotations

import re


def repaired_provider_canary_revisions(
    tracked_revisions: dict[str, str],
    provider_revision: str,
    *,
    provider_id: str = "universal_launcher",
) -> dict[str, str]:
    if provider_id not in {"universal_launcher", "universal_setup"}:
        raise ValueError("repaired-provider canary selects ULK or USK")
    label = "ULK" if provider_id == "universal_launcher" else "USK"
    revision = provider_revision.strip().lower()
    if re.fullmatch(r"[0-9a-f]{40}", revision) is None:
        raise ValueError(f"repaired-provider canary {label} revision must be an exact 40-character Git id")
    if revision == tracked_revisions[provider_id]:
        raise ValueError(f"repaired-provider canary {label} revision must differ from the tracked canonical pin")
    revisions = dict(tracked_revisions)
    revisions[provider_id] = revision
    return revisions


def select_provider_revisions(
    tracked_revisions: dict[str, str], ulk: str | None, usk: str | None
) -> tuple[dict[str, str], str]:
    if ulk is not None and usk is not None:
        raise ValueError("repaired-provider canary selects exactly one provider revision")
    if ulk is None and usk is None:
        return dict(tracked_revisions), "canonical"
    provider = "universal_launcher" if ulk is not None else "universal_setup"
    revision = ulk if ulk is not None else usk
    assert revision is not None
    return repaired_provider_canary_revisions(
        tracked_revisions, revision, provider_id=provider
    ), "repaired_provider_canary"
