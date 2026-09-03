# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

"""Load stable repository roles without conflating them with mutable slugs."""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "release/index/repository_identity.v1.toml"
SCHEMA = "facman.repository_identity.v1"
EXPECTED_ROLES = {"facman", "universal_launcher", "universal_setup"}
SLUG = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


def _github_slug(value: str) -> str | None:
    candidate = value.strip().replace("\\", "/")
    if re.match(r"^[^/@:]+@[^/:]+:", candidate):
        host_path = candidate.split("@", 1)[1]
        host, _, path = host_path.partition(":")
        if host.casefold() != "github.com":
            return None
        candidate = path
    elif "://" in candidate:
        parsed = urlsplit(candidate)
        if parsed.scheme not in {"https", "ssh"} or parsed.hostname != "github.com":
            return None
        candidate = parsed.path
    candidate = candidate.strip("/")
    if candidate.casefold().endswith(".git"):
        candidate = candidate[:-4]
    if SLUG.fullmatch(candidate) is None:
        return None
    return candidate.casefold()


@dataclass(frozen=True)
class RepositoryIdentity:
    role: str
    github_repository_id: int
    canonical_slug: str
    canonical_https_remote: str
    legacy_slugs: tuple[str, ...]
    product_name: str | None
    preferred_future_slug: str | None
    rename_status: str | None
    slug_status: str | None
    freeze_through: str | None
    rename_authorized: bool | None
    future_slug_candidate: str | None
    future_slug_candidate_is_current_plan: bool | None
    workspace_names: tuple[str, ...]

    @property
    def legacy_https_remotes(self) -> tuple[str, ...]:
        return tuple(f"https://github.com/{slug}.git" for slug in self.legacy_slugs)

    @property
    def preferred_future_https_remote(self) -> str | None:
        if self.preferred_future_slug is None:
            return None
        return f"https://github.com/{self.preferred_future_slug}.git"

    def classifies_slug(self, slug: str) -> str | None:
        if slug == self.canonical_slug:
            return "canonical"
        if slug in self.legacy_slugs:
            return "legacy_redirect"
        if slug == self.preferred_future_slug:
            return "deferred_future"
        return None

    def classifies_remote(self, remote: str) -> str | None:
        slug = _github_slug(remote)
        if slug == self.canonical_slug.casefold():
            return "canonical"
        if slug in {legacy.casefold() for legacy in self.legacy_slugs}:
            return "legacy_redirect"
        if (
            self.preferred_future_slug is not None
            and slug == self.preferred_future_slug.casefold()
        ):
            return "deferred_future"
        return None


def _remote_for(row: dict[str, object]) -> str:
    explicit = row.get("canonical_https_remote")
    if isinstance(explicit, str):
        return explicit
    return f"https://github.com/{row.get('canonical_slug', '')}.git"


