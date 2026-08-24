# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import copy
import hashlib
import json
import sys
import tomllib
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    import jsonschema
except ModuleNotFoundError:  # pragma: no cover - strict CI installs the lock
    jsonschema = None

from tools import json_contract


PACKET = ROOT / "release/index/factorio_2_1_14_route_packet.v1.toml"
PACKET_SCHEMA = (
    ROOT / "contracts/schema/release/factorio_2_1_14_route_packet.v1.schema.json"
)
HUMAN_TEMPLATE = (
    ROOT
    / "docs/quality/evidence/"
    "factorio_2_1_14_human_test_receipt.template.v1.json"
)
HUMAN_SCHEMA = ROOT / "contracts/schema/release/human_test_receipt.v1.schema.json"
ENGINEERING_DECISION = ROOT / "release/index/factorio_route_version_decision.v1.toml"
ROUTE_INDEX = ROOT / "release/index/successor_play_route.index.v1.toml"
ACTIVE_ROUTE = ROOT / "release/index/successor_play_route.v2.toml"
CRITERIA_SEED = (
    ROOT
    / "contracts/policy/factorio/"
    "windows_instance_isolated_play_2_0_77_windows_x64.v1.toml"
)
CHECKPOINT = ROOT / "docs/release/checkpoints/facman-2-1-14-route-packet-01.md"

EXPECTED_ACTIVE_ROUTE_ID = (
    "facman.play.windows-x64.factorio-2.0.77.standalone.menu."
    "instance-isolated.successor.v2"
)
EXPECTED_PROPOSED_ROUTE_ID = (
    "facman.play.windows-x64.factorio-2.1.14.standalone.menu."
    "instance-isolated.successor.v3"
)
EXPECTED_ARCHIVE_SHA256 = (
    "cd96202e93ef93e170c8f37dda0ebacb9031011ab81770a5eec075a067e3da30"
)
EXPECTED_EXECUTABLE_SHA256 = (
    "2f5e2238a25c28bfbedf624bd49844f819971484abf24595e6fd27375b914999"
)
UNASSIGNED = "unassigned"
ZERO_REVISION = "0" * 40
ZERO_SHA256 = "0" * 64
EXPECTED_CANDIDATE = {
    "candidate_id": "facman-0.1.0-alpha.1-windows-winforms-x86_64-technical-preview",
    "source_revision": "8362ddc55cbb98b538f4af410819c9503604ef99",
    "package_sha256": "7882edf9eb2c0f2d14e570d4d734ddf08277e13ae89711dd2647d2392d35a025",
    "resolution_sha256": "d86b7a30e9ff2cd610512ff4d88179754bfad8fe5ca12699f898b10266ada56f",
    "provider_lock_sha256": "d33943841431afdeffb7961c7453d8999619ef371793a6310ad2c2952b118f00",
}
EXPECTED_BINDINGS = {
    "product_version": "0.1.0-alpha.1",
    "release_source": "release/index/alpha_release_source.v1.toml",
    "source_revision": EXPECTED_CANDIDATE["source_revision"],
    "source_tree": "859695fdcaead2e5e11c5454976432df13cacc1a",
    "provider_lock_sha256": EXPECTED_CANDIDATE["provider_lock_sha256"],
    "universal_launcher_revision": "5479939ca5cbc9ee0f901608a92012778b4752ae",
    "universal_setup_revision": "d2a2aae7e61c47035c92334b0522143b4fea3880",
    "candidate_id": EXPECTED_CANDIDATE["candidate_id"],
    "package_sha256": EXPECTED_CANDIDATE["package_sha256"],
    "resolution_sha256": EXPECTED_CANDIDATE["resolution_sha256"],
    "candidate_manifest_sha256": "e98d9f292eb3de6313cd7b08e169ef9544e471b6c7a71f001abd4dcd788d9552",
    "source_closure_digest": UNASSIGNED,
    "clean_host_id": UNASSIGNED,
    "clean_host_digest": UNASSIGNED,
    "observer_provider_revision": UNASSIGNED,
    "policy_digest": UNASSIGNED,
    "route_definition_digest": UNASSIGNED,
}

