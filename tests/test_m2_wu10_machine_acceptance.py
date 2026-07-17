# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import copy
import hashlib
import json
import os
import shutil
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

import jsonschema

from tools import m2_wu10_machine_acceptance_check as verifier

RUNNER_REVISION = "3f8489275077347c2918f3bb03614ec6431362ff"
POLICY_REVISION = "a" * 40
VERIFIED_AT = "2099-01-01T00:00:00Z"
RUN_ID = "m2wu10-20990101-01"
INTERRUPTION_RUN_ID = RUN_ID + "-interruptions"
PRODUCT_BYTES = {
    "README.txt": b"Harmless Universal Setup M2 acceptance fixture.\n",
    "config/settings.ini": b"enabled=true\nmode=acceptance\n",
    "data/payload.dat": b"synthetic-data-v1\n",
}
SCHEMA_ROOT = Path(__file__).resolve().parents[1] / "contracts/schema/release"
RECORDED_OBSERVATION = (
    Path(__file__).resolve().parents[1]
    / "docs/quality/evidence/m2/m2-wu10-machine-acceptance.observation.v1.json"
)
RECORDED_RESULT = (
    Path(__file__).resolve().parents[1]
    / "docs/quality/evidence/m2/m2-wu10-machine-acceptance.pass.v1.json"
)


def canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def write_json(path: Path, value: dict[str, object], *, newline: bool = True) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical(value) + (b"\n" if newline else b""))


