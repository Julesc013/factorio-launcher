# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

"""Read-only laboratory inventory, scenario coverage and run-input custody."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import stat
import sys
import tomllib
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
REGISTRY = Path("release/index/lab_input_registry.v1.json")
SHA = re.compile(r"[0-9a-f]{64}")
OID = re.compile(r"[0-9a-f]{40}")
PLATFORMS = ("windows_x64", "linux_x64", "macos_intel_x64")
KINDS = ("machine_fixture", "real_game", "human_experience")


class Invalid(ValueError):
    """A record is incomplete, stale, ambiguous or outside its declared scope."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise Invalid(message)


def fields(value: Any, names: str) -> None:
    require(isinstance(value, dict) and set(value) == set(names.split()),
            "unexpected or missing record fields")


def text(value: Any) -> None:
    require(isinstance(value, str) and 0 < len(value) <= 4096, "nonempty bounded text required")


def identity(value: Any, pattern: re.Pattern[str] = SHA) -> None:
    require(isinstance(value, str) and pattern.fullmatch(value) is not None,
            "invalid content identity")


def parse_json(raw: bytes) -> dict[str, Any]:
    require(len(raw) <= 2 * 1024 * 1024, "registry/receipt byte budget exceeded")
    def unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            require(key not in result, "duplicate JSON field")
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=unique)


def load(path: Path) -> dict[str, Any]:
    with path.open("rb") as stream:
        return parse_json(stream.read(2 * 1024 * 1024 + 1))


def source_path(root: Path, relative: Any) -> Path:
    text(relative)
    require(not any(part in ("", ".", "..") for part in relative.split("/"))
            and not any(char in relative for char in "\\:\0"), "unsafe repository evidence path")
    path = root / relative
    require(not Path(relative).is_absolute() and path.resolve().is_relative_to(root.resolve()),
            "repository evidence escaped root")
    return path


def semantic_value(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                    ensure_ascii=True).encode()).hexdigest()


def source_value(path: Path) -> Any:
    with path.open("rb") as stream:
        raw = stream.read(2 * 1024 * 1024 + 1)
    require(len(raw) <= 2 * 1024 * 1024, "source byte budget exceeded")
    return tomllib.loads(raw.decode("utf-8")) if path.suffix == ".toml" else parse_json(raw)


def semantic_digest(path: Path) -> str:
    return semantic_value(source_value(path))