EXPECTED_ROLES = [
    "route_definition",
    "source_closure",
    "candidate_qualification",
    "clean_host",
    "observer_generation",
    "baseline",
    "prepare_lease",
    "launch_1_operation",
    "launch_1_attempt",
    "launch_1_permit",
    "launch_1_technical_packet",
    "launch_2_operation",
    "launch_2_attempt",
    "launch_2_permit",
    "launch_2_technical_packet",
    "human_verdict",
    "route_capability",
    "route_promotion",
]
EXPECTED_EVIDENCE_IDS = {
    "route_definition": "facman.successor-play.route-definition.03",
    "source_closure": "facman.successor-play.source-closure.03",
    "candidate_qualification": "facman.successor-play.candidate-qualification.03",
    "clean_host": "facman.successor-play.clean-host.03",
    "observer_generation": "facman.successor-play.observer-generation.03",
    "baseline": "facman.successor-play.baseline.03",
    "prepare_lease": "facman.successor-play.prepare-lease.03",
    "launch_1_operation": "facman.successor-play.launch-1.operation.03",
    "launch_1_attempt": "facman.successor-play.launch-1.attempt.03",
    "launch_1_permit": "facman.successor-play.launch-1.permit-slot.03",
    "launch_1_technical_packet": "facman.successor-play.launch-1.technical-packet.03",
    "launch_2_operation": "facman.successor-play.launch-2.operation.03",
    "launch_2_attempt": "facman.successor-play.launch-2.attempt.03",
    "launch_2_permit": "facman.successor-play.launch-2.permit-slot.03",
    "launch_2_technical_packet": "facman.successor-play.launch-2.technical-packet.03",
    "human_verdict": "facman.successor-play.human-verdict.03",
    "route_capability": "facman.successor-play.route-capability.03",
    "route_promotion": "facman.successor-play.route-promotion.03",
}
EXPECTED_ACTIONS = [
    "freeze_exact_candidate",
    "reconstruct_source_closure",
    "qualify_clean_windows_host",
    "freeze_version_specific_policy",
    "author_immutable_route_definition",
    "integrate_non_authorizing_route",
    "execute_two_fresh_supervised_launches",
    "record_human_test_receipt",
    "review_route_capability_and_promotion",
]
EXPECTED_HUMAN_JOURNEYS = [
    "facman.factorio-2-1-14.play-to-menu",
    "facman.factorio-2-1-14.last-run-truth",
    "facman.factorio-2-1-14.relaunch-save-visibility",
    "facman.preview.keyboard",
    "facman.preview.screen-reader",
    "facman.preview.high-contrast",
    "facman.preview.dpi-scaling",
]


def _toml(path: Path) -> dict[str, Any]:
    with path.open("rb") as handle:
        value = tomllib.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a TOML table")
    return value