def write_native_order_json(path: Path, value: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rendered = json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    path.write_bytes(rendered + b"\n")


def snapshot(root: Path) -> str:
    if not root.exists():
        return digest(canonical({"entries": [], "state": "nonexistent"}))
    entries: list[dict[str, object]] = []
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        if path.is_dir():
            entries.append({"relative_path": relative, "type": "directory"})
        else:
            data = path.read_bytes()
            entries.append({"relative_path": relative, "sha256": digest(data), "size_bytes": len(data), "type": "file"})
    entries.sort(key=lambda item: str(item["relative_path"]))
    return digest(canonical({"entries": entries, "state": "directory"}))


def transitions(transaction_id: str) -> list[dict[str, object]]:
    states = ["created", "validated", "planned", "staging", "staged", "verified", "committing", "committed", "completed"]
    result: list[dict[str, object]] = []
    prior: str | None = None
    for index, state in enumerate(states):
        result.append({
            "sequence": index,
            "transition_id": f"{transaction_id}.{index}",
            "from": prior,
            "to": state,
            "recorded_at": f"2099-01-01T00:00:{index:02d}Z",
            "durable_before_external_visibility": True,
        })
        prior = state
    return result


def journal_document(
    transaction_id: str,
    plan_id: str,
    plan_digest: str,
    operation: str,
    root: Path,
    target: Path,
) -> dict[str, object]:
    chain = transitions(transaction_id)
    chain_bytes = b"".join(
        str(item["sequence"]).encode() + b"\0"
        + (b"" if item["from"] is None else str(item["from"]).encode()) + b"\0"
        + str(item["to"]).encode() + b"\0" + str(item["recorded_at"]).encode() + b"\n"
        for item in chain
    )
    return {
        "schema": "usk.transaction_journal.v1",
        "journal_id": f"journal.{transaction_id}",
        "journal_digest": digest(chain_bytes),
        "transaction_id": transaction_id,
        "plan_id": plan_id,
        "plan_digest": plan_digest,
        "operation": operation,
        "current_state": "completed",
        "created_at": "2099-01-01T00:00:00Z",
        "updated_at": "2099-01-01T00:00:08Z",
        "roots": [
            {"role": "target", "root": str(target), "classification": "operator_selected_owned_target"},
            {"role": "staging", "root": str(root / "setup-state/staging/stage"), "classification": "setup_owned"},
            {"role": "setup_state", "root": str(root / "setup-state/state"), "classification": "setup_owned"},
            {"role": "audit", "root": str(root / "setup-state/audit"), "classification": "audit_owned"},
        ],
        "transitions": chain,
        "recovery_metadata": {"staging_identity": "test:identity", "staged_files": []},
        "recovery": {"required": False, "available_actions": []},
    }


def make_bundle(base: Path) -> tuple[Path, dict[str, object]]:
    acceptance_root = base / "acceptance"
    run_root = acceptance_root / RUN_ID
    interruption_root = acceptance_root / INTERRUPTION_RUN_ID
    product_root = run_root / "installed-product"
    moved_root = run_root / "moved-product"
    for relative, data in PRODUCT_BYTES.items():
        path = product_root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    (run_root / "setup-state/staging").mkdir(parents=True)
    for name in ("installed", "ownership", "transactions"):
        (run_root / "setup-state/state" / name).mkdir(parents=True)
    (run_root / "setup-state/evidence/packets").mkdir(parents=True)
    audit_chain_id = f"audit.synthetic.m2.{RUN_ID}"
    audit_root = run_root / "setup-state/audit/chains" / audit_chain_id
    audit_root.mkdir(parents=True)

    archive_path = run_root / "synthetic-product.zip"
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_STORED) as archive:
        for relative, data in PRODUCT_BYTES.items():
            info = zipfile.ZipInfo("product/" + relative, date_time=(1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            archive.writestr(info, data)
    archive_sha = digest(archive_path.read_bytes())
    product_policy = [
        {"path": relative, "sha256": digest(data), "size_bytes": len(data)}
        for relative, data in PRODUCT_BYTES.items()
    ]
    archive_entries = [
        {"path": "product/" + item["path"], "sha256": item["sha256"], "size_bytes": item["size_bytes"]}
        for item in product_policy
    ]
    write_json(run_root / "setup-state/.usk-owned-root.v1.json", {
        "acceptance_root": acceptance_root.as_posix(), "schema": "usk.setup_owned_root.v1",
    })

    closure_snapshot = snapshot(product_root)
    absent_snapshot = snapshot(moved_root)
    plan_digests = {name: digest(f"plan:{name}".encode()) for name in ("install", "repair", "move", "uninstall")}
    plan_ids = {
        "install": f"plan.install.{RUN_ID}", "repair": f"plan.repair.{RUN_ID}",
        "move": f"plan.move.{RUN_ID}", "uninstall": f"plan.uninstall.clean.{RUN_ID}",
    }
    transaction_ids = {
        "install": f"tx.install.{RUN_ID}", "repair": f"tx.repair.{RUN_ID}",
        "move": f"tx.move.{RUN_ID}", "uninstall": f"tx.uninstall.clean.{RUN_ID}",
    }
    journal_names = {
        "install": f"tx.install.{RUN_ID}.journal.json", "repair": f"tx.repair.{RUN_ID}.journal.json",
        "move": f"tx.move.{RUN_ID}.journal.json", "uninstall": f"tx.uninstall.clean.{RUN_ID}.journal.json",
    }
    journal_docs: dict[str, dict[str, object]] = {}
    for operation in ("install", "repair", "move", "uninstall"):
        target = moved_root if operation in {"move", "uninstall"} else product_root
        doc = journal_document(
            transaction_ids[operation], plan_ids[operation], plan_digests[operation],
            "install_local" if operation == "install" else operation, run_root, target,
        )
        journal_docs[operation] = doc
        write_native_order_json(
            run_root / "setup-state/state/transactions" / journal_names[operation], doc,
        )

    ownership_docs: dict[str, dict[str, object]] = {}
    ownership_names: dict[str, str] = {}
    for operation in ("install", "repair", "move"):
        target = moved_root if operation == "move" else product_root
        name = f"ownership.synthetic.m2.{RUN_ID}.tx.{operation}.{RUN_ID}.json"
        document: dict[str, object] = {
            "created_by_transaction_id": transaction_ids[operation],
            "directories": [{"relative_path": "config"}, {"relative_path": "data"}],
            "files": [
                {"relative_path": item["path"], "sha256": item["sha256"], "size_bytes": item["size_bytes"]}
                for item in product_policy
            ],
            "install_id": f"synthetic.m2.{RUN_ID}",
            "manifest_id": name[:-5],
            "schema": "usk.ownership_manifest.v1",
            "target_root": str(target),
        }
        document["manifest_digest"] = digest(canonical(document))
        ownership_docs[operation] = document
        ownership_names[operation] = name
        write_json(run_root / "setup-state/state/ownership" / name, document)

    lifecycle_states = {"install": "installed", "repair": "verified", "move": "move_pending_acceptance", "uninstall": "retired"}
    installed_docs: dict[str, dict[str, object]] = {}
    installed_names: dict[str, str] = {}
    for operation in ("install", "repair", "move", "uninstall"):
        owner_key = "move" if operation == "uninstall" else operation
        target = moved_root if operation in {"move", "uninstall"} else product_root
        tx_part = f"uninstall.clean.{RUN_ID}" if operation == "uninstall" else f"{operation}.{RUN_ID}"
        name = f"synthetic.m2.{RUN_ID}.tx.{tx_part}.json"
        document = {
            "audit_chain_id": audit_chain_id,
            "component_selection": ["base"],
            "created_at": "2099-01-01T00:00:00Z",
            "entrypoints": [{"entrypoint_id": "readme", "kind": "tool", "relative_path": "README.txt"}],
            "install_id": f"synthetic.m2.{RUN_ID}",
            "last_verification": {
                "report_digest": digest(f"verify:{operation}".encode()),
                "report_id": f"verify.{operation}.{RUN_ID}", "status": "pass", "verified_at": "2099-01-01T00:00:00Z",
            },
            "lifecycle_status": lifecycle_states[operation],
            "ownership_manifest_digest": ownership_docs[owner_key]["manifest_digest"],
            "ownership_manifest_ref": "ownership/" + ownership_names[owner_key],
            "product_id": "synthetic.product", "product_version": "1.0.0",
            "recipe_digest": digest(b"recipe.synthetic.m2.v1\nnon-executable\n3-files"),
            "schema": "usk.installed_state.v1",
            "setup_abi": {"major": 1, "minor": 0, "provider_revision": RUNNER_REVISION},
            "source_archive_digest": archive_sha, "target_root": str(target), "target_scope": "portable",
            "transaction_id": transaction_ids[operation],
        }
        installed_docs[operation] = document
        installed_names[operation] = name
        write_json(run_root / "setup-state/state/installed" / name, document)

    audit_events: list[dict[str, object]] = []
    previous: str | None = None
    audit_operations = ["install_local", "install_local", "repair", "move", "uninstall"]
    for index, operation in enumerate(audit_operations):
        state_operation = "install" if index < 2 else operation
        details = plan_digests["install"] if index == 0 else installed_docs[state_operation]["last_verification"]["report_digest"]
        event: dict[str, object] = {
            "audit_chain_id": audit_chain_id, "created_at": "2099-01-01T00:00:00Z",
            "details_digest": details, "event_id": f"{audit_chain_id}.{index}",
            "message": f"derived test event {index}", "operation": operation,
            "phase": "validated" if index == 0 else "completed", "plan_id": plan_ids[state_operation],
            "previous_event_digest": previous, "schema": "usk.audit_event.v1", "sequence": index,
            "status": "pass", "subject": {"subject_id": f"subject.{index}", "subject_type": "installation"},
            "transaction_id": transaction_ids[state_operation],
        }
        event["event_digest"] = digest(canonical(event))
        previous = str(event["event_digest"])
        audit_events.append(event)
        write_json(audit_root / f"{index:020d}.event.json", event)

    packet_docs: dict[str, dict[str, object]] = {}
    operation_names = {"install": "install_local", "repair": "repair", "move": "move", "uninstall": "uninstall"}
    state_audit = {"install": 1, "repair": 2, "move": 3, "uninstall": 4}
    snapshot_pairs = {
        "install": (absent_snapshot, closure_snapshot),
        "repair": (digest(b"damaged-snapshot"), closure_snapshot),
        "move": (absent_snapshot, closure_snapshot),
        "uninstall": (closure_snapshot, absent_snapshot),
    }
    for operation in ("install", "repair", "move", "uninstall"):
        owner_key = "move" if operation == "uninstall" else operation
        pre_snapshot, post_snapshot = snapshot_pairs[operation]
        packet: dict[str, object] = {
            "archive": {
                "filesystem_identity_digest": digest(b"filesystem"), "path_identity_digest": digest(b"archive-path"),
                "sha256": archive_sha, "size_bytes": archive_path.stat().st_size,
                "source_id": f"source.synthetic.m2.{RUN_ID}",
            },
            "automated_findings": [], "captured_at": "2099-01-01T00:00:00Z",
            "committed_closure": {
                "byte_count": 0 if operation == "uninstall" else sum(map(len, PRODUCT_BYTES.values())),
                "closure_digest": digest(b"closure-removed" if operation == "uninstall" else b"closure-present"),
                "file_count": 0 if operation == "uninstall" else 3,
                "status": "removed" if operation == "uninstall" else "committed",
            },
            "contract_versions": [
                {"contract_id": "install_plan", "schema_version": "usk.install_plan.v1"},
                {"contract_id": "installed_state", "schema_version": "usk.installed_state.v1"},
                {"contract_id": "live_evidence", "schema_version": "usk.live_target_evidence_packet.v1"},
            ],
            "filesystem": {
                "capabilities": {"local": True, "no_mount_redirection": True, "no_replace_commit": True, "stable_ancestors": True},
                "identity_digest": digest(b"filesystem"), "kind": "test_fixed",
            },
            "operator_verdict": {"recorded_at": None, "recorded_by": None, "statement_digest": None, "status": "pending", "verdict": None},
            "packet_id": f"evidence.{operation}.{RUN_ID}",
            "plan": {
                "expected_byte_count": sum(map(len, PRODUCT_BYTES.values())), "expected_file_count": 3,
                "operation": operation_names[operation], "plan_digest": plan_digests[operation], "plan_id": plan_ids[operation],
            },
            "recipe": {
                "product_id": "synthetic.product", "product_version": "1.0.0",
                "recipe_digest": digest(b"recipe.synthetic.m2.v1\nnon-executable\n3-files"), "recipe_id": "recipe.synthetic.m2.v1",
            },
            "recovery": {"journal_digest": journal_docs[operation]["journal_digest"], "status": "not_required"},
            "schema": "usk.live_target_evidence_packet.v1",
            "setup_abi": {"major": 1, "minor": 0, "provider_revision": RUNNER_REVISION},
            "snapshots": {"post_target_digest": post_snapshot, "pre_target_digest": pre_snapshot},
            "source_revisions": [
                {"repository_id": "product_consumer", "revision": POLICY_REVISION},
                {"repository_id": "universal_setup", "revision": RUNNER_REVISION},
            ],
            "state": {
                "audit_chain_id": audit_chain_id, "audit_head_digest": audit_events[state_audit[operation]]["event_digest"],
                "installed_state_digest": digest(canonical(installed_docs[operation])),
                "ownership_digest": ownership_docs[owner_key]["manifest_digest"],
            },
            "supersedes_packet_digest": None,
            "target": {
                "path_identity_digest": digest(f"target:{operation}".encode()),
                "persistent_effects": [
                    "append setup-owned audit and evidence records", "create or mutate exact setup-owned target",
                    "write setup-owned state and transaction journal",
                ],
                "target_class": "operator_acceptance", "target_identity_digest": digest(f"identity:{operation}".encode()),
            },
        }
        packet["packet_digest"] = digest(canonical(packet))
        packet_docs[operation] = packet
        write_json(run_root / f"setup-state/evidence/packets/evidence.{operation}.{RUN_ID}.json", packet)

    steps = [
        ["install_plan", "reviewed"], ["install_apply", "completed"], ["install_verify", "pass"],
        ["damage_verify", "expected_fail"], ["repair", "pass"],
        ["same_volume_move", "pass_old_root_retained"],
        ["cross_volume_move", "not_attempted_no_second_authorized_volume"],
        ["uninstall_with_foreign_content", "refused_and_retained"],
        ["operator_exact_foreign_file_removal", "completed_by_runner_not_setup"], ["clean_uninstall", "pass"],
    ]
    summary = {
        "archive": {"contains_executable_code": False, "path": archive_path.as_posix(), "sha256": archive_sha},
        "authority": {
            "acceptance_root": acceptance_root.as_posix(), "operator_verdict": "pending",
            "ordinary_live_apply_promoted": False, "run_execute_authorized": False,
        },
        "completed_at": VERIFIED_AT,
        "evidence_packets": [
            {"packet_digest": packet_docs[operation]["packet_digest"], "packet_id": packet_docs[operation]["packet_id"]}
            for operation in ("install", "repair", "move", "uninstall")
        ],
        "run_id": RUN_ID, "run_root": run_root.as_posix(), "schema": "usk.m2_live_acceptance_summary.v1",
        "source_revisions": {"consumer": POLICY_REVISION, "universal_setup": RUNNER_REVISION},
        "status": "automated_findings_complete_pending_operator_verdict",
        "steps": [{"name": name, "status": status} for name, status in steps],
    }
    write_json(run_root / "acceptance-summary.json", summary)

    interruption_root.mkdir(parents=True)
    interruption_summary = {
        "automation_created_verdict": False, "case_count": 11, "completed": 3,
        "operator_verdict": "pending", "recovery_required": 3, "rolled_back": 4,
        "run_id": INTERRUPTION_RUN_ID, "schema": "usk.interruption_acceptance_summary.v1", "unchanged": 1,
    }
    write_json(interruption_root / "interruption-summary.json", interruption_summary, newline=False)
    for index in range(14):
        tx = f"tx.interruption.{index}"
        plan = f"plan.interruption.{index}"
        document = journal_document(tx, plan, digest(plan.encode()), "install_local", interruption_root, interruption_root / f"target-{index}")
        write_native_order_json(
            interruption_root / f"case-{index}/state/{tx}.journal.json", document,
        )

    policy = copy.deepcopy(verifier.load_policy())
    policy["scope"]["acceptance_root"] = str(acceptance_root)
    policy["synthetic_archive"]["sha256"] = archive_sha
    policy["synthetic_archive"]["entries"] = archive_entries
    policy["retained_lifecycle"]["product_files"] = product_policy
    files = [path for path in run_root.rglob("*") if path.is_file()]
    directories = [path for path in run_root.rglob("*") if path.is_dir()]
    policy["retained_lifecycle"]["file_count"] = len(files)
    policy["retained_lifecycle"]["directory_count"] = len(directories)
    policy["retained_lifecycle"]["total_bytes"] = sum(path.stat().st_size for path in files)
    return acceptance_root, policy


def run_verifier(root: Path, policy: dict[str, object]) -> tuple[dict[str, object] | None, list[str]]:
    return verifier.verify_evidence(
        policy, root, RUN_ID, INTERRUPTION_RUN_ID, POLICY_REVISION,
        RUNNER_REVISION, POLICY_REVISION, VERIFIED_AT,
        test_mode=True, enforce_frozen_policy=False,
    )


class M2Wu10MachineAcceptanceTests(unittest.TestCase):
    def test_frozen_policy_records_no_result(self) -> None:
        policy = verifier.load_policy()
        schema = json.loads((SCHEMA_ROOT / "m2_synthetic_portable_acceptance_policy.v1.schema.json").read_text(encoding="utf-8"))
        jsonschema.Draft202012Validator(schema).validate(policy)
        self.assertEqual([], verifier.validate_policy(policy))
        self.assertFalse(policy["technical_acceptance"]["current_result_recorded"])
        self.assertNotIn("result", policy)
        self.assertEqual(0, verifier.main(["--policy-only"]))

    def test_independent_fixture_derives_evidence_pass(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root, policy = make_bundle(Path(temporary))
            journals = sorted(root.rglob("*.journal.json"))
            self.assertEqual(18, len(journals))
            for path in journals:
                raw = path.read_bytes()
                value = json.loads(raw)
                self.assertNotIn(raw, {canonical(value), canonical(value) + b"\n"})
            result, problems = run_verifier(root, policy)
        self.assertEqual([], problems)
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual("factorio.m2_machine_acceptance_observation.v1", result["schema"])
        self.assertEqual("EvidencePass", result["technical_acceptance"]["result"])
        self.assertEqual("not_required", result["human_review"]["result"])
        self.assertFalse(result["authority"]["run_execute"])
        observation_schema = json.loads((SCHEMA_ROOT / "m2_machine_acceptance_observation.v1.schema.json").read_text(encoding="utf-8"))
        jsonschema.Draft202012Validator(observation_schema).validate(result)

        recorded = copy.deepcopy(result)
        recorded["schema"] = "factorio.m2_machine_acceptance_result.v1"
        recorded["technical_acceptance"]["result"] = "MachinePass"
        recorded["technical_acceptance"]["observation_sha256"] = digest(canonical(result))
        recorded["validation"] = {
            "local": {"result": "pass", "commands": ["strict"]},
            "hosted": {
                "result": "pass", "validated_revision": "b" * 40,
                "pull_request": 1,
                "workflows": [
                    {"name": name, "run_id": str(index), "result": "success"}
                    for index, name in enumerate(("ci", "codeql", "security", "schema"), start=1)
                ],
            },
        }
        result_schema = json.loads((SCHEMA_ROOT / "m2_machine_acceptance_result.v1.schema.json").read_text(encoding="utf-8"))
        jsonschema.Draft202012Validator(result_schema).validate(recorded)

    def test_recorded_observation_binds_corrected_policy_and_fresh_evidence(self) -> None:
        raw = RECORDED_OBSERVATION.read_bytes()
        self.assertEqual(
            "fb0fcb58eec795d45a56cb48773d74ed74a38d4b14834a4921c1542310777181",
            digest(raw),
        )
        observation = json.loads(raw)
        schema = json.loads(
            (SCHEMA_ROOT / "m2_machine_acceptance_observation.v1.schema.json").read_text(
                encoding="utf-8",
            )
        )
        jsonschema.Draft202012Validator(schema).validate(observation)
        technical = observation["technical_acceptance"]
        self.assertEqual("EvidencePass", technical["result"])
        self.assertEqual(
            "26eb7056984b42859e377c1ffd0ffb7c80488078",
            technical["policy_revision"],
        )
        self.assertEqual(technical["policy_revision"], technical["verifier_revision"])
        self.assertEqual(
            "3f8489275077347c2918f3bb03614ec6431362ff",
            technical["runner_revision"],
        )
        self.assertEqual("m2wu10-20260717-02", observation["evidence"]["run_id"])
        self.assertFalse(observation["authority"]["run_execute"])

    def test_recorded_machine_pass_binds_candidate_validation_without_human_pass(self) -> None:
        raw = RECORDED_RESULT.read_bytes()
        self.assertEqual(
            "a4a00a3f77b394f988a71f9eaa86de3c9c9b74a4051d1c2e3ad38f60b9ad8efa",
            digest(raw),
        )
        result = json.loads(raw)
        schema = json.loads(
            (SCHEMA_ROOT / "m2_machine_acceptance_result.v1.schema.json").read_text(
                encoding="utf-8",
            )
        )
        jsonschema.Draft202012Validator(schema).validate(result)
        observation = json.loads(RECORDED_OBSERVATION.read_text(encoding="utf-8"))
        self.assertEqual(observation["evidence"], result["evidence"])
        self.assertEqual(observation["authority"], result["authority"])
        self.assertEqual("MachinePass", result["technical_acceptance"]["result"])
        self.assertEqual(
            digest(canonical(result["evidence"])),
            result["technical_acceptance"]["evidence_digest"],
        )
        self.assertEqual(
            digest(RECORDED_OBSERVATION.read_bytes()),
            result["technical_acceptance"]["observation_sha256"],
        )
        hosted = result["validation"]["hosted"]
        self.assertEqual(
            "ff883cd7b88dda07c0a336ced267cbe1f9f2746f",
            hosted["validated_revision"],
        )
        self.assertEqual(28, hosted["pull_request"])
        self.assertEqual(
            {
                "ci (push)": "29562177050",
                "code-security (push)": "29562177030",
                "security-policy (push)": "29562177062",
                "ci (pull_request)": "29562194145",
                "code-security (pull_request)": "29562194103",
                "security-policy (pull_request)": "29562194153",
            },
            {entry["name"]: entry["run_id"] for entry in hosted["workflows"]},
        )
        self.assertEqual("not_required", result["human_review"]["result"])
        self.assertEqual("candidate", result["authority"]["local_managed_portable_setup"])
        for excluded in (
            "credentials", "elevation", "existing_factorio_mutation",
            "existing_installation_adoption", "factorio_archive_acceptance",
            "network", "publication", "registry", "run_execute", "shortcuts",
            "signing", "steam_cloud_mutation", "steam_mutation",
            "system_wide_installation",
        ):
            self.assertFalse(result["authority"][excluded], excluded)
        self.assertEqual("none", result["authority"]["h1_inference"])

    def test_required_negative_controls_fail_closed(self) -> None:
        controls = {
            "alter_acceptance_summary": self._alter_summary,
            "alter_synthetic_archive": self._alter_archive,
            "alter_evidence_packet": self._alter_packet,
            "break_audit_chain_linkage": self._break_audit,
            "add_reparse_point": self._add_reparse,
            "add_unexpected_retained_file": self._add_file,
            "change_expected_tree_counts": self._change_counts,
            "recreate_moved_product": self._recreate_moved,
            "remove_installed_product": self._remove_installed,
            "target_outside_acceptance_root": self._escape_target,
            "change_provider_revision": self._change_provider,
            "promote_excluded_authority": self._promote_authority,
        }
        self.assertEqual(verifier.EXPECTED_NEGATIVE_CONTROLS, list(controls))
        for name, mutate in controls.items():
            with self.subTest(control=name), tempfile.TemporaryDirectory() as temporary:
                root, policy = make_bundle(Path(temporary))
                patcher = mutate(root, policy)
                if patcher is None:
                    _, problems = run_verifier(root, policy)
                else:
                    with patcher:
                        _, problems = run_verifier(root, policy)
                self.assertTrue(problems, f"negative control {name} unexpectedly passed")

    @staticmethod
    def _alter_summary(root: Path, policy: dict[str, object]) -> None:
        path = root / RUN_ID / "acceptance-summary.json"
        path.write_bytes(path.read_bytes() + b" ")

    @staticmethod
    def _alter_archive(root: Path, policy: dict[str, object]) -> None:
        path = root / RUN_ID / "synthetic-product.zip"
        data = bytearray(path.read_bytes())
        data[0] ^= 0xFF
        path.write_bytes(data)

    @staticmethod
    def _alter_packet(root: Path, policy: dict[str, object]) -> None:
        path = root / RUN_ID / f"setup-state/evidence/packets/evidence.install.{RUN_ID}.json"
        document = json.loads(path.read_text())
        document["captured_at"] = "2099-01-01T00:00:01Z"
        write_json(path, document)

    @staticmethod
    def _break_audit(root: Path, policy: dict[str, object]) -> None:
        path = root / RUN_ID / f"setup-state/audit/chains/audit.synthetic.m2.{RUN_ID}/00000000000000000002.event.json"
        document = json.loads(path.read_text())
        document["previous_event_digest"] = "0" * 64
        document["event_digest"] = digest(canonical({key: value for key, value in document.items() if key != "event_digest"}))
        write_json(path, document)

    @staticmethod
    def _add_reparse(root: Path, policy: dict[str, object]) -> mock._patch:
        path = root / RUN_ID / "redirected"
        path.mkdir()
        original = verifier._is_reparse_or_link
        return mock.patch.object(verifier, "_is_reparse_or_link", side_effect=lambda candidate: candidate == path or original(candidate))

    @staticmethod
    def _add_file(root: Path, policy: dict[str, object]) -> None:
        (root / RUN_ID / "unexpected.txt").write_text("unexpected", encoding="utf-8")

    @staticmethod
    def _change_counts(root: Path, policy: dict[str, object]) -> None:
        policy["retained_lifecycle"]["file_count"] += 1

    @staticmethod
    def _recreate_moved(root: Path, policy: dict[str, object]) -> None:
        (root / RUN_ID / "moved-product").mkdir()

    @staticmethod
    def _remove_installed(root: Path, policy: dict[str, object]) -> None:
        shutil.rmtree(root / RUN_ID / "installed-product")

    @staticmethod
    def _escape_target(root: Path, policy: dict[str, object]) -> None:
        path = root / RUN_ID / f"setup-state/state/transactions/tx.install.{RUN_ID}.journal.json"
        document = json.loads(path.read_text())
        document["roots"][0]["root"] = str(root.parent / "outside-target")
        write_json(path, document)

    @staticmethod
    def _change_provider(root: Path, policy: dict[str, object]) -> None:
        path = root / RUN_ID / "acceptance-summary.json"
        document = json.loads(path.read_text())
        document["source_revisions"]["universal_setup"] = "b" * 40
        write_json(path, document)

    @staticmethod
    def _promote_authority(root: Path, policy: dict[str, object]) -> None:
        path = root / RUN_ID / "acceptance-summary.json"
        document = json.loads(path.read_text())
        document["authority"]["run_execute_authorized"] = True
        write_json(path, document)


if __name__ == "__main__":
    unittest.main()
