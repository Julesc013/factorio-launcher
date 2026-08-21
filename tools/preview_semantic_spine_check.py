# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

"""Validate the non-authorizing Technical Preview semantic-spine fixture."""

from __future__ import annotations

import json
import sys
import tomllib
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
RECORD = ROOT / "release/index/preview_semantic_spine.v0.toml"
SCHEMA = ROOT / "contracts/schema/ui/facman.preview_semantic_spine.v0.schema.json"
FIXTURE = ROOT / "tests/fixtures/presentation/semantic-spine/walking-skeleton.v0.json"
PRESENTATION = ROOT / "contracts/schema/ui/facman.presentation.v0.schema.json"
RUN_CONTRACT = ROOT / "contracts/command/factorio/run.execute.v1.toml"

try:
    import jsonschema
except ModuleNotFoundError:
    jsonschema = None


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain an object")
    return value


def load_toml(path: Path) -> dict[str, Any]:
    with path.open("rb") as handle:
        return tomllib.load(handle)


def validate_fixture(fixture: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    steps = fixture.get("steps", [])
    expected_ids = [
        "workspace.open",
        "installation.discover",
        "installation.register",
        "instance.create-select",
        "readiness.compute",
        "launch-deck.render",
        "fixture-session.start",
        "fixture-session.observe",
        "last-run.inspect",
        "last-run.relaunch",
        "recovery.inspect",
    ]
    if [item.get("id") for item in steps] != expected_ids:
        problems.append("walking skeleton step sequence has drifted")
    revisions = [item.get("presentation_revision") for item in steps]
    if revisions != list(range(1, len(steps) + 1)):
        problems.append("walking skeleton revisions must be monotonic and gap-free")
    request_ids: list[str] = []
    idempotency_keys: list[str] = []
    for item in steps:
        action = item.get("action", {})
        request_ids.append(str(action.get("request_id")))
        key = action.get("idempotency_key")
        operation_id = action.get("durable_operation_id")
        if key is not None:
            idempotency_keys.append(str(key))
        if action.get("effect") in {"local_state", "fixture_process"}:
            if not key or not operation_id:
                problems.append(f"{item.get('id')}: effectful action lacks idempotency/operation identity")
        if action.get("production_command_dispatched") is not False:
            problems.append(f"{item.get('id')}: fixture dispatched a production command")
        if action.get("command_id") in {"run.execute", "setup.operation"}:
            problems.append(f"{item.get('id')}: forbidden production command in fixture")
    if len(request_ids) != len(set(request_ids)):
        problems.append("walking skeleton repeats a request_id")
    if len(idempotency_keys) != len(set(idempotency_keys)):
        problems.append("walking skeleton repeats an idempotency_key")
    return problems


def validate() -> list[str]:
    problems: list[str] = []
    record = load_toml(RECORD)
    schema = load_json(SCHEMA)
    fixture = load_json(FIXTURE)
    presentation = load_json(PRESENTATION)
    if jsonschema is not None:
        try:
            jsonschema.validators.validator_for(schema)(schema).validate(fixture)
        except jsonschema.ValidationError as exc:
            problems.append(f"semantic-spine fixture schema failure: {exc.message}")
    problems.extend(validate_fixture(fixture))
    if record.get("status") != "characterization_only":
        problems.append("semantic spine must remain characterization-only")
    for field in (
        "production_path_changed",
        "backend_presentation_service_implemented",
        "canonical_last_run_migrated",
        "canonical_readiness_migrated",
    ):
        if record.get(field) is not False:
            problems.append(f"semantic spine prematurely changes {field}")
    if record.get("fixture_walking_skeleton_implemented") is not True:
        problems.append("semantic spine must bind its engineering fixture")
    if any(value is not False for value in record.get("authority", {}).values()):
        problems.append("semantic spine grants authority")
    stop = record.get("stop_law", {})
    if stop.get("required_disposition") != "characterize_without_switching_production":
        problems.append("semantic spine stop law has drifted")
    if any(value is not False for key, value in stop.items() if key.endswith("_allowed")):
        problems.append("semantic spine permits split authority")
    frontends = record.get("current_frontend_projection", [])
    if [item.get("id") for item in frontends] != ["winforms", "appkit", "gtk"]:
        problems.append("semantic spine must characterize all production preview projections")
    retired_markers = {
        "winforms": ("SaveLastRunCache", "non_authoritative_view_copy"),
        "appkit": ("cacheKeyForWorkspace", "non_authoritative_view_copy"),
        "gtk": ("save_view_only_last_run", "non_authoritative_view_copy"),
    }
    for item in frontends:
        path = ROOT / str(item.get("path"))
        text = path.read_text(encoding="utf-8") if path.is_file() else ""
        for marker in retired_markers.get(str(item.get("id")), ()):
            if marker in text:
                problems.append(f"{item.get('id')} retains retired Last Run cache authority: {marker}")
    definitions = presentation.get("$defs", {})
    for view in record.get("views", []):
        if view not in definitions:
            problems.append(f"presentation contract is missing {view}")
    with RUN_CONTRACT.open("rb") as handle:
        run_contract = tomllib.load(handle)
    if run_contract.get("availability") != "unavailable_until_isolation_proof":
        problems.append("semantic-spine fixture changed real run.execute availability")
    return problems


def main() -> int:
    try:
        problems = validate()
    except (OSError, ValueError, tomllib.TOMLDecodeError) as exc:
        problems = [str(exc)]
    if problems:
        for problem in problems:
            print(f"preview-semantic-spine-check: {problem}", file=sys.stderr)
        return 1
    print("preview-semantic-spine-check: ok (characterization only; 11 fixture steps)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