def load(path: Path = MANIFEST) -> dict[str, RepositoryIdentity]:
    with path.open("rb") as handle:
        document = tomllib.load(handle)
    if document.get("schema") != SCHEMA:
        raise ValueError(f"repository identity schema must be {SCHEMA}")
    rows = document.get("repository")
    if not isinstance(rows, list):
        raise ValueError("repository identity manifest must contain repository rows")
    identities: dict[str, RepositoryIdentity] = {}
    numeric_ids: set[int] = set()
    for raw in rows:
        if not isinstance(raw, dict):
            raise ValueError("repository identity rows must be tables")
        role = raw.get("role")
        repository_id = raw.get("github_repository_id")
        slug = raw.get("canonical_slug")
        remote = _remote_for(raw)
        legacy = raw.get("legacy_slugs")
        product_name = raw.get("product_name")
        preferred_future_slug = raw.get("preferred_future_slug")
        rename_status = raw.get("rename_status")
        slug_status = raw.get("slug_status", rename_status)
        freeze_through = raw.get("freeze_through")
        rename_authorized = raw.get("rename_authorized")
        future_slug_candidate = raw.get(
            "future_slug_candidate", preferred_future_slug
        )
        future_slug_candidate_is_current_plan = raw.get(
            "future_slug_candidate_is_current_plan"
        )
        workspace = raw.get("workspace_names")
        if not isinstance(role, str) or role in identities:
            raise ValueError("repository roles must be unique strings")
        if not isinstance(repository_id, int) or repository_id <= 0 or repository_id in numeric_ids:
            raise ValueError(f"{role}: GitHub repository ID must be a unique positive integer")
        if not isinstance(slug, str) or SLUG.fullmatch(slug) is None:
            raise ValueError(f"{role}: canonical slug is invalid")
        if remote != f"https://github.com/{slug}.git":
            raise ValueError(f"{role}: canonical HTTPS remote differs from canonical slug")
        if not isinstance(legacy, list) or not all(isinstance(item, str) and SLUG.fullmatch(item) for item in legacy):
            raise ValueError(f"{role}: legacy slugs must be valid slug strings")
        if slug in legacy or len(set(legacy)) != len(legacy):
            raise ValueError(f"{role}: canonical and legacy slugs must remain distinct")
        if product_name is not None and (not isinstance(product_name, str) or not product_name.strip()):
            raise ValueError(f"{role}: product name must be a non-empty string")
        if preferred_future_slug is not None and (
            not isinstance(preferred_future_slug, str)
            or SLUG.fullmatch(preferred_future_slug) is None
        ):
            raise ValueError(f"{role}: preferred future slug is invalid")
        if preferred_future_slug is not None and (
            preferred_future_slug == slug or preferred_future_slug in legacy
        ):
            raise ValueError(
                f"{role}: canonical, legacy, and preferred future slugs must remain distinct"
            )
        if rename_status is not None and (
            not isinstance(rename_status, str) or not rename_status.strip()
        ):
            raise ValueError(f"{role}: rename status must be a non-empty string")
        if slug_status is not None and (
            not isinstance(slug_status, str) or not slug_status.strip()
        ):
            raise ValueError(f"{role}: slug status must be a non-empty string")
        if rename_status is not None and slug_status != rename_status:
            raise ValueError(f"{role}: compatibility and canonical slug status differ")
        if future_slug_candidate != preferred_future_slug:
            raise ValueError(f"{role}: compatibility and canonical future slug differ")
        if freeze_through is not None and (
            not isinstance(freeze_through, str) or not freeze_through.strip()
        ):
            raise ValueError(f"{role}: freeze boundary must be a non-empty string")
        for name, value in (
            ("rename_authorized", rename_authorized),
            (
                "future_slug_candidate_is_current_plan",
                future_slug_candidate_is_current_plan,
            ),
        ):
            if value is not None and not isinstance(value, bool):
                raise ValueError(f"{role}: {name} must be boolean")
        if role == "facman":
            expected_freeze = "0.1.0_publication_and_post_release_review"
            if slug_status != "frozen_for_0_1_release_train":
                raise ValueError("facman: canonical slug must be frozen for 0.1")
            if freeze_through != expected_freeze:
                raise ValueError(f"facman: freeze boundary must be {expected_freeze}")
            if rename_authorized is not False:
                raise ValueError("facman: rename must remain unauthorized")
            if future_slug_candidate_is_current_plan is not False:
                raise ValueError("facman: future slug cannot be the current plan")
        if not isinstance(workspace, list) or not workspace or not all(
            isinstance(item, str) and item and "/" not in item and "\\" not in item
            for item in workspace
        ):
            raise ValueError(f"{role}: workspace names must be non-empty directory names")
        if len(set(workspace)) != len(workspace):
            raise ValueError(f"{role}: workspace names must be unique")
        identities[role] = RepositoryIdentity(
            role=role,
            github_repository_id=repository_id,
            canonical_slug=slug,
            canonical_https_remote=remote,
            legacy_slugs=tuple(legacy),
            product_name=product_name,
            preferred_future_slug=preferred_future_slug,
            rename_status=rename_status,
            slug_status=slug_status,
            freeze_through=freeze_through,
            rename_authorized=rename_authorized,
            future_slug_candidate=future_slug_candidate,
            future_slug_candidate_is_current_plan=(
                future_slug_candidate_is_current_plan
            ),
            workspace_names=tuple(workspace),
        )
        numeric_ids.add(repository_id)
    if set(identities) != EXPECTED_ROLES:
        raise ValueError(f"repository identity roles must be {sorted(EXPECTED_ROLES)}")
    return identities


def identity(role: str) -> RepositoryIdentity:
    try:
        return load()[role]
    except KeyError as exc:
        raise ValueError(f"unknown repository role: {role}") from exc


def validate(path: Path = MANIFEST) -> list[str]:
    try:
        load(path)
    except (OSError, ValueError, tomllib.TOMLDecodeError) as exc:
        return [str(exc)]
    return []


def main() -> int:
    problems = validate()
    for problem in problems:
        print(f"repository-identity: {problem}")
    if problems:
        return 1
    print("repository-identity: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