def validate(document: dict[str, Any], root: Path = ROOT) -> None:
    fields(document, "schema execution_authorized qualification_granted source_refs hosts inputs coverage run_requirements")
    require(document["schema"] == "facman.lab_input_registry.v1", "unknown laboratory registry")
    require(document["execution_authorized"] is False and document["qualification_granted"] is False,
            "registry cannot grant execution or qualification")
    refs = document["source_refs"]
    fields(refs, "journeys corpus hosts")
    expected = {"journeys": "release/index/foundation_beta_readiness.v1.toml",
                "corpus": "tests/fixtures/cross-frontend-journeys/corpus.v1.json"}
    snapshots = {}
    for name, ref in refs.items():
        fields(ref, "path semantic_sha256")
        identity(ref["semantic_sha256"])
        if name in expected:
            require(ref["path"] == expected[name], "canonical scenario source changed")
        snapshots[name] = source_value(source_path(root, ref["path"]))
        require(semantic_value(snapshots[name]) == ref["semantic_sha256"],
                f"{name} source drift invalidates registry")
    observation = snapshots["hosts"]
    require(observation.get("schema") == "facman.lab-host-observation.v1", "wrong host observation schema")
    hosts = document["hosts"]
    require(isinstance(hosts, list) and len(hosts) == 3, "one declared host slot per required platform")
    require({host.get("platform") for host in hosts if isinstance(host, dict)} == set(PLATFORMS),
            "required platform coverage differs")
    ids = set()
    for host in hosts:
        fields(host, "id platform environment identity availability capabilities limitations blocker owner")
        text(host["id"])
        require(host["id"] not in ids, "duplicate host identity")
        ids.add(host["id"])
        require(host["availability"] in ("observed", "unavailable"), "invalid host availability")
        text(host["environment"])
        text(host["owner"])
        require(isinstance(host["limitations"], list) and bool(host["limitations"]), "host limitations required")
        for limitation in host["limitations"]:
            text(limitation)
        require(isinstance(host["capabilities"], list) and
                len(set(host["capabilities"])) == len(host["capabilities"]) and
                set(host["capabilities"]) <= set(KINDS), "invalid host claim classes")
        if host["availability"] == "observed":
            text(host["identity"])
            if host["platform"] == "windows_x64":
                require(host["identity"] == observation["windows"]["hostname"] and
                        host["environment"] == observation["windows"]["os"], "Windows host observation mismatch")
            elif host["platform"] == "linux_x64":
                wsl = observation["linux_wsl"]
                require(all(row["exit_code"] == 0 for row in wsl.values()) and
                        host["identity"] == wsl["identity"]["output"] and
                        host["environment"] == "WSL2 / " + wsl["kernel"]["output"], "WSL host observation mismatch")
            else:
                raise Invalid("macOS inventory needs its own named host observation adapter")
            require(host["blocker"] is None, "observed inventory carries an availability blocker")
        else:
            require(host["identity"] is None and host["capabilities"] == [], "unavailable host has capabilities")
            text(host["blocker"])
    inputs = document["inputs"]
    fields(inputs, "fixture approved_game")
    require(inputs["fixture"] == refs["corpus"], "fixture input must bind the actual corpus")
    games = inputs["approved_game"]
    fields(games, " ".join(PLATFORMS))
    for game_platform, game in games.items():
        fields(game, "status digest approval_ref blocker owner")
        require(game["status"] in ("unavailable", "registered"), "invalid game custody status")
        text(game["owner"])
        if game["status"] == "unavailable":
            require(game["digest"] is None and game["approval_ref"] is None, "unavailable input has invented custody")
            text(game["blocker"])
        else:
            identity(game["digest"])
            fields(game["approval_ref"], "path semantic_sha256")
            ref = game["approval_ref"]
            approval = load(source_path(root, ref["path"]))
            require(semantic_value(approval) == ref["semantic_sha256"], "game approval evidence drift")
            fields(approval, "schema platform input_sha256 issuer scope")
            require(approval["schema"] == "facman.lab-input-approval.v1" and
                    approval["platform"] == game_platform and
                    approval["input_sha256"] == game["digest"] and
                    approval["scope"] == "input_custody_only", "approval does not bind game input custody")
            text(approval["issuer"])
            require(game["blocker"] is None, "registered game input remains blocked")
    coverage = document["coverage"]
    fields(coverage, "journeys fixture_scenarios platforms classes real_game_journeys")
    from tools.foundation_beta_readiness_check import JOURNEY_IDS
    from tools.cross_frontend_journey_conformance import REQUIRED_SCENARIOS
    require(coverage["journeys"] == JOURNEY_IDS and coverage["fixture_scenarios"] == list(REQUIRED_SCENARIOS),
            "scenario census is incomplete or reordered")
    require(coverage["platforms"] == list(PLATFORMS) and coverage["classes"] == list(KINDS), "qualification axes differ")
    require(coverage["real_game_journeys"] == JOURNEY_IDS[7:10], "Play/readiness/recovery input coverage differs")
    require(document["run_requirements"] == ["exact_source_and_package", "fresh_host_observation", "owned_roots",
            "allowed_effects", "reset_and_export", "approved_input", "independent_outcome"], "run custody requirements differ")


