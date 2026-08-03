#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

"""Emit live checkout/provider truth without writing it into tracked source."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tomllib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "facman.current_checkout_observation.v1"
OUTPUT_STEM = "current-checkout-observation.v1"
SHA_PATTERN = re.compile(r"[0-9a-f]{40}")
ABI_PATTERN = re.compile(
    r"^\s*#\s*define\s+([A-Z][A-Z0-9_]*)_API_VERSION_(MAJOR|MINOR)\s+([0-9]+)\b",
    re.MULTILINE,
)
REQUIRED_PROVIDER_IDS = {"universal_launcher", "universal_setup"}
REQUIRED_ABI_IDS = {
    "universal_launcher": {"ulk", "ulu"},
    "universal_setup": {"usk", "usu"},
}


def _run_git(
    root: Path,
    *args: str,
    trust_root: bool = False,
) -> subprocess.CompletedProcess[str]:
    environment = {
        key: value
        for key, value in os.environ.items()
        if not key.upper().startswith("GIT_")
    }
    environment.update(
        {
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_NO_REPLACE_OBJECTS": "1",
            "GIT_OPTIONAL_LOCKS": "0",
        }
    )
    command = [
        "git",
        "--no-optional-locks",
        "-c",
        "core.fsmonitor=false",
        "-c",
        "core.useReplaceRefs=false",
        "-c",
        "core.ignoreStat=false",
    ]
    if trust_root:
        command.extend(["-c", f"safe.directory={root}"])
    command.extend(args)
    return subprocess.run(
        command,
        cwd=root,
        env=environment,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def _git_text(root: Path, *args: str, trust_root: bool = False) -> str | None:
    completed = _run_git(root, *args, trust_root=trust_root)
    if completed.returncode != 0:
        return None
    return completed.stdout.strip()


def _observe_checkout(
    root: Path,
    label: str,
    *,
    trust_root: bool = False,
) -> tuple[dict[str, Any], list[str]]:
    problems: list[str] = []
    resolved = root.resolve()
    observation: dict[str, Any] = {
        "root": str(resolved),
        "head": None,
        "branch": None,
        "detached": None,
        "dirty": None,
        "index_flags_clean": None,
    }
    if not resolved.is_dir():
        problems.append(f"{label}: repository root does not exist: {resolved}")
        return observation, problems

    head = _git_text(
        resolved,
        "rev-parse",
        "--verify",
        "HEAD^{commit}",
        trust_root=trust_root,
    )
    if head is None or SHA_PATTERN.fullmatch(head) is None:
        problems.append(f"{label}: cannot resolve an exact Git HEAD")
    else:
        observation["head"] = head

    branch = _git_text(
        resolved,
        "symbolic-ref",
        "--quiet",
        "--short",
        "HEAD",
        trust_root=trust_root,
    )
    observation["branch"] = branch or None
    observation["detached"] = branch is None

    status = _git_text(
        resolved,
        "status",
        "--porcelain=v1",
        "--untracked-files=normal",
        trust_root=trust_root,
    )
    if status is None:
        problems.append(f"{label}: cannot inspect worktree cleanliness")
    else:
        observation["dirty"] = bool(status)
    index_entries = _git_text(resolved, "ls-files", "-v", trust_root=trust_root)
    if index_entries is None:
        problems.append(f"{label}: cannot inspect index flags")
    else:
        special_entries = [
            line for line in index_entries.splitlines() if line and line[0] != "H"
        ]
        observation["index_flags_clean"] = not special_entries
        if special_entries:
            problems.append(
                f"{label}: index contains assume-unchanged, skip-worktree, or "
                "nonstandard entries"
            )
    return observation, problems


def _normalize_remote(value: str, repository_root: Path) -> str:
    candidate = value.strip().replace("\\", "/")
    if not candidate:
        return ""
    if re.match(r"^[A-Za-z]:/", candidate) or candidate.startswith(("/", "./", "../")):
        path = Path(candidate)
        if not path.is_absolute():
            path = repository_root / path
        return os.path.normcase(str(path.resolve())).replace("\\", "/").rstrip("/")
    if re.match(r"^[^/@:]+@[^/:]+:", candidate):
        user_host, path = candidate.split(":", 1)
        candidate = f"ssh://{user_host}/{path}"
    parts = urlsplit(candidate)
    if parts.scheme:
        normalized_path = parts.path.rstrip("/")
        if normalized_path.endswith(".git"):
            normalized_path = normalized_path[:-4]
        return urlunsplit(
            (
                parts.scheme.lower(),
                parts.netloc.rsplit("@", 1)[-1].lower(),
                normalized_path,
                "",
                "",
            )
        )
    return candidate.rstrip("/")


def _redact_remote(value: str) -> str:
    candidate = value.strip()
    if re.match(r"^[^/@:]+@[^/:]+:", candidate):
        return candidate.split("@", 1)[1]
    if re.match(r"^[A-Za-z][A-Za-z0-9+.-]*://", candidate):
        parts = urlsplit(candidate)
        return urlunsplit(
            (
                parts.scheme,
                parts.netloc.rsplit("@", 1)[-1],
                parts.path,
                "",
                "",
            )
        )
    return candidate


def _discover_abi_versions(
    root: Path,
    label: str,
    revision: str,
    *,
    trust_root: bool = False,
) -> tuple[list[dict[str, Any]], list[str]]:
    values: dict[str, dict[str, int]] = {}
    sources: dict[str, set[str]] = {}
    problems: list[str] = []
    tree = _git_text(
        root,
        "ls-tree",
        "-r",
        "--name-only",
        revision,
        "--",
        "include",
        trust_root=trust_root,
    )
    if tree is None:
        return [], [f"{label}: cannot enumerate public headers from locked pin"]

    headers = sorted(
        item for item in tree.splitlines() if item.startswith("include/") and item.endswith(".h")
    )
    if not headers:
        return [], [f"{label}: locked pin has no public headers"]
    for header in headers:
        text = _git_text(
            root,
            "show",
            f"{revision}:{header}",
            trust_root=trust_root,
        )
        if text is None:
            problems.append(f"{label}: cannot read pinned ABI header {header}")
            continue
        for prefix, part, raw_value in ABI_PATTERN.findall(text):
            key = part.lower()
            value = int(raw_value)
            prior = values.setdefault(prefix, {}).get(key)
            if prior is not None and prior != value:
                problems.append(
                    f"{label}: conflicting {prefix} ABI {key} values {prior} and {value}"
                )
                continue
            values[prefix][key] = value
            sources.setdefault(prefix, set()).add(header)

    versions: list[dict[str, Any]] = []
    for prefix in sorted(values):
        parts = values[prefix]
        if "major" not in parts or "minor" not in parts:
            problems.append(f"{label}: incomplete {prefix} ABI version declaration")
            continue
        major = parts["major"]
        minor = parts["minor"]
        versions.append(
            {
                "id": prefix.lower(),
                "major": major,
                "minor": minor,
                "version": f"{major}.{minor}",
                "sources": sorted(sources[prefix]),
            }
        )
    if not versions:
        problems.append(f"{label}: no complete public ABI version declarations found")
    return versions, problems


def _provider_components(lock: dict[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
    problems: list[str] = []
    raw_components = lock.get("component")
    if not isinstance(raw_components, list):
        return [], ["workspace lock has no component array"]
    providers: list[dict[str, Any]] = []
    seen_provider_ids: set[str] = set()
    for raw in raw_components:
        if not isinstance(raw, dict):
            problems.append("workspace lock contains a non-table component")
            continue
        if not any(raw.get(key) for key in ("remote", "required_ref", "reachability")):
            continue
        component: dict[str, Any] = {
            key: str(raw.get(key, "")).strip()
            for key in (
                "id",
                "source",
                "pin",
                "remote",
                "required_ref",
                "reachability",
            )
        }
        validation_problems: list[str] = []
        label = component["id"] or "<unnamed>"
        if not component["id"]:
            validation_problems.append("workspace lock contains a provider without an id")
        if SHA_PATTERN.fullmatch(component["pin"]) is None:
            validation_problems.append(
                f"workspace lock provider {label} has no exact pin"
            )
        if not component["remote"]:
            validation_problems.append(
                f"workspace lock provider {label} has no declared remote"
            )
        if component["required_ref"] != "refs/heads/main":
            validation_problems.append(
                f"workspace lock provider {label} required_ref is not refs/heads/main"
            )
        if component["reachability"] != "required_for_source_closure":
            validation_problems.append(
                f"workspace lock provider {label} does not require source closure"
            )
        problems.extend(validation_problems)
        component["_validation_problems"] = validation_problems
        if component["id"]:
            if component["id"] in seen_provider_ids:
                duplicate_problem = (
                    f"workspace lock contains duplicate provider {component['id']}"
                )
                problems.append(duplicate_problem)
                component["_validation_problems"].append(duplicate_problem)
                for prior in providers:
                    if prior["id"] == component["id"]:
                        prior["_validation_problems"].append(duplicate_problem)
            seen_provider_ids.add(component["id"])
            providers.append(component)
    providers.sort(key=lambda item: item["id"])
    missing = REQUIRED_PROVIDER_IDS - {provider["id"] for provider in providers}
    for component_id in sorted(missing):
        problems.append(f"workspace lock is missing required provider {component_id}")
    return providers, problems


def _observe_provider(
    component: dict[str, Any],
    root: Path | None,
    *,
    trust_root: bool = False,
) -> tuple[dict[str, Any], list[str]]:
    component_id = component["id"]
    label = f"provider {component_id}"
    observation: dict[str, Any] = {
        "id": component_id,
        "source": component["source"],
        "pin": component["pin"],
        "declared_remote": _redact_remote(component["remote"]),
        "required_ref": component["required_ref"],
        "reachability_policy": component["reachability"],
        "canonical_remote_ref": None,
        "canonical_remote_head": None,
        "origin_remote": None,
        "remote_matches_lock": None,
        "checkout": {
            "root": str(root.resolve()) if root is not None else None,
            "head": None,
            "branch": None,
            "detached": None,
            "dirty": None,
            "index_flags_clean": None,
        },
        "pin_object_present": None,
        "pin_checkout": None,
        "pin_reachable_from_canonical_ref": None,
        "abi_source_revision": component["pin"],
        "abi_versions": [],
        "status": "fail",
    }
    problems = list(component.get("_validation_problems", []))
    if root is None:
        problems.append(f"{label}: no sibling root was passed")
        return observation, problems

    resolved = root.resolve()
    checkout, checkout_problems = _observe_checkout(
        resolved,
        label,
        trust_root=trust_root,
    )
    observation["checkout"] = checkout
    problems.extend(checkout_problems)
    if not resolved.is_dir():
        return observation, problems

    origin_remote = _git_text(
        resolved,
        "config",
        "--local",
        "--no-includes",
        "--get",
        "remote.origin.url",
        trust_root=trust_root,
    )
    observation["origin_remote"] = (
        _redact_remote(origin_remote) if origin_remote is not None else None
    )
    if origin_remote is None:
        problems.append(f"{label}: cannot resolve origin remote")
    else:
        remote_matches = _normalize_remote(
            origin_remote, resolved
        ) == _normalize_remote(component["remote"], resolved)
        observation["remote_matches_lock"] = remote_matches
        if not remote_matches:
            problems.append(f"{label}: origin remote does not match the workspace lock")

    pin = component["pin"]
    pin_object = _run_git(
        resolved,
        "cat-file",
        "-e",
        f"{pin}^{{commit}}",
        trust_root=trust_root,
    )
    pin_present = pin_object.returncode == 0
    observation["pin_object_present"] = pin_present
    if not pin_present:
        problems.append(f"{label}: locked pin is not present in the sibling repository")

    head = checkout.get("head")
    pin_checkout = head == pin if head is not None else False
    observation["pin_checkout"] = pin_checkout
    if not pin_checkout:
        problems.append(f"{label}: checkout HEAD does not equal the locked pin")
    if checkout.get("dirty") is True:
        problems.append(f"{label}: checkout is dirty")

    required_ref = component["required_ref"]
    canonical_ref: str | None = None
    if required_ref.startswith("refs/heads/"):
        canonical_ref = "refs/remotes/origin/" + required_ref.removeprefix("refs/heads/")
        observation["canonical_remote_ref"] = canonical_ref
        canonical_head = _git_text(
            resolved,
            "rev-parse",
            "--verify",
            f"{canonical_ref}^{{commit}}",
            trust_root=trust_root,
        )
        observation["canonical_remote_head"] = canonical_head
        if canonical_head is None:
            problems.append(f"{label}: canonical remote-tracking ref is unavailable")
        elif pin_present:
            reachable = _run_git(
                resolved,
                "merge-base",
                "--is-ancestor",
                pin,
                canonical_ref,
                trust_root=trust_root,
            ).returncode == 0
            observation["pin_reachable_from_canonical_ref"] = reachable
            if not reachable:
                problems.append(f"{label}: locked pin is not reachable from canonical origin/main")

    if pin_present:
        abi_versions, abi_problems = _discover_abi_versions(
            resolved,
            label,
            pin,
            trust_root=trust_root,
        )
    else:
        abi_versions = []
        abi_problems = [f"{label}: cannot inspect ABI declarations without locked pin"]
    observation["abi_versions"] = abi_versions
    problems.extend(abi_problems)
    missing_abis = REQUIRED_ABI_IDS.get(component_id, set()) - {
        abi["id"] for abi in abi_versions
    }
    for abi_id in sorted(missing_abis):
        problems.append(f"{label}: required public ABI {abi_id} is not declared")
    observation["status"] = "pass" if not problems else "fail"
    return observation, problems


def collect_observation(
    repository_root: Path,
    workspace_lock: Path,
    provider_roots: dict[str, Path],
    *,
    expected_source_sha: str | None = None,
    observed_at_utc: str | None = None,
    trust_passed_roots: bool = False,
) -> dict[str, Any]:
    repository_root = repository_root.resolve()
    workspace_lock = workspace_lock.resolve()
    problems: list[str] = []

    source, source_problems = _observe_checkout(
        repository_root,
        "factorio-launcher",
        trust_root=trust_passed_roots,
    )
    problems.extend(source_problems)
    expected = expected_source_sha.strip().lower() if expected_source_sha else None
    expected_match: bool | None = None
    if expected is not None:
        if SHA_PATTERN.fullmatch(expected) is None:
            problems.append("factorio-launcher: expected CI SHA is not an exact Git revision")
            expected_match = False
        else:
            expected_match = source.get("head") == expected
            if not expected_match:
                problems.append("factorio-launcher: checkout HEAD does not match expected CI SHA")
    if source.get("dirty") is True:
        problems.append("factorio-launcher: checkout is dirty")
    source["expected_ci_sha"] = expected
    source["expected_ci_sha_match"] = expected_match

    lock_data: dict[str, Any] = {}
    lock_digest: str | None = None
    if not workspace_lock.is_file():
        problems.append(f"workspace lock is missing: {workspace_lock}")
    else:
        try:
            lock_bytes = workspace_lock.read_bytes()
            lock_data = tomllib.loads(lock_bytes.decode("utf-8"))
            lock_digest = hashlib.sha256(lock_bytes).hexdigest()
            if lock_data.get("schema") != "flaunch.workspace_lock.v1":
                problems.append("workspace lock has the wrong schema")
        except (OSError, UnicodeError, tomllib.TOMLDecodeError) as exc:
            problems.append(f"cannot read workspace lock: {exc}")

    components, component_problems = _provider_components(lock_data)
    problems.extend(component_problems)
    declared_ids = {component["id"] for component in components}
    for component_id in sorted(set(provider_roots) - declared_ids):
        problems.append(f"provider root was passed for undeclared component {component_id}")

    providers = []
    for component in components:
        provider, provider_problems = _observe_provider(
            component,
            provider_roots.get(component["id"]),
            trust_root=trust_passed_roots,
        )
        providers.append(provider)
        problems.extend(provider_problems)

    observed_at = observed_at_utc or datetime.now(timezone.utc).isoformat(
        timespec="seconds"
    ).replace("+00:00", "Z")
    unique_problems = list(dict.fromkeys(problems))
    return {
        "schema": SCHEMA,
        "observed_at_utc": observed_at,
        "git_ownership_mode": (
            "explicit_exact_roots" if trust_passed_roots else "owner_verified"
        ),
        "source": source,
        "workspace_lock": {
            "path": str(workspace_lock),
            "schema": lock_data.get("schema") if lock_data else None,
            "sha256": lock_digest,
        },
        "providers": providers,
        "result": {
            "status": "pass" if not unique_problems else "fail",
            "problem_count": len(unique_problems),
            "problems": unique_problems,
        },
    }


def canonical_json(observation: dict[str, Any]) -> str:
    return json.dumps(
        observation,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ) + "\n"


def _display(value: Any) -> str:
    if value is None:
        return "unknown"
    if isinstance(value, bool):
        return str(value).lower()
    return str(value).replace("|", "\\|").replace("\n", " ")


def markdown(observation: dict[str, Any]) -> str:
    source = observation["source"]
    lock = observation["workspace_lock"]
    result = observation["result"]
    lines = [
        "# Current checkout and provider observation",
        "",
        f"- Schema: `{observation['schema']}`",
        f"- Observed at: `{observation['observed_at_utc']}`",
        f"- Git ownership mode: `{observation['git_ownership_mode']}`",
        f"- Overall status: **{result['status']}**",
        "",
        "This file is generated after checkout. It is not tracked project-state truth and",
        "does not grant execution, mutation, signing, publication, or route authority.",
        "",
        "## FacMan checkout",
        "",
        "| Root | HEAD | Branch | Detached | Dirty | Expected CI SHA | Match |",
        "| --- | --- | --- | --- | --- | --- | --- |",
        f"| `{_display(source['root'])}` | `{_display(source['head'])}` | "
        f"`{_display(source['branch'])}` | {_display(source['detached'])} | "
        f"{_display(source['dirty'])} | `{_display(source['expected_ci_sha'])}` | "
        f"{_display(source['expected_ci_sha_match'])} |",
        "",
        "## Workspace lock",
        "",
        f"- Path: `{_display(lock['path'])}`",
        f"- Schema: `{_display(lock['schema'])}`",
        f"- SHA-256: `{_display(lock['sha256'])}`",
        "",
        "## Providers",
        "",
    ]
    for provider in observation["providers"]:
        checkout = provider["checkout"]
        lines.extend(
            [
                f"### {provider['id']}",
                "",
                f"- Status: **{provider['status']}**",
                f"- Consumed pin: `{_display(provider['pin'])}`",
                f"- Checkout HEAD: `{_display(checkout['head'])}`",
                f"- Checkout pin match: `{_display(provider['pin_checkout'])}`",
                f"- Checkout dirty: `{_display(checkout['dirty'])}`",
                f"- Declared remote: `{_display(provider['declared_remote'])}`",
                f"- Observed origin: `{_display(provider['origin_remote'])}`",
                f"- Remote matches lock: `{_display(provider['remote_matches_lock'])}`",
                f"- Canonical ref: `{_display(provider['canonical_remote_ref'])}`",
                f"- Canonical ref HEAD: `{_display(provider['canonical_remote_head'])}`",
                "- Pin reachable from canonical ref: "
                f"`{_display(provider['pin_reachable_from_canonical_ref'])}`",
                f"- ABI source revision: `{_display(provider['abi_source_revision'])}`",
                "",
                "| ABI | Version | Declaration source |",
                "| --- | --- | --- |",
            ]
        )
        if provider["abi_versions"]:
            for abi in provider["abi_versions"]:
                lines.append(
                    f"| `{abi['id']}` | `{abi['version']}` | "
                    f"`{', '.join(abi['sources'])}` |"
                )
        else:
            lines.append("| unknown | unknown | unavailable |")
        lines.append("")

    lines.extend(["## Problems", ""])
    if result["problems"]:
        lines.extend(f"- {problem}" for problem in result["problems"])
    else:
        lines.append("- None.")
    lines.append("")
    return "\n".join(lines)


def _parse_provider_roots(
    values: list[str],
    base: Path,
) -> tuple[dict[str, Path], list[str]]:
    roots: dict[str, Path] = {}
    problems: list[str] = []
    for value in values:
        component_id, separator, raw_path = value.partition("=")
        component_id = component_id.strip()
        raw_path = raw_path.strip()
        if not separator or not component_id or not raw_path:
            problems.append(f"invalid --provider-root value: {value!r}; expected ID=PATH")
            continue
        if component_id in roots:
            problems.append(f"duplicate --provider-root component: {component_id}")
            continue
        path = Path(raw_path)
        roots[component_id] = (
            (base / path).resolve() if not path.is_absolute() else path.resolve()
        )
    return roots, problems


def _is_within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate versioned live checkout/provider observation artifacts."
    )
    parser.add_argument("--repository-root", default=str(ROOT))
    parser.add_argument(
        "--workspace-lock",
        default="release/index/workspace_lock.v1.toml",
    )
    parser.add_argument(
        "--provider-root",
        action="append",
        default=[],
        metavar="ID=PATH",
        help="Passed sibling root; repeat once for each provider in the workspace lock.",
    )
    parser.add_argument(
        "--expected-source-sha",
        default=os.environ.get("FACMAN_CI_SOURCE_SHA"),
    )
    parser.add_argument("--output-dir", required=True)
    parser.add_argument(
        "--trust-passed-roots",
        action="store_true",
        help=(
            "Explicitly trust only the passed source/provider roots when Git "
            "reports a different filesystem owner; recorded in the artifact."
        ),
    )
    args = parser.parse_args(argv)

    repository_root = Path(args.repository_root).resolve()
    workspace_lock = Path(args.workspace_lock)
    if not workspace_lock.is_absolute():
        workspace_lock = repository_root / workspace_lock
    output_dir = Path(args.output_dir).resolve()
    provider_roots, parse_problems = _parse_provider_roots(
        args.provider_root,
        repository_root,
    )
    if parse_problems:
        for problem in parse_problems:
            print(f"current-checkout-observation: {problem}", file=sys.stderr)
        return 2
    if _is_within(output_dir, repository_root):
        print(
            "current-checkout-observation: --output-dir must be outside the source checkout",
            file=sys.stderr,
        )
        return 2

    observation = collect_observation(
        repository_root,
        workspace_lock,
        provider_roots,
        expected_source_sha=args.expected_source_sha,
        trust_passed_roots=args.trust_passed_roots,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"{OUTPUT_STEM}.json"
    markdown_path = output_dir / f"{OUTPUT_STEM}.md"
    json_path.write_text(canonical_json(observation), encoding="utf-8")
    markdown_path.write_text(markdown(observation), encoding="utf-8")
    print(f"current-checkout-observation: wrote {json_path}")
    print(f"current-checkout-observation: wrote {markdown_path}")
    if observation["result"]["status"] != "pass":
        for problem in observation["result"]["problems"]:
            print(f"current-checkout-observation: {problem}", file=sys.stderr)
        return 1
    print("current-checkout-observation: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