def _json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def packet_digest(record: dict[str, Any]) -> str:
    canonical = copy.deepcopy(record)
    canonical.pop("packet_digest", None)
    encoded = json.dumps(
        canonical,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _schema_problems(
    instance: dict[str, Any], schema: dict[str, Any], label: str
) -> list[str]:
    if jsonschema is None:
        bounded_schema = _bounded_schema(schema)
        unsupported = json_contract.supported_schema_problems(bounded_schema)
        if unsupported:
            return [f"{label} bounded schema is unsupported: {item}" for item in unsupported]
        return [
            f"{label} schema rejection at {item}"
            for item in json_contract.validate(instance, bounded_schema)
        ]
    validator_class = jsonschema.validators.validator_for(schema)
    try:
        validator_class.check_schema(schema)
    except jsonschema.exceptions.SchemaError as exc:
        return [f"{label} schema is invalid: {exc.message}"]
    validator = validator_class(schema)
    problems: list[str] = []
    for error in sorted(validator.iter_errors(instance), key=lambda item: list(item.path)):
        location = ".".join(str(part) for part in error.absolute_path) or "$"
        problems.append(f"{label} schema rejection at {location}: {error.message}")
    return problems


def _bounded_schema(
    schema: dict[str, Any], root: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Inline local refs for FacMan's dependency-free bounded validator."""

    root = schema if root is None else root
    result: dict[str, Any] = {}
    reference = schema.get("$ref")
    if isinstance(reference, str):
        prefix = "#/$defs/"
        if not reference.startswith(prefix):
            raise ValueError(f"unsupported non-local schema reference: {reference}")
        target = root.get("$defs", {}).get(reference[len(prefix) :])
        if not isinstance(target, dict):
            raise ValueError(f"missing local schema reference: {reference}")
        result.update(_bounded_schema(target, root))
    for key, value in schema.items():
        if key in {"$ref", "$defs", "format", "uniqueItems"}:
            continue
        if isinstance(value, dict):
            result[key] = _bounded_schema(value, root)
        elif isinstance(value, list):
            result[key] = [
                _bounded_schema(item, root) if isinstance(item, dict) else item
                for item in value
            ]
        else:
            result[key] = value
    return result


def load_packet() -> dict[str, Any]:
    return _toml(PACKET)


def load_human_template() -> dict[str, Any]:
    return _json(HUMAN_TEMPLATE)


def validate(
    packet: dict[str, Any] | None = None,
    human_template: dict[str, Any] | None = None,
) -> list[str]:
    problems: list[str] = []
    try:
        packet = copy.deepcopy(packet) if packet is not None else load_packet()
        human_template = (
            copy.deepcopy(human_template)
            if human_template is not None
            else load_human_template()
        )
        packet_schema = _json(PACKET_SCHEMA)
        human_schema = _json(HUMAN_SCHEMA)
        decision = _toml(ENGINEERING_DECISION)
        route_index = _toml(ROUTE_INDEX)
        active_route = _toml(ACTIVE_ROUTE)
    except (OSError, ValueError, json.JSONDecodeError, tomllib.TOMLDecodeError) as exc:
        return [f"2.1.14 route packet input cannot be read: {exc}"]

    problems.extend(_schema_problems(packet, packet_schema, "route packet"))
    problems.extend(_schema_problems(human_template, human_schema, "human template"))

    if packet.get("packet_digest") != packet_digest(packet):
        problems.append("route packet digest does not match canonical content")

    if packet.get("active_route_id") != active_route.get("route_id"):
        problems.append("route packet does not preserve the exact active 2.0.77 route")
    if packet.get("active_route_id") != route_index.get("current_route_id"):
        problems.append("route packet disagrees with the unchanged active route index")
    if route_index.get("current_route_contract") != "release/index/successor_play_route.v2.toml":
        problems.append("active route index no longer selects immutable route v2")
    indexed_ids = [
        item.get("route_id")
        for item in route_index.get("route", [])
        if isinstance(item, dict)
    ]
    if indexed_ids != [
        "facman.play.windows-x64.factorio-2.0.77.standalone.menu.instance-isolated.successor.v1",
        EXPECTED_ACTIVE_ROUTE_ID,
    ]:
        problems.append("route packet work changed or extended the accepted 2.0.77 route index")
    if packet.get("proposed_route_id") in indexed_ids:
        problems.append("unaccepted 2.1.14 proposal was inserted into the active route index")
    if (ROOT / "release/index/successor_play_route.v3.toml").exists():
        problems.append("immutable route v3 may not be authored before exact candidate binding")
    if (
        ROOT
        / "contracts/policy/factorio/"
        "windows_instance_isolated_play_2_1_14_windows_x64.v1.toml"
    ).exists():
        problems.append("2.1.14 policy may not be frozen before exact candidate and host binding")

    seed = packet.get("engineering_seed", {})
    if seed.get("decision_contract") != "release/index/factorio_route_version_decision.v1.toml":
        problems.append("engineering seed does not point to the retained route-version decision")
    for field, expected in (
        ("version", decision.get("selected_engineering_version")),
        ("build", decision.get("selected_engineering_build")),
        ("archive_sha256", decision.get("archive", {}).get("sha256")),
        ("executable_sha256", decision.get("executable", {}).get("sha256")),
    ):
        if seed.get(field) != expected:
            problems.append(f"engineering seed {field} does not match the retained decision")
    if seed.get("archive_sha256") != EXPECTED_ARCHIVE_SHA256:
        problems.append("engineering seed archive identity drifted")
    if seed.get("executable_sha256") != EXPECTED_EXECUTABLE_SHA256:
        problems.append("engineering seed executable identity drifted")
    if seed.get("release_evidence_transfer_allowed") is not False:
        problems.append("engineering facts may not be relabelled as release evidence")
    if seed.get("fresh_rehash_required") is not True:
        problems.append("future source closure must freshly rehash private inputs")

    policy = packet.get("policy_scaffold", {})
    try:
        criteria_seed_sha256 = file_sha256(CRITERIA_SEED)
    except OSError as exc:
        problems.append(f"criteria seed cannot be hashed: {exc}")
    else:
        if policy.get("criteria_seed_sha256") != criteria_seed_sha256:
            problems.append("policy scaffold does not bind the exact structural criteria seed")
    if policy.get("criteria_seed_use") != "structure_only_rewrite_and_review_required":
        problems.append("2.0.77 policy may be used only as a structural seed")
    if policy.get("contract_path") != UNASSIGNED or policy.get("policy_digest") != UNASSIGNED:
        problems.append("policy identity was invented before exact candidate and host binding")

    bindings = packet.get("future_bindings", {})
    if bindings != EXPECTED_BINDINGS:
        problems.append("candidate-bound route identities differ from the qualified alpha.1 inputs")

    evidence = packet.get("evidence_identity", [])
    roles = [item.get("role") for item in evidence if isinstance(item, dict)]
    ids = [item.get("id") for item in evidence if isinstance(item, dict)]
    if roles != EXPECTED_ROLES:
        problems.append("fresh .03 evidence family roles are incomplete or reordered")
    if ids != [EXPECTED_EVIDENCE_IDS[role] for role in EXPECTED_ROLES]:
        problems.append("fresh .03 evidence family identities drifted or reuse history")
    if len(ids) != len(set(ids)):
        problems.append("fresh .03 evidence family contains duplicate identities")
    if any(str(identity).endswith((".01", ".02")) for identity in ids):
        problems.append("2.1.14 evidence family reuses a 2.0.77 identity")
    for item in evidence:
        if not isinstance(item, dict):
            continue
        expected_state = "reserved_uncreated"
        if item.get("role") == "candidate_qualification":
            expected_state = "bound_external_machine_receipt"
        elif item.get("role") in {"launch_1_permit", "launch_2_permit"}:
            expected_state = "reserved_unissued"
        elif item.get("role") == "human_verdict":
            expected_state = "reserved_unrecorded"
        if item.get("state") != expected_state:
            problems.append(f"evidence role {item.get('role')} has the wrong candidate-bound state")

    sequence = packet.get("sequence", {})
    if sequence.get("ordered_roles") != EXPECTED_ROLES:
        problems.append("evidence sequence does not preserve the exact fresh family order")
    for flag in (
        "historical_2_0_77_identity_reuse_forbidden",
        "engineering_evidence_relabel_forbidden",
        "later_steps_require_separate_authority",
    ):
        if sequence.get(flag) is not True:
            problems.append(f"evidence sequence must keep {flag} true")

    actions = packet.get("action", [])
    if [item.get("order") for item in actions if isinstance(item, dict)] != list(range(1, 10)):
        problems.append("action checklist order must be exactly 1 through 9")
    if [item.get("id") for item in actions if isinstance(item, dict)] != EXPECTED_ACTIONS:
        problems.append("action checklist is incomplete or reordered")
    if any(item.get("execution_allowed") is not False for item in actions if isinstance(item, dict)):
        problems.append("the preparation packet may not execute a future action")
    if actions and actions[0].get("requires_authority") is not False:
        problems.append("tagless exact-candidate identity preparation is incorrectly authority-gated")
    if any(item.get("requires_authority") is not True for item in actions[1:] if isinstance(item, dict)):
        problems.append("effectful or acceptance actions require separate future authority")

    human_packet = packet.get("human_packet", {})
    if human_packet.get("reserved_receipt_id") != EXPECTED_EVIDENCE_IDS["human_verdict"]:
        problems.append("human packet does not reserve the fresh .03 verdict identity")
    if human_packet.get("template_receipt_id") != UNASSIGNED:
        problems.append("human template must not consume the reserved verdict identity")
    for field in (
        "exact_candidate_required",
        "exact_source_closure_required",
        "exact_clean_host_required",
        "human_only",
        "automated_inference_forbidden",
    ):
        if human_packet.get(field) is not True:
            problems.append(f"human packet must keep {field} true")
    if human_packet.get("grants_route_authority") is not False:
        problems.append("human verdict may not grant route authority")

    if human_template.get("receipt_id") != UNASSIGNED:
        problems.append("human template receipt identity must remain unassigned")
    if human_template.get("candidate") != EXPECTED_CANDIDATE:
        problems.append("human template candidate fields differ from the exact alpha.1 binding")
    if human_template.get("tester") != "UNASSIGNED_TEMPLATE_DO_NOT_ACCEPT":
        problems.append("human template tester sentinel drifted")
    if human_template.get("tested_at") != "1970-01-01T00:00:00Z":
        problems.append("human template time sentinel drifted")
    journeys = human_template.get("journeys", [])
    if [item.get("id") for item in journeys if isinstance(item, dict)] != EXPECTED_HUMAN_JOURNEYS:
        problems.append("human template journey set is incomplete or reordered")
    if any(item.get("result") != "Inconclusive" for item in journeys if isinstance(item, dict)):
        problems.append("unexecuted human template journeys must remain Inconclusive")
    if human_template.get("result") != "Inconclusive":
        problems.append("unexecuted human template result must remain Inconclusive")
    authority = human_template.get("authority", {})
    if not authority or any(value is not False for value in authority.values()):
        problems.append("human template opens release or route authority")

    packet_authority = packet.get("authority", {})
    if not packet_authority or any(value is not False for value in packet_authority.values()):
        problems.append("route packet opens authority")
    if packet.get("release_evidence_created") is not False:
        problems.append("route packet claims release evidence")
    if packet.get("route_index_mutation") is not False:
        problems.append("route packet claims an active route-index mutation")

    try:
        checkpoint = CHECKPOINT.read_text(encoding="utf-8")
    except OSError as exc:
        problems.append(f"route packet checkpoint cannot be read: {exc}")
    else:
        for anchor in (
            "candidate_bound_unaccepted_non_authorizing",
            EXPECTED_PROPOSED_ROUTE_ID,
            "The active 2.0.77 route remains unchanged",
            "Do not execute this checklist from this WorkUnit",
        ):
            if anchor not in checkpoint:
                problems.append(f"route packet checkpoint is missing {anchor!r}")

    return problems


def main() -> int:
    problems = validate()
    if problems:
        for problem in problems:
            print(f"factorio-2-1-14-route-packet-check: {problem}", file=sys.stderr)
        return 1
    print(
        "factorio-2-1-14-route-packet-check: ok "
        "(candidate bound; 2.0.77 active; no execution or authority)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