def matrix(document: dict[str, Any]) -> list[dict[str, Any]]:
    """Produce obligations, never outcomes or an executable permission record."""
    rows = []
    coverage = document["coverage"]
    for host in document["hosts"]:
        for kind in KINDS:
            scenarios = (coverage["journeys"] + coverage["fixture_scenarios"] if kind == "machine_fixture" else
                         coverage["real_game_journeys"] if kind == "real_game" else coverage["journeys"])
            for scenario in scenarios:
                blockers = []
                if host["availability"] == "unavailable":
                    blockers.append(host["blocker"])
                if kind not in host["capabilities"]:
                    blockers.append(f"{host['owner']}: qualify this named host for {kind}")
                if (kind != "machine_fixture" and scenario in coverage["real_game_journeys"] and
                        document["inputs"]["approved_game"][host["platform"]]["status"] == "unavailable"):
                    blockers.append(document["inputs"]["approved_game"][host["platform"]]["blocker"])
                if kind == "human_experience":
                    blockers.append("Operator: record genuine experience on the exact final candidate")
                rows.append({"id": f"{host['platform']}/{kind}/{scenario}", "host": host["id"],
                             "platform": host["platform"], "kind": kind, "scenario": scenario,
                             "status": "blocked_external" if blockers else "fixture_preparation_available",
                             "blockers": blockers, "pending_run_custody": document["run_requirements"],
                             "execution_authorized": False, "qualified": False})
    return rows


def _inspect_file(path: Path, expected: str, capture_limit: int | None = None) -> tuple[dict[str, Any], bytes]:
    """Hash actual local bytes without executing or copying the input."""
    identity(expected)
    require(path.is_absolute(), "actual input path must be absolute")
    for part in (path, *path.parents):
        info = part.lstat()
        require(not stat.S_ISLNK(info.st_mode) and not getattr(info, "st_file_attributes", 0) & 0x400,
                "linked input custody requires a separate reviewed capture")
    digest = hashlib.sha256()
    captured = []
    maximum = capture_limit if capture_limit is not None else 4 * 1024**3
    with path.open("rb") as stream:
        import os
        before = os.fstat(stream.fileno())
        require(stat.S_ISREG(before.st_mode) and before.st_size <= maximum, "input kind or byte budget")
        total = 0
        for chunk in iter(lambda: stream.read(65536), b""):
            total += len(chunk)
            require(total <= maximum, "input grew beyond byte budget")
            if capture_limit is not None:
                captured.append(chunk)
            digest.update(chunk)
        after = os.fstat(stream.fileno())
        require((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) ==
                (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns), "input changed during inspection")
    require(digest.hexdigest() == expected, "actual input digest differs from approved bytes")
    receipt = {"sha256": expected, "bytes": before.st_size, "execution_authorized": False,
            "qualification_granted": False, "scope": "point-in-time content custody; revalidate before effects"}
    return receipt, b"".join(captured)


def inspect_file(path: Path, expected: str) -> dict[str, Any]:
    return _inspect_file(path, expected)[0]


def inspect_json(path: Path, expected: str) -> tuple[dict[str, Any], Any]:
    receipt, raw = _inspect_file(path, expected, 2 * 1024 * 1024)
    return receipt, parse_json(raw)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", nargs="?", default="check", choices=("check", "matrix", "inspect-input"))
    parser.add_argument("--registry", type=Path, default=ROOT / REGISTRY)
    parser.add_argument("--input", type=Path)
    parser.add_argument("--sha256")
    args = parser.parse_args(argv)
    try:
        document = load(args.registry)
        validate(document)
        if args.command == "matrix":
            print(json.dumps({"schema": "facman.lab-scenario-matrix.v1", "cells": matrix(document)}, indent=2))
        elif args.command == "inspect-input":
            require(args.input is not None and args.sha256 is not None, "input and approved SHA256 required")
            print(json.dumps(inspect_file(args.input, args.sha256), indent=2))
        else:
            print(f"lab-registry: ok ({len(matrix(document))} classified obligations; no qualification granted)")
        return 0
    except (Invalid, OSError, ValueError, TypeError, KeyError) as error:
        print(f"lab-registry: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
