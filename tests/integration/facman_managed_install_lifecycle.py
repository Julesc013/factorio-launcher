# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT
"""Exercise Windows public managed-install commands with owned, non-executable ZIP inputs."""
from __future__ import annotations

import argparse
import ctypes
import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
import zipfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools import development_layout  # noqa: E402

VERSION = "2.0.77"
BYTES = b"harmless non-executable fixture bytes"


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def shared_bytes(path: Path, limit=4*1024*1024) -> bytes:
    """Observe retained bytes without introducing Windows sharing failures."""
    import msvcrt
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateFileW.argtypes = [ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_uint32,
                                  ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p]
    kernel.CreateFileW.restype = ctypes.c_void_p
    kernel.CloseHandle.argtypes = [ctypes.c_void_p]
    handle = kernel.CreateFileW(str(path), 0x80000000, 7, None, 3, 0x80, None)
    if handle == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        descriptor = msvcrt.open_osfhandle(handle, os.O_RDONLY | os.O_BINARY)
    except Exception:
        kernel.CloseHandle(handle)
        raise
    with os.fdopen(descriptor, "rb") as stream:
        data = stream.read(limit+1)
    if len(data) > limit:
        raise ValueError("retained file exceeds the proof's observation bound")
    return data


def shared_journal(path: Path) -> dict:
    """Observe atomic journal replacement without introducing Windows sharing failures."""
    return json.loads(shared_bytes(path))


class PublicInstallProof:
    def __init__(self, executable: Path, root: Path):
        self.executable = executable.resolve(strict=True)
        self.root = root.resolve()
        owner = next((p for p in self.root.parents if (p/development_layout.MARKER_NAME).is_file()), None)
        if owner is None:
            raise ValueError("proof root must be below a marker-owned task root")
        development_layout.read_marker(owner, ROOT)
        self.root.mkdir(exist_ok=False)
        self.steps: list[dict] = []
        self.open_gaps: list[str] = []

    def environment(self, case: Path, configured=True, fault="") -> dict[str, str]:
        environment = os.environ.copy()
        for key in list(environment):
            if key.startswith("FACMAN_TEST_INSTALL_") or key in {
                "FACMAN_SETUP_STATE_ROOT", "FACMAN_SETUP_ACCEPTANCE_ROOT", "FACMAN_SETUP_POLICY_ACTIVATION"
            }:
                environment.pop(key)
        if configured:
            environment.update(FACMAN_SETUP_STATE_ROOT=str(case/"setup-state"),
                               FACMAN_SETUP_ACCEPTANCE_ROOT=str(case),
                               FACMAN_SETUP_POLICY_ACTIVATION="operator_acceptance_candidate")
        if fault:
            environment[fault] = "1"
        return environment

    def case(self, name: str) -> Path:
        case = self.root/name
        case.mkdir()
        with zipfile.ZipFile(case/"source.zip", "w", zipfile.ZIP_STORED) as archive:
            archive.writestr("factorio/bin/x64/factorio.exe", BYTES)
            archive.writestr("factorio/data/base/info.json", json.dumps({"name": "base", "version": VERSION}))
        return case

    def run(self, case: Path, args: list[str], outcome="ok", code="", configured=True, fault="") -> dict:
        environment = self.environment(case, configured, fault)
        command = [str(self.executable), "--workspace", str(case/"workspace"), *args, "--json"]
        result = subprocess.run(command, env=environment, capture_output=True, text=True, timeout=40)
        response = json.loads(result.stdout)
        self.steps.append({"case": case.name, "command": args, "exit": result.returncode,
                           "response": response, "fault": fault})
        self.receipt("running")
        if response["outcome"] != outcome:
            raise AssertionError(f"{args[:4]}: expected {outcome}, received {response}")
        if outcome == "recovery_required":
            assert response["operation"]["effects_may_have_occurred"]
            assert response["operation"]["recovery"]["required"]
        payload = response["payload"]
        if code and payload.get("refusal", {}).get("code") != code:
            raise AssertionError(f"unexpected refusal: {payload}")
        return payload

    def plan(self, case: Path) -> dict:
        return self.run(case, ["installs", "install", "plan", VERSION, "--archive", str(case/"source.zip"),
                               "--target", str(case/"target"), "--id", "managed-test"])

    def apply_args(self, case: Path, plan: dict, transaction="tx-managed-install") -> list[str]:
        applied = (datetime.datetime.fromisoformat(plan["created_at"].replace("Z", "+00:00")) +
                   datetime.timedelta(seconds=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
        return ["installs", "install", "apply", plan["plan_id"], "--version", VERSION,
                "--archive", str(case/"source.zip"), "--target", str(case/"target"), "--id", "managed-test",
                "--digest", plan["plan_digest"], "--plan-created-at", plan["created_at"],
                "--transaction-id", transaction, "--applied-at", applied, "--confirm", "APPLY"]

    def record(self, case: Path) -> Path:
        return case/"workspace/installs/refs/managed-test.json"

    def verify(self, case: Path, verification="pass") -> dict:
        record = json.loads(self.record(case).read_text())
        assert record["ownership"] == "managed" and record["lifecycle_status"] == "active"
        assert record["safe_actions"] == {"repair": True, "uninstall": True}
        assert record["strict_isolation_eligibility"] == "unproven"
        assert record["installation_layout"] == "portable_archive"
        assert (case/"target/bin/x64/factorio.exe").read_bytes() == BYTES
        state = json.loads(Path(record["setup_state_ref"]).read_text())
        assert state["install_id"] == "managed-test" and state["product_version"] == VERSION
        assert state["last_verification"]["status"] == verification
        assert record["verification"]["status"] == verification
        assert record["state_revision"] == state["transaction_id"] + ":" + state["ownership_manifest_digest"]
        if (case/"source.zip").exists():
            assert state["source_archive_digest"] == digest(case/"source.zip")
        return record

    def recover(self, case: Path, fault="", classification="provider_installed") -> dict:
        plan = self.run(case, ["installs", "recovery", "inspect", "tx-managed-install"])
        assert plan["operation"] == "install" and plan["classification"] == classification
        return self.run(case, ["installs", "recovery", "apply", "tx-managed-install", plan["plan_id"],
                               "--digest", plan["plan_digest"], "--confirm", "APPLY"],
                        outcome="recovery_required" if fault else "ok",
                        code="transaction_recovery_required" if fault else "", fault=fault)

    def receipt(self, result: str) -> None:
        document = {"schema": "facman.managed_install_public_proof.v1", "result": result,
                    "classification": "owned synthetic-input engineering evidence; no game execution or human qualification",
                    "facman_sha256": digest(self.executable), "steps": self.steps, "open_gaps": self.open_gaps}
        (self.root/"receipt.json").write_text(json.dumps(document, indent=2), encoding="utf-8")

    def verification(self) -> None:
        case = self.case("verification")
        self.run(case, self.apply_args(case, self.plan(case)))
        self.verify(case)

        def snapshot() -> dict:
            return {str(path.relative_to(case)): ("directory" if path.is_dir() else digest(path))
                    for path in sorted(case.rglob("*"))}

        def check(status="", code="", configured=True, missing=0, changed=0, damaged=(), unknown=()) -> dict:
            before = snapshot()
            payload = self.run(case, ["installs", "verify", "managed-test"],
                               outcome=("unavailable" if code == "live_target_acceptance_required" and not configured
                                        else "refused" if code else "ok"), code=code, configured=configured)
            assert snapshot() == before, "read-only verification changed retained bytes or paths"
            if code:
                response = self.steps[-1]["response"]
                assert response["effects"] == []
                assert not response["operation"]["effects_may_have_occurred"]
                assert not response["operation"]["recovery"]["required"]
                if configured:
                    assert payload["refusal"]["detail"] != "capability remains quarantined"
            if status:
                assert payload["schema"] == "usk.verification_report.v1" and payload["status"] == status
                unsigned = {key: value for key, value in payload.items() if key not in {"schema", "report_digest"}}
                canonical = json.dumps(unsigned, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
                assert hashlib.sha256(canonical).hexdigest() == payload["report_digest"]
                human = subprocess.run([str(self.executable), "--workspace", str(case/"workspace"),
                                        "installs", "verify", "managed-test"],
                                       env=self.environment(case), capture_output=True, text=True, timeout=40)
                self.steps.append({"case": case.name, "command": ["installs", "verify", "managed-test"],
                                   "format": "human", "exit": human.returncode,
                                   "stdout": human.stdout, "stderr": human.stderr})
                self.receipt("running")
                assert human.returncode == 0 and not human.stderr, human.stderr
                assert snapshot() == before, "human verification changed retained bytes or paths"
                assert f"Verification: {status}" in human.stdout and "Install: managed-test" in human.stdout
                assert f"Owned files: 2; missing: {missing}; changed: {changed}" in human.stdout
                assert "Setup operation previewed" not in human.stdout
                if status == "fail":
                    assert "Verification: pass" not in human.stdout
                    assert "Damaged owned paths: none" not in human.stdout
                for path, observed in damaged:
                    assert f"{path}: {observed}" in human.stdout
                assert f"Preserved unknown paths ({len(unknown)}):" in human.stdout
                for path in unknown:
                    assert path in human.stdout.split("Preserved unknown paths", 1)[1]
            return payload

        check(code="live_target_acceptance_required", configured=False)
        check("pass")
        # Verification does not depend on the original archive surviving.
        (case/"source.zip").unlink()
        check("pass")
        foreign = case/"target/user-data.txt"
        foreign.write_bytes(b"foreign bytes must survive")
        warn = check("warn", unknown=("user-data.txt",))
        assert warn["unknown_paths"] == ["user-data.txt"]
        executable = case/"target/bin/x64/factorio.exe"
        executable.write_bytes(b"modified owned bytes")
        failed = check("fail", changed=1, damaged=(("bin/x64/factorio.exe", "modified"),), unknown=("user-data.txt",))
        assert failed["summary"]["modified_files"] == 1
        executable.unlink()
        failed = check("fail", missing=1, damaged=(("bin/x64/factorio.exe", "missing"),), unknown=("user-data.txt",))
        assert failed["summary"]["missing_files"] == 1
        executable.mkdir()
        failed = check("fail", changed=1, damaged=(("bin/x64/factorio.exe", "wrong_type"),), unknown=("user-data.txt",))
        assert failed["summary"]["modified_files"] == 1
        assert any(row["status"] == "wrong_type" for row in failed["files"])
        executable.rmdir()
        executable.write_bytes(BYTES)
        sentinel = case/"foreign-sentinel"
        sentinel.mkdir()
        (sentinel/"untouched.txt").write_bytes(b"foreign sentinel bytes")
        junction = case/"target/foreign-junction"
        subprocess.run(["cmd", "/c", "mklink", "/J", str(junction), str(sentinel)],
                       check=True, capture_output=True, text=True)
        try:
            check(code="ownership_denied")
            assert (sentinel/"untouched.txt").read_bytes() == b"foreign sentinel bytes"
        finally:
            os.rmdir(junction)
        retained_target = case/"temporarily-retained-target"
        (case/"target").rename(retained_target)
        try:
            failed = check("fail", missing=2, damaged=(("bin/x64/factorio.exe", "missing"),
                                                      ("data/base/info.json", "missing")))
            assert failed["summary"]["missing_files"] == failed["summary"]["owned_files"]
            assert not (case/"target").exists()
        finally:
            retained_target.rename(case/"target")
        original = self.record(case).read_bytes()
        record = json.loads(original)
        for field, value, code in [
            ("ownership", "external", "ownership_denied"),
            ("provider_id", "foreign-provider", "managed_install_provider_mismatch"),
            ("state_revision", "stale-revision", "setup_installed_state_response_invalid"),
            ("last_verification_identity", "0"*64, "setup_installed_state_response_invalid"),
            ("setup_state_ref", str(case/"foreign-state.json"), "setup_installed_state_response_invalid"),
        ]:
            changed = dict(record)
            changed[field] = value
            self.record(case).write_text(json.dumps(changed))
            check(code=code)
            self.record(case).write_bytes(original)
        before = snapshot()
        self.run(case, ["installs", "verify", "unknown-install"], outcome="refused", code="unknown_install")
        assert snapshot() == before
        # A registered managed record outside the explicit acceptance root stays foreign.
        changed = dict(record)
        changed["root"] = str(case.parent/"foreign-target")
        self.record(case).write_text(json.dumps(changed))
        check(code="ownership_denied")
        self.record(case).write_bytes(original)
        check("warn", unknown=("user-data.txt",))

    def move_preview(self) -> None:
        case = self.case("move-preview")
        self.run(case, self.apply_args(case, self.plan(case)))
        self.verify(case)
        destination = case/"move-destination"
        foreign = case/"target/foreign.txt"
        foreign.write_bytes(b"foreign bytes remain foreign")
        (case/"target/empty-directory").mkdir()

        def snapshot() -> dict:
            # Walk without following junctions; include types, empty directories,
            # all source/provider/workspace bytes and any sibling shared guards.
            rows = {}
            pending = [case]
            while pending:
                directory = pending.pop()
                for path in sorted(directory.iterdir()):
                    status = path.lstat()
                    key = str(path.relative_to(case))
                    if getattr(status, "st_file_attributes", 0) & 0x400 or path.is_symlink():
                        rows[key] = ("redirect", getattr(status, "st_reparse_tag", 0))
                    elif path.is_dir():
                        rows[key] = "directory"
                        pending.append(path)
                    else:
                        rows[key] = digest(path)
            rows["sibling-guards"] = {p.name: digest(p) for p in case.parent.glob(".facman-managed-install-*.lock")}
            return rows

        def check(target=destination, code="", configured=True) -> dict:
            before = snapshot()
            payload = self.run(case, ["installs", "move", "plan", "managed-test", "--target", str(target)],
                               outcome=("unavailable" if not configured else "refused" if code else "ok"),
                               code=code, configured=configured)
            assert snapshot() == before and not destination.exists(), "move preview changed fixture bytes/paths"
            response = self.steps[-1]["response"]
            assert response["effects"] == [] and not response["operation"]["effects_may_have_occurred"]
            assert not response["operation"]["recovery"]["required"]
            if code:
                return payload
            assert payload["schema"] == "facman.managed_move_plan.v1"
            assert payload["copy_scope"] == "complete_source_files_including_foreign"
            assert payload["grants_ownership"] is False and payload["apply_available"] is True
            assert payload["observation_atomic"] is False
            assert payload["empty_directory_preservation"] == "not_promised"
            plan = payload["provider_plan"]
            assert plan["schema"] == "usk.operation_plan.v1" and plan["operation"] == "move"
            assert plan["status"] == "planned" and plan["install_id"] == "managed-test"
            copies = {r["relative_path"]: r for r in plan["effects"] if r["kind"] == "copy_owned_file"}
            actual = {p.relative_to(case/"target").as_posix(): digest(p)
                      for p in (case/"target").rglob("*") if p.is_file()}
            assert set(copies) == set(actual)
            assert all(copies[path]["expected_sha256"] == value for path, value in actual.items())
            assert "foreign.txt" in copies and "empty-directory" not in copies
            assert {r["role"] for r in plan["roots"]} == {"current", "destination", "staging", "setup_state", "audit"}
            staging = next(r for r in plan["roots"] if r["role"] == "staging")
            assert staging["root"] == destination.parent.as_posix()
            assert staging["classification"] == "setup_owned"
            selected = next(r for r in plan["roots"] if r["role"] == "destination")
            assert selected["root"] == destination.as_posix() and selected["must_not_exist"] is True
            assert selected["classification"] == "operator_selected_owned_target"
            return payload

        check(code="live_target_acceptance_required", configured=False)
        planned = check()
        before = snapshot()
        human_args = ["installs", "move", "plan", "managed-test", "--target", str(destination)]
        human = subprocess.run([str(self.executable), "--workspace", str(case/"workspace"), *human_args],
                               env=self.environment(case), capture_output=True, text=True, timeout=40)
        self.steps.append({"case": case.name, "command": human_args, "format": "human", "exit": human.returncode,
                           "stdout": human.stdout, "stderr": human.stderr})
        self.receipt("running")
        assert human.returncode == 0 and not human.stderr, human.stderr
        for text in ("Read-only managed move preview: planned", "Source:", "Destination (must be absent):",
                     "Copies include foreign files", "grant no ownership", "preservation is not promised",
                     "Bounded apply verifies the new root", "not an atomic snapshot"):
            assert text in human.stdout, text
        assert snapshot() == before
        rpc = {"schema": "facman.transport_request.v2", "protocol_version": 2,
               "request_id": "req-move-preview", "operation_id": "op-move-preview", "attempt_id": "attempt-move-preview",
               "command": "installs.move.plan", "workspace": str(case/"workspace"), "dry_run": True,
               "payload": {"install_id": "managed-test", "target_root": str(destination)}}
        result = subprocess.run([str(self.executable), "rpc", "--stdio"], input=json.dumps(rpc)+"\n",
                                env=self.environment(case), capture_output=True, text=True, timeout=40)
        response = json.loads(result.stdout)
        self.steps.append({"case": case.name, "command": ["rpc", "--stdio"], "request": rpc,
                           "response": response, "exit": result.returncode})
        self.receipt("running")
        assert result.returncode == 0 and response["outcome"] == "ok", response
        assert response["payload"]["schema"] == planned["schema"]
        assert response["payload"]["grants_ownership"] is False and response["effects"] == []
        assert snapshot() == before
        for target, code in ((case/"target", "ownership_denied"), (case/"workspace", "invalid_argument"),
                             (Path("relative-destination"), "ownership_denied"),
                             (case/".."/"escaped", "ownership_denied"), (case.parent/"outside", "ownership_denied")):
            check(target, code)
        original = self.record(case).read_bytes()
        record = json.loads(original)
        for field, value, code in (
            ("provider_id", "foreign", "managed_install_provider_mismatch"),
            ("state_revision", "stale", "setup_installed_state_response_invalid"),
            ("last_verification_identity", "0"*64, "setup_installed_state_response_invalid"),
            ("setup_state_ref", str(case/"stale-state.json"), "setup_installed_state_response_invalid"),
            ("ownership", "external", "ownership_denied"), ("lifecycle_status", "uninstalled", "move_lifecycle_ineligible")):
            changed = dict(record, **{field: value})
            self.record(case).write_text(json.dumps(changed))
            check(code=code)
            self.record(case).write_bytes(original)
        executable = case/"target/bin/x64/factorio.exe"
        executable.write_bytes(b"damaged owned closure")
        check(code="lifecycle_refused")
        executable.write_bytes(BYTES)
        sentinel = case/"foreign-sentinel"
        sentinel.mkdir()
        (sentinel/"untouched.txt").write_bytes(b"foreign sentinel")
        junction = case/"target/foreign-junction"
        subprocess.run(["cmd", "/c", "mklink", "/J", str(junction), str(sentinel)],
                       check=True, capture_output=True, text=True)
        try:
            check(code="ownership_denied")
        finally:
            os.rmdir(junction)
        destination_junction = case/"destination-junction"
        subprocess.run(["cmd", "/c", "mklink", "/J", str(destination_junction), str(sentinel)],
                       check=True, capture_output=True, text=True)
        try:
            check(destination_junction/"absent", "ownership_denied")
        finally:
            os.rmdir(destination_junction)
        before = snapshot()
        provider = planned["provider_plan"]
        applied = (datetime.datetime.fromisoformat(provider["created_at"].replace("Z", "+00:00")) +
                   datetime.timedelta(seconds=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
        self.run(case, ["installs", "move", "apply", "managed-test", provider["plan_id"],
                        "--target", str(destination), "--digest", provider["plan_digest"],
                        "--plan-created-at", provider["created_at"], "--record-digest", planned["install_record_sha256"],
                        "--transaction-id", "tx-default-move", "--applied-at", applied, "--confirm", "APPLY"],
                 outcome="unavailable", code="live_target_acceptance_required", configured=False)
        assert snapshot() == before and not destination.exists()
        check()

    def interrupt_provider(self, phase="streaming") -> None:
        case = self.case("os-gen" if phase == "genesis" else "os-stream" if phase == "streaming" else "os-stage")
        with zipfile.ZipFile(case/"source.zip", "a", zipfile.ZIP_STORED) as archive:
            with archive.open("factorio/data/harmless-payload.bin", "w") as payload:
                for _ in range(128):
                    payload.write(b"non-executable engineering bytes\n"*4096)
        plan = self.plan(case)
        args = self.apply_args(case, plan)
        command = [str(self.executable), "--workspace", str(case/"workspace"), *args, "--json"]
        journal = case/"setup-state/state/transactions/tx-managed-install.journal.json"
        observed = None
        deadline = time.monotonic()+40
        process = subprocess.Popen(command, env=self.environment(case), stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, text=True)
        try:
            while process.poll() is None and time.monotonic() < deadline:
                try:
                    candidate = shared_journal(journal)
                    stream = candidate.get("recovery_metadata", {}).get("stream_journal", {})
                    eligible = candidate.get("current_state") == "staging"
                    if phase in {"streaming", "genesis"}:
                        eligible = eligible and bool(stream.get("source_context")) and any(
                            entry.get("phase") == "writing" and entry.get("relative_path") == "data/harmless-payload.bin"
                            for entry in stream.get("entries", []))
                    elif phase == "earliest":
                        eligible = eligible and not stream.get("publication_root_identity")
                    if eligible:
                        observed = candidate
                        process.kill()
                        break
                except (OSError, json.JSONDecodeError):
                    pass
                time.sleep(.001)
        finally:
            if process.poll() is None:
                process.kill()
            stdout, stderr = process.communicate(timeout=5)
        self.steps.append({"case": case.name, "command": args, "exit": process.returncode,
                           "actual_process_termination": observed is not None, "stdout": stdout, "stderr": stderr})
        if observed is None:
            raise AssertionError("live provider staging was not observed; this run cannot qualify interruption")
        (case/"interrupted-provider-journal.json").write_text(json.dumps(observed, indent=2))
        staging = next(Path(p["root"]) for p in observed["roots"] if p["role"] == "staging")
        assert staging.resolve().is_relative_to((case/"setup-state").resolve())
        sentinel = case/"workspace/operator-note.txt"
        sentinel.write_text("preserve workspace data after crash")
        saved_journal = digest(journal)
        staging_was_present = staging.exists()
        if phase == "earliest":
            inspection = self.run(case, ["installs", "recovery", "inspect", "tx-managed-install"])
            if inspection["classification"] == "indeterminate":
                self.run(case, ["installs", "recovery", "apply", "tx-managed-install", inspection["plan_id"],
                               "--digest", inspection["plan_digest"], "--confirm", "APPLY"],
                         outcome="recovery_required", code="install_recovery_indeterminate")
                assert digest(journal) == saved_journal and not self.record(case).exists()
                self.open_gaps.append("initial staging can lack durable ownership and stream context; requires provider fix")
                return
            assert inspection["classification"] == "provider_replay_available"
            durable_stream = shared_journal(journal)["recovery_metadata"]["stream_journal"]
            assert durable_stream.get("source_context") and not durable_stream.get("publication_root_identity"), (
                "the actual stop passed initial staging identity publication; no earliest-boundary qualification")
        if phase == "genesis":
            self.interrupt_replay_genesis(case)
            self.recover(case)
            self.verify(case)
            self.recover(case)
            assert digest(journal) == saved_journal and staging.exists()
            self.maintain(case)
            return
        assert phase in {"streaming", "earliest"}
        self.recover(case, "FACMAN_TEST_INSTALL_RECOVERY_INTERRUPT_BEFORE_REPLAY", "provider_replay_available")
        assert staging.exists() == staging_was_present and digest(journal) == saved_journal
        assert not (case/"target").exists() and not self.record(case).exists()
        self.recover(case, "FACMAN_TEST_INSTALL_RECOVERY_INTERRUPT_AFTER_REPLAY", "provider_replay_available")
        assert not self.record(case).exists()
        self.recover(case)
        record = self.verify(case)
        assert record["state_revision"].startswith("tx-replay-")
        self.recover(case)
        assert digest(journal) == saved_journal and staging.exists() == staging_was_present
        assert (case/"target/data/harmless-payload.bin").stat().st_size == 128*4096*len(b"non-executable engineering bytes\n")
        assert sentinel.read_text() == "preserve workspace data after crash"
        assert journal.is_file() and self.record(case).is_file()
        self.maintain(case)

    def interrupt_replay_genesis(self, case: Path) -> None:
        plan = self.run(case, ["installs", "recovery", "inspect", "tx-managed-install"])
        assert plan["classification"] == "provider_replay_available"
        args = ["installs", "recovery", "apply", "tx-managed-install", plan["plan_id"],
                "--digest", plan["plan_digest"], "--confirm", "APPLY"]
        command = [str(self.executable), "--workspace", str(case/"workspace"), *args, "--json"]
        directory = case/"setup-state/state/transactions"
        previous = set(directory.glob("*.journal.json"))
        deadline = time.monotonic()+40
        child_journal = None
        process = subprocess.Popen(command, env=self.environment(case), stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, text=True)
        try:
            while process.poll() is None and time.monotonic() < deadline:
                for path in set(directory.glob("*.journal.json"))-previous:
                    try:
                        candidate = shared_journal(path)
                        stream = candidate.get("recovery_metadata", {}).get("stream_journal", {})
                        if candidate.get("current_state") == "created" and stream.get("restart_origin"):
                            child_journal = path
                            process.kill()
                            break
                    except (OSError, json.JSONDecodeError):
                        pass
                if child_journal is not None:
                    break
                time.sleep(.001)
        finally:
            if process.poll() is None:
                process.kill()
            stdout, stderr = process.communicate(timeout=5)
        self.steps.append({"case": case.name, "command": args, "exit": process.returncode,
                           "actual_process_termination": child_journal is not None, "stdout": stdout, "stderr": stderr})
        assert child_journal is not None, "child replay creation was not observed; no interruption qualification"
        child_sha256 = digest(child_journal)
        restarted = self.run(case, ["installs", "recovery", "inspect", "tx-managed-install"])
        assert restarted["classification"] == "provider_replay_available"
        assert restarted["retained_child_journal_snapshot_sha256"] == child_sha256, (
            "the actual stop passed audit genesis; this run cannot qualify missing-genesis recovery")
        self.run(case, ["installs", "recovery", "apply", "tx-managed-install", restarted["plan_id"],
                       "--digest", restarted["plan_digest"], "--confirm", "APPLY"])
        assert digest(child_journal) == child_sha256
        assert self.record(case).exists() and (case/"target/bin/x64/factorio.exe").read_bytes() == BYTES

    def maintain(self, case: Path) -> None:
        executable = case/"target/bin/x64/factorio.exe"
        foreign = case/"target/operator-note.txt"
        foreign.write_text("preserve foreign content")
        sentinel = case/"workspace/operator-note.txt"
        sentinel.write_text("preserve workspace data")
        executable.write_bytes(b"damaged owned bytes")
        plan = self.run(case, ["installs", "repair", "plan", "managed-test", "--archive", str(case/"source.zip")])
        assert any(p["relative_path"] == "bin/x64/factorio.exe" for p in plan["provider_plan"]["repairs"])
        assert "operator-note.txt" in plan["provider_plan"]["retained_unknown_paths"]
        applied = (datetime.datetime.fromisoformat(plan["created_at"].replace("Z", "+00:00")) +
                   datetime.timedelta(seconds=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
        self.run(case, ["installs", "repair", "apply", "managed-test", plan["plan_id"],
                       "--archive", str(case/"source.zip"), "--digest", plan["plan_digest"],
                       "--plan-created-at", plan["created_at"], "--record-digest", plan["install_record_sha256"],
                       "--transaction-id", "tx-managed-repair", "--applied-at", applied, "--confirm", "APPLY"])
        self.verify(case, verification="warn")
        assert foreign.read_text() == "preserve foreign content"
        plan = self.run(case, ["installs", "uninstall", "plan", "managed-test"])
        applied = (datetime.datetime.fromisoformat(plan["created_at"].replace("Z", "+00:00")) +
                   datetime.timedelta(seconds=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
        self.run(case, ["installs", "uninstall", "apply", "managed-test", plan["plan_id"],
                       "--digest", plan["plan_digest"], "--plan-created-at", plan["created_at"],
                       "--transaction-id", "tx-managed-uninstall", "--applied-at", applied, "--confirm", "APPLY"],
                 outcome="refused", code="foreign_content_review_required")
        assert executable.read_bytes() == BYTES
        assert foreign.read_text() == "preserve foreign content"
        foreign.unlink()  # Remove only this harness's owned note after proving refusal preserves it.
        plan = self.run(case, ["installs", "uninstall", "plan", "managed-test"])
        applied = (datetime.datetime.fromisoformat(plan["created_at"].replace("Z", "+00:00")) +
                   datetime.timedelta(seconds=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
        self.run(case, ["installs", "uninstall", "apply", "managed-test", plan["plan_id"],
                       "--digest", plan["plan_digest"], "--plan-created-at", plan["created_at"],
                       "--transaction-id", "tx-managed-uninstall-clean", "--applied-at", applied, "--confirm", "APPLY"])
        assert not executable.exists()
        assert sentinel.read_text() == "preserve workspace data"
        retired = json.loads(self.record(case).read_text())
        assert retired["lifecycle_status"] == "uninstalled"
        assert retired["safe_actions"] == {"repair": False, "uninstall": False}
        assert Path(retired["setup_state_ref"]).is_file()
        for transaction in ("tx-managed-install", "tx-managed-repair", "tx-managed-uninstall-clean"):
            assert (case/"setup-state/state/transactions"/(transaction+".journal.json")).is_file()

    def exercise(self) -> None:
        case = self.case("authority-refusal")
        plan = {"plan_id": "reviewed-plan", "plan_digest": "0"*64, "created_at": "2026-09-26T00:00:00Z"}
        self.run(case, self.apply_args(case, plan), outcome="unavailable", code="setup_authority_required", configured=False)
        assert not (case/"target").exists() and not (case/"workspace").exists()

        case = self.case("ordinary-install")
        plan = self.plan(case)
        self.run(case, self.apply_args(case, plan))
        record = self.verify(case)
        before = digest(self.record(case)), digest(Path(record["setup_state_ref"]))
        self.run(case, self.apply_args(case, plan), outcome="refused", code="persistent_target_exists")
        assert before == (digest(self.record(case)), digest(Path(record["setup_state_ref"])))
        self.maintain(case)

        case = self.case("source-drift")
        plan = self.plan(case)
        with (case/"source.zip").open("ab") as source:
            source.write(b"source changed after review")
        self.run(case, self.apply_args(case, plan), outcome="refused", code="stale_plan")
        assert not (case/"target").exists() and not (case/"workspace").exists()

        case = self.case("projection-recovery")
        plan = self.plan(case)
        self.run(case, self.apply_args(case, plan), outcome="recovery_required", code="transaction_recovery_required",
                 fault="FACMAN_TEST_INSTALL_INTERRUPT_AFTER_PROVIDER")
        assert not self.record(case).exists() and (case/"target/bin/x64/factorio.exe").read_bytes() == BYTES
        recovery_plan = self.run(case, ["installs", "recovery", "inspect", "tx-managed-install"])
        self.run(case, ["installs", "recovery", "apply", "tx-managed-install", recovery_plan["plan_id"],
                       "--digest", "0"*64, "--confirm", "APPLY"], outcome="refused", code="stale_plan")
        assert not self.record(case).exists()
        lock = case/"workspace/transactions/tx-managed-install.transaction.v1.json.recovery.lock"
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.CreateFileW.argtypes = [ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_uint32,
                                      ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p]
        kernel.CreateFileW.restype = ctypes.c_void_p
        kernel.CloseHandle.argtypes = [ctypes.c_void_p]
        handle = kernel.CreateFileW(str(lock), 0xC0000000, 0, None, 1, 0x80, None)
        if handle == ctypes.c_void_p(-1).value:
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            self.run(case, ["installs", "recovery", "apply", "tx-managed-install", recovery_plan["plan_id"],
                           "--digest", recovery_plan["plan_digest"], "--confirm", "APPLY"],
                     outcome="refused", code="recovery_lock_contended")
            assert not self.record(case).exists()
        finally:
            kernel.CloseHandle(handle)
            lock.unlink()
        self.recover(case, "FACMAN_TEST_INSTALL_RECOVERY_INTERRUPT_AFTER_PROJECTION")
        before = digest(self.record(case))
        recovered = self.recover(case)
        assert recovered["status"] == "completed" and before == digest(self.record(case))
        self.verify(case)
        self.recover(case)
        assert before == digest(self.record(case))

        case = self.case("source-free-recovery")
        plan = self.plan(case)
        self.run(case, self.apply_args(case, plan), outcome="recovery_required", code="transaction_recovery_required",
                 fault="FACMAN_TEST_INSTALL_INTERRUPT_AFTER_PROVIDER")
        (case/"source.zip").unlink()
        self.recover(case)
        self.verify(case)

        case = self.case("target-drift-before-projection")
        plan = self.plan(case)
        self.run(case, self.apply_args(case, plan), outcome="recovery_required", code="transaction_recovery_required",
                 fault="FACMAN_TEST_INSTALL_INTERRUPT_AFTER_PROVIDER")
        executable = case/"target/bin/x64/factorio.exe"
        executable.write_bytes(b"changed after committed provider verification")
        self.run(case, ["installs", "recovery", "inspect", "tx-managed-install"],
                 outcome="conflict", code="setup_install_terminal_target_changed")
        assert not self.record(case).exists()
        assert executable.read_bytes() == b"changed after committed provider verification"
        executable.write_bytes(BYTES)
        self.recover(case)
        self.verify(case)

        case = self.case("no-provider-effect")
        plan = self.plan(case)
        self.run(case, self.apply_args(case, plan), outcome="recovery_required", code="transaction_recovery_required",
                 fault="FACMAN_TEST_INSTALL_INTERRUPT_BEFORE_PROVIDER")
        assert not (case/"target").exists() and not (case/"setup-state").exists()
        self.recover(case, classification="no_provider_effect")
        self.recover(case, classification="no_provider_effect")
        assert not self.record(case).exists() and not (case/"target").exists()

        case = self.case("projection-conflict")
        plan = self.plan(case)
        self.run(case, self.apply_args(case, plan), outcome="recovery_required", code="transaction_recovery_required",
                 fault="FACMAN_TEST_INSTALL_INTERRUPT_AFTER_PROVIDER")
        self.record(case).parent.mkdir(parents=True, exist_ok=True)
        self.record(case).write_text("foreign record; do not replace")
        self.run(case, ["installs", "recovery", "inspect", "tx-managed-install"],
                 outcome="conflict", code="install_recovery_projection_conflict")
        assert self.record(case).read_text() == "foreign record; do not replace"
        assert (case/"target/bin/x64/factorio.exe").read_bytes() == BYTES
        self.interrupt_provider()
        self.interrupt_provider("genesis")
        self.interrupt_provider("earliest")


class OwnedCoordinationProof(PublicInstallProof):
    """Real CLI contenders and process loss, with private job containment."""

    def dispatch(self, case: Path, args: list[str], *, environment=None,
                 workspace=None, timeout=40):
        from tools import provider_canary_process as owned
        command = [str(self.executable), "--workspace", str(workspace or case/"workspace"), *args, "--json"]
        execution = self.root / ("execution-" + str(len(list(self.root.glob("execution-*")))))
        # Parallel calls receive disjoint evidence roots rather than sharing stdout.
        import uuid
        execution = execution.with_name(execution.name + "-" + uuid.uuid4().hex)
        return owned.command(command, cwd=ROOT,
                             environment=environment or self.environment(case),
                             timeout=timeout, directory=execution,
                             wait_for_job_empty_after_primary=False)

    def run(self, case, args, outcome="ok", code="", configured=True, fault=""):
        result = self.dispatch(case, args, environment=self.environment(case, configured, fault))
        if result.receipt["termination"] != "completed" or not result.receipt["job_empty_observed"]:
            raise AssertionError("owned public command failed containment or deadline")
        response = json.loads(result.stdout.decode("utf-8"))
        self.steps.append({"case": case.name, "command": args, "exit": result.returncode,
                           "response": response, "fault": fault,
                           "execution_receipt": str(result.directory/"receipt.json")})
        self.receipt("running")
        if response["outcome"] != outcome or (code and response["payload"].get("refusal", {}).get("code") != code):
            raise AssertionError(f"unexpected coordination result: {response}")
        return response["payload"]

    def snapshot(self, *roots, exclude=()):
        return {(str(root), str(p.relative_to(root))): digest(p)
                for root in roots if root.exists() for p in sorted(root.rglob("*"))
                if p.is_file() and p not in exclude}

    def byte_summary(self, snapshot):
        entries = sorted([root, relative, sha] for (root, relative), sha in snapshot.items())
        return {"file_count": len(entries), "sha256": hashlib.sha256(
            json.dumps(entries, ensure_ascii=False, separators=(",", ":")).encode("utf-8")).hexdigest()}

    def observe_guard(self, case, transaction):
        for path in case.glob(".facman-managed-install-*.lock"):
            try:
                metadata = shared_journal(path)
                if metadata.get("transaction_id") == transaction:
                    return path, metadata
            except (OSError, ValueError):
                pass
        return None

    def guards(self, case):
        return {path.name: hashlib.sha256(shared_bytes(path, 8192)).hexdigest()
                for path in sorted(case.glob(".facman-managed-install-*.lock"))}

    def short_alias(self, path):
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.GetShortPathNameW.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint32]
        kernel.GetShortPathNameW.restype = ctypes.c_uint32
        buffer = ctypes.create_unicode_buffer(32768)
        size = kernel.GetShortPathNameW(str(path), buffer, len(buffer))
        if not size or size >= len(buffer):
            return None
        alias = Path(buffer.value)
        return alias if os.path.samefile(alias, path) else None

    def wait_guard(self, case, transaction, future, *, provider_completed=False):
        deadline = time.monotonic() + 10
        while not future.done() and time.monotonic() < deadline:
            guard = self.observe_guard(case, transaction)
            if guard:
                if not provider_completed:
                    return guard
                journal = case/"setup-state/state/transactions"/(transaction + ".journal.json")
                try:
                    if shared_journal(journal).get("current_state") == "completed":
                        return guard
                except (OSError, ValueError):
                    pass
            time.sleep(0.005)
        raise AssertionError("actual owned mutation lease window was not observed")

    def physical_pending_mutation_loss(self, case, operation):
        transaction = "tx-death-" + operation
        damaged_owned = case/"target/bin/x64/factorio.exe"
        if operation == "repair":
            # Repair planning requires damaged owned input. This is the same
            # harmless fixture file used by the projection contender case.
            assert damaged_owned.read_bytes() == BYTES
            damaged_owned.write_bytes(b"damaged owned bytes before physical death")
        plan_args = ["installs", operation, "plan", "managed-test"]
        if operation == "repair":
            plan_args += ["--archive", str(case/"source.zip")]
        plan = self.run(case, plan_args)
        args = ["installs", operation, "apply", "managed-test", plan["plan_id"],
                "--digest", plan["plan_digest"], "--plan-created-at", plan["created_at"],
                "--transaction-id", transaction, "--applied-at", "2099-01-01T00:00:01Z", "--confirm", "APPLY"]
        if operation == "repair":
            args += ["--archive", str(case/"source.zip"), "--record-digest", plan["install_record_sha256"]]
        product_before = self.snapshot(case/"target", case/"setup-state")
        record_before = self.record(case).read_bytes()
        coordinator = case/"workspace/transactions"/(transaction + ".transaction.v1.json")
        provider_journal = case/"setup-state/state/transactions"/(transaction + ".journal.json")
        environment = self.environment(case, fault="FACMAN_TEST_MANAGED_INSTALL_PAUSE_AFTER_LEASE")
        with ThreadPoolExecutor(max_workers=1) as pool:
            owner = pool.submit(self.dispatch, case, args, environment=environment, timeout=1.2)
            guard, _ = self.wait_guard(case, transaction, owner)
            requested = shared_journal(coordinator)
            assert requested["state"] == "requested" and "provider_entry_started" not in json.dumps(requested)
            assert not provider_journal.exists()
            killed = owner.result()
            assert killed.receipt["termination"] == "command_timeout" and killed.receipt["job_empty_observed"]
        orphan = guard.read_bytes()
        assert self.snapshot(case/"target", case/"setup-state") == product_before
        assert self.record(case).read_bytes() == record_before
        recovery = self.run(case, ["installs", "recovery", "inspect", transaction])
        assert recovery["classification"] == "no_provider_effect" and recovery["action"] == "close_no_provider_effect"
        assert guard.read_bytes() == orphan and shared_journal(coordinator)["state"] == "requested"
        assert self.snapshot(case/"target", case/"setup-state") == product_before
        self.run(case, ["installs", "recovery", "apply", transaction, recovery["plan_id"],
                        "--digest", recovery["plan_digest"], "--confirm", "APPLY"])
        product_after = self.snapshot(case/"target", case/"setup-state")
        assert product_after == product_before and self.record(case).read_bytes() == record_before
        assert not provider_journal.exists() and not guard.exists() and self.guards(case) == {}
        assert shared_journal(coordinator)["state"] == "complete"
        self.steps.append({"case": case.name, "command": args,
                           "execution_receipt": str(killed.directory/"receipt.json"),
                           "product_before": self.byte_summary(product_before),
                           "product_after": self.byte_summary(product_after),
                           "install_record_sha256": hashlib.sha256(record_before).hexdigest(),
                           "requested_orphan_sha256": hashlib.sha256(orphan).hexdigest(),
                           "closed_coordinator_sha256": digest(coordinator),
                           "provider_journal_absent": not provider_journal.exists(),
                           "shared_namespace_after": self.guards(case),
                           "oracle": "physical " + operation + " death retained REQUESTED; ordinary no-effect recovery durably closes with exact product/record bytes"})
        if operation == "repair":
            # Only after the no-effect oracle is recorded, reset our synthetic
            # input for the separate uninstall-death case.
            damaged_owned.write_bytes(BYTES)

    def coordination(self):
        unicode_parent = self.case("p-Ω")
        self.run(unicode_parent, self.apply_args(unicode_parent, self.plan(unicode_parent)))
        self.verify(unicode_parent)
        assert self.guards(unicode_parent) == {}, "Unicode parent changed the shared lease lifecycle"
        unicode_leaf = self.case("ul")
        unicode_environment = self.environment(unicode_leaf)
        unicode_environment["FACMAN_SETUP_STATE_ROOT"] = str(unicode_leaf/"Ω")
        unicode_plan_args = ["installs", "install", "plan", VERSION, "--archive", str(unicode_leaf/"source.zip"),
                             "--target", str(unicode_leaf/"target"), "--id", "managed-test"]
        unicode_planned = self.dispatch(unicode_leaf, unicode_plan_args, environment=unicode_environment)
        unicode_plan_response = json.loads(unicode_planned.stdout.decode("utf-8"))
        assert unicode_planned.ok and unicode_plan_response["outcome"] == "ok", unicode_plan_response
        unicode_apply_args = self.apply_args(unicode_leaf, unicode_plan_response["payload"], "tx-ul")
        unicode_applied = self.dispatch(unicode_leaf, unicode_apply_args, environment=unicode_environment)
        unicode_response = json.loads(unicode_applied.stdout.decode("utf-8"))
        assert unicode_response["outcome"] == "refused" and unicode_response["payload"]["refusal"]["code"] == "setup_plan_path_invalid"
        assert not (unicode_leaf/"Ω").exists() and not (unicode_leaf/"target").exists() and self.guards(unicode_leaf) == {}
        unicode_journal = shared_journal(unicode_leaf/"workspace/transactions/tx-ul.transaction.v1.json")
        assert unicode_journal["state"] == "refused"
        self.steps.extend([
            {"case": unicode_leaf.name, "command": unicode_plan_args, "execution_receipt": str(unicode_planned.directory/"receipt.json")},
            {"case": unicode_leaf.name, "command": unicode_apply_args, "response": unicode_response,
             "execution_receipt": str(unicode_applied.directory/"receipt.json"),
             "oracle": "unsupported Unicode first-root leaf creates no shared cell/provider root/target"},
        ])
        # A long but otherwise valid parent cannot create an oversized orphan.
        oversized = self.case("mb")
        deep = oversized
        for index in range(42):
            deep /= f"parent-{index:02d}-" + "a"*90
            Path("\\\\?\\" + str(deep)).mkdir()
        oversized_environment = self.environment(oversized)
        oversized_environment["FACMAN_SETUP_STATE_ROOT"] = str(deep/"setup-state")
        oversized_plan_args = ["installs", "install", "plan", VERSION, "--archive", str(oversized/"source.zip"),
                               "--target", str(deep/"target"), "--id", "managed-test"]
        oversized_planned = self.dispatch(oversized, oversized_plan_args, environment=oversized_environment,
                                         workspace=deep/"workspace")
        oversized_plan_response = json.loads(oversized_planned.stdout.decode("utf-8"))
        if oversized_plan_response["outcome"] == "unavailable":
            assert oversized_plan_response["payload"]["refusal"]["code"] == "native_path_limit_exceeded"
            assert oversized_plan_response["effects"] == []
            assert not oversized_plan_response["operation"]["effects_may_have_occurred"]
            assert not (deep/"setup-state").exists() and not (deep/"target").exists()
            assert not (deep/"workspace/transactions").exists() and self.guards(deep) == {}
            self.open_gaps.append("Windows provider path policy refuses before the prospective 8192-byte shared metadata limit can be reached")
            self.steps.append({"case": oversized.name, "command": oversized_plan_args,
                               "response": oversized_plan_response,
                               "execution_receipt": str(oversized_planned.directory/"receipt.json"),
                               "oracle": "actual provider path-policy refusal before coordinator/shared cell/provider entry; metadata bound unexecuted"})
        else:
            assert oversized_planned.ok and oversized_plan_response["outcome"] == "ok", oversized_plan_response
            oversized_apply_args = self.apply_args(oversized, oversized_plan_response["payload"], "tx-mb")
            oversized_apply_args[oversized_apply_args.index(str(oversized/"target"))] = str(deep/"target")
            oversized_applied = self.dispatch(oversized, oversized_apply_args, environment=oversized_environment,
                                             workspace=deep/"workspace")
            oversized_response = json.loads(oversized_applied.stdout.decode("utf-8"))
            assert oversized_response["outcome"] == "refused" and oversized_response["payload"]["refusal"]["code"] == "setup_plan_path_invalid"
            assert not (deep/"setup-state").exists() and not (deep/"target").exists() and self.guards(deep) == {}
            assert shared_journal(deep/"workspace/transactions/tx-mb.transaction.v1.json")["state"] == "refused"
            self.steps.extend([
                {"case": oversized.name, "command": oversized_plan_args, "execution_receipt": str(oversized_planned.directory/"receipt.json")},
                {"case": oversized.name, "command": oversized_apply_args, "response": oversized_response,
                 "execution_receipt": str(oversized_applied.directory/"receipt.json"),
                 "oracle": "prospective metadata over 8192 bytes refuses before shared cell/provider root/target"},
            ])
        # A valid terminal retry can become stale before its new cell is taken.
        # Observe the new cell only after the competing operation has completed.
        race = self.case("tr")
        self.run(race, self.apply_args(race, self.plan(race)))
        terminal_review = self.run(race, ["installs", "recovery", "inspect", "tx-managed-install"])
        removal = self.run(race, ["installs", "uninstall", "plan", "managed-test"])
        removal_args = ["installs", "uninstall", "apply", "managed-test", removal["plan_id"],
                        "--digest", removal["plan_digest"], "--plan-created-at", removal["created_at"],
                        "--transaction-id", "tx-tr", "--applied-at", "2099-01-01T00:00:01Z",
                        "--confirm", "APPLY"]
        retry_args = ["installs", "recovery", "apply", "tx-managed-install", terminal_review["plan_id"],
                      "--digest", terminal_review["plan_digest"], "--confirm", "APPLY"]
        retry_environment = self.environment(race)
        retry_environment.update(FACMAN_TEST_MANAGED_INSTALL_RECOVERY_PAUSE_BEFORE_LEASE="1",
                                 FACMAN_TEST_MANAGED_INSTALL_RECOVERY_PAUSE_AFTER_LEASE="1")
        terminal_journal = race/"workspace/transactions/tx-managed-install.transaction.v1.json"
        terminal_before = terminal_journal.read_bytes()
        with ThreadPoolExecutor(max_workers=1) as pool:
            retry = pool.submit(self.dispatch, race, retry_args, environment=retry_environment)
            transaction_guard = Path(str(terminal_journal) + ".recovery.lock")
            deadline = time.monotonic() + 10
            while not transaction_guard.exists() and not retry.done() and time.monotonic() < deadline:
                time.sleep(0.005)
            assert transaction_guard.exists(), "terminal retry transaction window was not observed"
            self.run(race, removal_args)
            # This exact observed owner's transient transaction guard is held
            # exclusively on Windows; its removal is asserted separately.
            changed_generation = self.snapshot(race/"target", race/"setup-state", race/"workspace",
                                               exclude=(transaction_guard,))
            new_guard, _ = self.wait_guard(race, "tx-managed-install", retry)
            assert not (race/"target").exists()
            assert shared_journal(race/"setup-state/state/transactions/tx-tr.journal.json")["current_state"] == "completed"
            rejected = retry.result()
            rejected_response = json.loads(rejected.stdout.decode("utf-8"))
            assert rejected_response["outcome"] != "ok", rejected_response
            assert not new_guard.exists() and self.guards(race) == {}, "stale under-lease terminal retry retained its new cell"
            assert terminal_journal.read_bytes() == terminal_before
            assert not transaction_guard.exists()
            assert self.snapshot(race/"target", race/"setup-state", race/"workspace") == changed_generation
            self.steps.append({"case": race.name, "command": retry_args, "response": rejected_response,
                               "execution_receipt": str(rejected.directory/"receipt.json"),
                               "generation_before": self.byte_summary(changed_generation),
                               "generation_after": self.byte_summary(self.snapshot(race/"target", race/"setup-state", race/"workspace")),
                               "terminal_journal_before_sha256": hashlib.sha256(terminal_before).hexdigest(),
                               "terminal_journal_after_sha256": digest(terminal_journal),
                               "transient_transaction_guard_removed": not transaction_guard.exists(),
                               "shared_namespace_after": self.guards(race),
                               "oracle": "observed new terminal retry cell after different operation completed; refusal releases only that new cell"})
        case = self.case("c")
        self.run(case, self.apply_args(case, self.plan(case)))
        foreign = case/"target/operator-note.txt"
        foreign.write_text("foreign bytes remain", encoding="utf-8")
        executable = case/"target/bin/x64/factorio.exe"
        executable.write_bytes(b"damaged owned bytes")
        record_before = self.record(case).read_bytes()
        other_workspace = case/"other-workspace"
        imported = self.dispatch(case, ["installs", "import", str(case/"target"), "--id", "managed-test"],
                                 workspace=other_workspace)
        assert imported.ok
        other_record = other_workspace/"installs/refs/managed-test.json"
        other_record.write_bytes(record_before)  # Owned synthetic registry fixture only.
        repair = self.run(case, ["installs", "repair", "plan", "managed-test", "--archive", str(case/"source.zip")])
        uninstall = self.run(case, ["installs", "uninstall", "plan", "managed-test"])
        repair_args = ["installs", "repair", "apply", "managed-test", repair["plan_id"],
                       "--archive", str(case/"source.zip"), "--digest", repair["plan_digest"],
                       "--plan-created-at", repair["created_at"], "--record-digest", repair["install_record_sha256"],
                       "--transaction-id", "tx-c-repair", "--applied-at", "2098-01-01T00:00:01Z",
                       "--confirm", "APPLY"]
        uninstall_args = ["installs", "uninstall", "apply", "managed-test", uninstall["plan_id"],
                          "--digest", uninstall["plan_digest"], "--plan-created-at", uninstall["created_at"],
                          "--transaction-id", "tx-c-uninstall", "--applied-at", "2099-01-01T00:00:01Z",
                          "--confirm", "APPLY"]
        environment = self.environment(case, fault="FACMAN_TEST_MANAGED_INSTALL_PAUSE_BEFORE_PROJECTION")
        with ThreadPoolExecutor(max_workers=1) as pool:
            owner = pool.submit(self.dispatch, case, repair_args, environment=environment)
            guard, metadata = self.wait_guard(case, "tx-c-repair", owner, provider_completed=True)
            assert metadata["command_id"] == "installs.repair.apply"
            assert self.record(case).read_bytes() == record_before and executable.read_bytes() == BYTES
            guarded = self.snapshot(case/"target", case/"setup-state")
            guarded_namespace = self.guards(case)
            contender = self.dispatch(case, uninstall_args, workspace=other_workspace)
            response = json.loads(contender.stdout.decode("utf-8"))
            assert response["payload"]["refusal"]["code"] == "recovery_lock_contended", response
            assert self.snapshot(case/"target", case/"setup-state") == guarded
            assert self.guards(case) == guarded_namespace
            assert self.record(case).read_bytes() == record_before and other_record.read_bytes() == record_before
            assert self.observe_guard(case, "tx-c-repair")[1] == metadata
            refused_journal = shared_journal(other_workspace/"transactions/tx-c-uninstall.transaction.v1.json")
            assert refused_journal["state"] == "refused"
            assert "provider_entry_started" not in json.dumps(refused_journal)
            assert not (case/"setup-state/state/transactions/tx-c-uninstall.journal.json").exists()
            alias_environment = self.environment(case)
            state_alias = self.short_alias(case/"setup-state")
            alias_environment["FACMAN_SETUP_STATE_ROOT"] = str(state_alias or case/"setup-state").upper()
            alias_args = uninstall_args.copy()
            alias_args[alias_args.index("tx-c-uninstall")] = "tx-c-uninstall-alias"
            alias = self.dispatch(case, alias_args, workspace=Path(str(other_workspace).upper()),
                                  environment=alias_environment)
            alias_response = json.loads(alias.stdout.decode("utf-8"))
            assert alias_response["payload"]["refusal"]["code"] == "recovery_lock_contended", alias_response
            assert self.guards(case) == guarded_namespace and self.snapshot(case/"target", case/"setup-state") == guarded
            self.steps.append({"case": case.name, "command": alias_args, "response": alias_response,
                               "execution_receipt": str(alias.directory/"receipt.json"),
                               "existing_8dot3_alias_available": state_alias is not None and str(state_alias).casefold() != str(case/"setup-state").casefold(),
                               "oracle": "Windows case and available 8.3 aliases share the same guard"})
            self.steps.append({"case": case.name, "command": uninstall_args, "response": response,
                               "execution_receipt": str(contender.directory/"receipt.json"),
                               "product_before": self.byte_summary(guarded),
                               "product_after": self.byte_summary(self.snapshot(case/"target", case/"setup-state")),
                               "shared_namespace_before": guarded_namespace,
                               "shared_namespace_after": self.guards(case),
                               "owner_record_sha256": hashlib.sha256(record_before).hexdigest(),
                               "contender_refused_journal_sha256": digest(other_workspace/"transactions/tx-c-uninstall.transaction.v1.json"),
                               "oracle": "provider complete; FacMan preimage unchanged; competing workspace no entry"})
            result = owner.result()
            assert result.ok and json.loads(result.stdout.decode("utf-8"))["outcome"] == "ok"
            self.steps.append({"case": case.name, "command": repair_args,
                               "execution_receipt": str(result.directory/"receipt.json")})
        assert not guard.exists() and foreign.read_text(encoding="utf-8") == "foreign bytes remain"
        assert self.record(case).read_bytes() != record_before
        stale = repair_args.copy()
        stale[stale.index("tx-c-repair")] = "tx-c-stale"
        before_stale = self.snapshot(case/"target", case/"setup-state", case/"workspace")
        self.run(case, stale, outcome="conflict", code="managed_install_record_preimage_changed")
        assert self.snapshot(case/"target", case/"setup-state", case/"workspace") == before_stale
        terminal_plan = self.run(case, ["installs", "recovery", "inspect", "tx-c-repair"])
        self.run(case, ["installs", "recovery", "apply", "tx-c-repair", terminal_plan["plan_id"],
                       "--digest", "0"*64, "--confirm", "APPLY"], outcome="refused", code="stale_plan")
        assert self.guards(case) == {}, "invalid terminal recovery poisoned a clean installation"
        assert self.snapshot(case/"target", case/"setup-state", case/"workspace") == before_stale

        self.physical_pending_mutation_loss(case, "repair")
        self.physical_pending_mutation_loss(case, "uninstall")

        # Physical owner death in the shared-lock metadata / requested-journal window.
        case = self.case("od")
        plan = self.plan(case)
        args = self.apply_args(case, plan, "tx-c-death")
        environment = self.environment(case, fault="FACMAN_TEST_MANAGED_INSTALL_PAUSE_AFTER_LEASE")
        with ThreadPoolExecutor(max_workers=1) as pool:
            owner = pool.submit(self.dispatch, case, args, environment=environment, timeout=1.2)
            guard, metadata = self.wait_guard(case, "tx-c-death", owner)
            journal = case/"workspace/transactions/tx-c-death.transaction.v1.json"
            assert shared_journal(journal)["state"] == "requested"
            assert not (case/"target").exists() and not (case/"setup-state").exists()
            killed = owner.result()
            assert killed.receipt["termination"] == "command_timeout" and killed.receipt["job_empty_observed"]
            self.steps.append({"case": case.name, "command": args,
                               "execution_receipt": str(killed.directory/"receipt.json"),
                               "oracle": "observed requested journal and exact shared metadata before contained physical termination"})
        assert self.observe_guard(case, "tx-c-death")[1] == metadata
        orphan_bytes = guard.read_bytes()
        recovery = self.run(case, ["installs", "recovery", "inspect", "tx-c-death"])
        assert recovery["classification"] == "no_provider_effect"
        guard.write_bytes(orphan_bytes + b"\n")
        format_edit = guard.read_bytes()
        self.run(case, ["installs", "recovery", "apply", "tx-c-death", recovery["plan_id"],
                        "--digest", recovery["plan_digest"], "--confirm", "APPLY"],
                 outcome="recovery_required", code="recovery_write_refused")
        assert guard.read_bytes() == format_edit, "pre-adoption whitespace edit was relabelled owned"
        changed_metadata = dict(metadata, command_id="installs.uninstall.apply")
        guard.write_text(json.dumps(changed_metadata) + "\n", encoding="utf-8")
        changed_bytes = guard.read_bytes()
        self.run(case, ["installs", "recovery", "apply", "tx-c-death", recovery["plan_id"],
                        "--digest", recovery["plan_digest"], "--confirm", "APPLY"],
                 outcome="recovery_required", code="recovery_write_refused")
        assert guard.read_bytes() == changed_bytes, "changed ownership metadata was removed"
        guard.write_bytes(orphan_bytes)  # Restore only this harness's exact owner fixture.
        owner_recovery_args = ["installs", "recovery", "apply", "tx-c-death", recovery["plan_id"],
                               "--digest", recovery["plan_digest"], "--confirm", "APPLY"]
        owner_alias = self.short_alias(case/"workspace")
        alias_owner = self.dispatch(case, owner_recovery_args, workspace=Path(str(owner_alias or case/"workspace").upper()))
        alias_owner_response = json.loads(alias_owner.stdout.decode("utf-8"))
        assert alias_owner.ok and alias_owner_response["outcome"] == "ok", alias_owner_response
        self.steps.append({"case": case.name, "command": owner_recovery_args, "response": alias_owner_response,
                           "execution_receipt": str(alias_owner.directory/"receipt.json"),
                           "oracle": "matching physical owner workspace case alias safely adopts and closes orphan"})
        assert not guard.exists() and not (case/"target").exists() and not self.record(case).exists()
        assert self.guards(case) == {}

        # Foreign/torn lock content is never rewritten or removed by admission.
        guard.write_bytes(b"foreign torn metadata\n")
        refused_args = self.apply_args(case, plan, "tx-c-foreign")
        before_foreign = guard.read_bytes()
        self.run(case, refused_args, outcome="refused", code="recovery_lock_contended")
        assert guard.read_bytes() == before_foreign and not (case/"target").exists()
        refused_journal = shared_journal(case/"workspace/transactions/tx-c-foreign.transaction.v1.json")
        assert refused_journal["state"] == "refused"
        assert not (case/"setup-state/state/transactions/tx-c-foreign.journal.json").exists()
        foreign_plan = self.run(case, ["installs", "recovery", "inspect", "tx-c-foreign"])
        recovery_args = ["installs", "recovery", "apply", "tx-c-foreign", foreign_plan["plan_id"],
                         "--digest", foreign_plan["plan_digest"], "--confirm", "APPLY"]
        self.run(case, recovery_args, outcome="recovery_required", code="recovery_write_refused")
        assert guard.read_bytes() == before_foreign
        guard.unlink()  # This harness's exact proved foreign fixture only.
        self.receipt("running")


class OwnedMoveProof(OwnedCoordinationProof):
    """Separate CLI/RPC handoff, exact reference CAS and bounded move recovery."""

    def dispatch(self, case, args, *, environment=None, workspace=None, timeout=40):
        from tools import provider_canary_process as owned
        import uuid
        result = owned.command([str(self.executable), "--workspace", str(workspace or case/"workspace"),
                                *args, "--json"], cwd=ROOT,
                               environment=environment or self.environment(case), timeout=timeout,
                               directory=self.root/("execution-move-"+uuid.uuid4().hex),
                               wait_for_job_empty_after_primary=True)
        if result.receipt["termination"] == "completed":
            assert result.receipt["primary_stopped"] and result.receipt["job_empty_observed"]
            assert not result.receipt["job_terminated"] and result.receipt["waited_for_job_empty_after_primary"]
        return result

    def inventory(self, case):
        entries = {}
        pending = [case]
        while pending:
            directory = pending.pop()
            for path in sorted(directory.iterdir()):
                status = path.lstat()
                key = path.relative_to(case).as_posix()
                assert not path.is_symlink() and not getattr(status, "st_file_attributes", 0) & 0x400
                if path.is_dir():
                    entries[key] = ["directory"]
                    pending.append(path)
                else:
                    entries[key] = ["file", status.st_size, digest(path)]
        return entries

    def prepare_move(self, name):
        case = self.case(name)
        self.run(case, self.apply_args(case, self.plan(case)))
        self.verify(case)
        (case/"target/foreign-user.txt").write_bytes(b"foreign bytes remain foreign")
        (case/"target/.facman-transaction-staging.v2.json").write_bytes(b"foreign marker-shaped sentinel")
        (case/"target/empty-user-directory").mkdir()
        destination = case/"destination"
        preview = self.run(case, ["installs", "move", "plan", "managed-test", "--target", str(destination)])
        provider = preview["provider_plan"]
        assert preview["install_record_sha256"] == digest(self.record(case))
        args = ["installs", "move", "apply", "managed-test", provider["plan_id"], "--target", str(destination),
                "--digest", provider["plan_digest"], "--plan-created-at", provider["created_at"],
                "--record-digest", preview["install_record_sha256"], "--transaction-id", "tx-public-move",
                "--applied-at", "2099-01-01T00:00:01Z", "--confirm", "APPLY"]
        return case, destination, preview, args

    def retained_source(self, case):
        return self.inventory(case/"target"), digest(case/"source.zip")

    def assert_projection(self, case, destination, original):
        record = json.loads(self.record(case).read_bytes())
        prior = json.loads(original)
        assert Path(record["root"]) == Path(record["app_dir"]) == destination
        assert Path(record["executable"]) == destination/"bin/x64/factorio.exe"
        assert record["lifecycle_status"] == "move_pending_acceptance"
        assert record["safe_actions"] == {"repair": False, "uninstall": False}
        for key in ("source_ref", "source", "ownership", "provider_id", "version", "platform_integration",
                    "strict_isolation_eligibility", "distribution_origin"):
            if key in prior:
                assert record[key] == prior[key], key
        state = json.loads(Path(record["setup_state_ref"]).read_bytes())
        old_state = json.loads(Path(prior["setup_state_ref"]).read_bytes())
        assert Path(state["target_root"]) == destination
        assert state["transaction_id"] == "tx-public-move" and state["lifecycle_status"] == "move_pending_acceptance"
        assert record["state_revision"] == state["transaction_id"]+":"+state["ownership_manifest_digest"]
        assert record["last_verification_identity"] == state["last_verification"]["report_digest"]
        old_owned = json.loads((case/"setup-state/state"/old_state["ownership_manifest_ref"]).read_bytes())
        new_owned = json.loads((case/"setup-state/state"/state["ownership_manifest_ref"]).read_bytes())
        assert old_owned["files"] == new_owned["files"] and old_owned["directories"] == new_owned["directories"]
        assert "foreign-user.txt" not in {row["relative_path"] for row in new_owned["files"]}
        assert (destination/"foreign-user.txt").read_bytes() == b"foreign bytes remain foreign"
        assert (destination/".facman-transaction-staging.v2.json").read_bytes() == b"foreign marker-shaped sentinel"
        assert self.guards(case) == {}
        before_reload = self.inventory(case)
        reloaded = self.run(case, ["installs", "list"])["install_refs"]
        selected = next(row for row in reloaded if row["install_id"] == "managed-test")
        assert Path(selected["root"]) == Path(selected["app_dir"]) == destination
        assert Path(selected["executable"]) == destination/"bin/x64/factorio.exe"
        assert selected["setup_state_ref"] == record["setup_state_ref"]
        assert self.inventory(case) == before_reload
        return record

    def move_retry_rpc(self, case, args):
        from tools import provider_canary_process as owned
        import uuid
        values = dict(zip(args[5::2], args[6::2]))
        request = {"schema": "facman.transport_request.v2", "protocol_version": 2,
                   "request_id": "req-move-retry", "operation_id": "op-move-retry", "attempt_id": "attempt-move-retry",
                   "command": "installs.move.apply", "workspace": str(case/"workspace"), "dry_run": False,
                   "payload": {"install_id": args[3], "plan_id": args[4], "target_root": values["--target"],
                               "plan_digest": values["--digest"], "plan_created_at": values["--plan-created-at"],
                               "install_record_sha256": values["--record-digest"], "transaction_id": values["--transaction-id"],
                               "applied_at": values["--applied-at"], "confirmation": "APPLY"}}
        before = self.inventory(case)
        result = owned.command([str(self.executable), "rpc", "--stdio"], cwd=ROOT,
                               environment=self.environment(case), input_bytes=(json.dumps(request)+"\n").encode(),
                               timeout=40, directory=self.root/("execution-rpc-"+uuid.uuid4().hex),
                               wait_for_job_empty_after_primary=True)
        response = json.loads(result.stdout)
        assert result.ok and result.receipt["job_empty_observed"] and not result.receipt["job_terminated"]
        assert response["outcome"] == "ok" and response["payload"]["lifecycle_status"] == "move_pending_acceptance"
        assert self.inventory(case) == before
        self.steps.append({"case": case.name, "command": ["rpc", "--stdio"], "request": request,
                           "response": response, "execution_receipt": str(result.directory/"receipt.json"),
                           "oracle": "identical completed handoff; complete tree unchanged"})
        self.receipt("running")

    def moves(self):
        case, destination, preview, args = self.prepare_move("move-positive")
        original = self.record(case).read_bytes()
        source_before = self.retained_source(case)
        for change in ("record", "source", "destination", "owned"):
            if change == "record": self.record(case).write_bytes(original+b" ")
            if change == "source": (case/"target/foreign-user.txt").write_bytes(b"drift")
            if change == "destination": destination.mkdir()
            if change == "owned": (case/"target/bin/x64/factorio.exe").write_bytes(b"damaged owned file")
            before = self.inventory(case)
            self.run(case, args, outcome="refused", code={"record": "stale_plan", "source": "stale_plan",
                     "destination": "invalid_argument", "owned": "lifecycle_refused"}[change])
            assert self.inventory(case) == before
            if change == "record": self.record(case).write_bytes(original)
            if change == "source": (case/"target/foreign-user.txt").write_bytes(b"foreign bytes remain foreign")
            if change == "destination": destination.rmdir()
            if change == "owned": (case/"target/bin/x64/factorio.exe").write_bytes(BYTES)
        from tools import provider_canary_process as owned
        import uuid
        human = owned.command([str(self.executable), "--workspace", str(case/"workspace"), *args], cwd=ROOT,
                              environment=self.environment(case), timeout=40,
                              directory=self.root/("execution-human-"+uuid.uuid4().hex),
                              wait_for_job_empty_after_primary=True)
        text = human.stdout.decode()
        assert human.ok and human.receipt["job_empty_observed"] and not human.receipt["job_terminated"]
        assert all(part in text for part in ("new root verified", "Old source (retained):", "New root:",
                   "move_pending_acceptance", "launch remains ineligible", "Foreign copied content remains foreign"))
        self.steps.append({"case": case.name, "command": args, "format": "human", "stdout": text,
                           "execution_receipt": str(human.directory/"receipt.json")})
        assert self.retained_source(case) == source_before
        self.assert_projection(case, destination, original)
        before_retry = self.inventory(case)
        self.run(case, args)
        assert self.inventory(case) == before_retry
        self.move_retry_rpc(case, args)
        self.assert_projection(case, destination, original)

        # Durable entry intent without a provider dispatch is still unproved, even with absent paths.
        case, destination, preview, args = self.prepare_move("move-entry-unproved")
        self.run(case, args, outcome="recovery_required", code="transaction_recovery_required",
                 fault="FACMAN_TEST_MOVE_INTERRUPT_BEFORE_PROVIDER")
        before = self.inventory(case)
        recovery = self.run(case, ["installs", "recovery", "inspect", "tx-public-move"])
        assert (recovery["classification"], recovery["action"], recovery["status"]) == ("indeterminate", "none", "blocked")
        import jsonschema
        move_schema = json.loads((ROOT/"contracts/schema/factorio/facman_managed_move_recovery.v1.schema.json").read_bytes())
        shared_schema = json.loads((ROOT/"contracts/schema/factorio/facman_managed_install_recovery.v1.schema.json").read_bytes())
        jsonschema.Draft202012Validator(move_schema).validate(recovery)
        jsonschema.Draft202012Validator(shared_schema).validate(recovery)
        assert not destination.exists()
        assert not (case/"setup-state/state/transactions/tx-public-move.journal.json").exists()
        self.run(case, ["installs", "recovery", "apply", "tx-public-move", recovery["plan_id"],
                       "--digest", recovery["plan_digest"], "--confirm", "APPLY"],
                 outcome="recovery_required", code="move_recovery_indeterminate")
        assert self.inventory(case) == before

        # Both post-provider windows: exact preimage and exact already-projected postimage.
        for fault in ("FACMAN_TEST_MOVE_INTERRUPT_AFTER_PROVIDER", "FACMAN_TEST_MOVE_INTERRUPT_AFTER_PROJECTION"):
            case, destination, preview, args = self.prepare_move("move-"+fault.rsplit("_", 1)[1].lower())
            original = self.record(case).read_bytes()
            source_before = self.retained_source(case)
            self.run(case, args, outcome="recovery_required", code="transaction_recovery_required", fault=fault)
            assert self.retained_source(case) == source_before
            provider_before = self.inventory(case/"setup-state")
            recovery = self.run(case, ["installs", "recovery", "inspect", "tx-public-move"])
            assert recovery["classification"] == "provider_move_completed" and recovery["action"] == "project_terminal"
            recovery_args = ["installs", "recovery", "apply", "tx-public-move", recovery["plan_id"],
                             "--digest", recovery["plan_digest"], "--confirm", "APPLY"]
            stale = recovery_args.copy(); stale[stale.index("--digest")+1] = "0"*64
            before = self.inventory(case)
            self.run(case, stale, outcome="refused", code="stale_plan")
            assert self.inventory(case) == before
            current = self.record(case).read_bytes()
            self.record(case).write_bytes(current+b" ")
            before = self.inventory(case)
            self.run(case, ["installs", "recovery", "inspect", "tx-public-move"],
                     outcome="conflict", code="move_recovery_projection_conflict")
            assert self.inventory(case) == before
            self.record(case).write_bytes(current)
            foreign = destination/"foreign-user.txt"; foreign.write_bytes(b"destination drift")
            before = self.inventory(case)
            self.run(case, ["installs", "recovery", "inspect", "tx-public-move"],
                     outcome="refused", code="setup_move_evidence_invalid")
            assert self.inventory(case) == before
            foreign.write_bytes(b"foreign bytes remain foreign")
            self.run(case, recovery_args)
            assert self.inventory(case/"setup-state") == provider_before and self.retained_source(case) == source_before
            self.assert_projection(case, destination, original)
            before = self.inventory(case)
            self.run(case, recovery_args)
            self.run(case, args)
            assert self.inventory(case) == before
            self.assert_projection(case, destination, original)

        # Real process loss at observed REQUESTED before provider entry; shared cross-workspace contention.
        case, destination, preview, args = self.prepare_move("move-requested")
        original = self.record(case).read_bytes()
        imported = self.dispatch(case, ["installs", "import", str(case/"target"), "--id", "managed-test"],
                                 workspace=case/"other-workspace")
        assert imported.ok
        other_record = case/"other-workspace/installs/refs/managed-test.json"
        other_record.write_bytes(original)
        provider_before = self.inventory(case/"setup-state")
        source_before = self.retained_source(case)
        environment = self.environment(case, fault="FACMAN_TEST_MANAGED_INSTALL_PAUSE_AFTER_LEASE")
        with ThreadPoolExecutor(max_workers=1) as pool:
            owner = pool.submit(self.dispatch, case, args, environment=environment, timeout=1.2)
            guard, metadata = self.wait_guard(case, "tx-public-move", owner)
            journal = case/"workspace/transactions/tx-public-move.transaction.v1.json"
            requested = shared_journal(journal)
            assert requested["state"] == "requested" and "provider_entry_started" not in json.dumps(requested)
            assert not (case/"setup-state/state/transactions/tx-public-move.journal.json").exists()
            contender_args = args.copy(); contender_args[contender_args.index("--transaction-id")+1] = "tx-other-move"
            contender = self.dispatch(case, contender_args, workspace=case/"other-workspace")
            response = json.loads(contender.stdout)
            assert response["outcome"] == "refused" and response["payload"]["refusal"]["code"] == "recovery_lock_contended"
            self.steps.append({"case": case.name, "command": contender_args, "response": response,
                               "execution_receipt": str(contender.directory/"receipt.json"),
                               "oracle": "same provider-state/install key contends across distinct FacMan workspaces"})
            killed = owner.result()
            assert killed.receipt["termination"] == "command_timeout" and killed.receipt["job_empty_observed"]
            self.steps.append({"case": case.name, "command": args, "intentional_interruption": "observed REQUESTED owner process loss",
                               "execution_receipt": str(killed.directory/"receipt.json"), "requested": requested,
                               "orphan_guard_sha256": digest(guard), "member_metadata": metadata})
        assert self.inventory(case/"setup-state") == provider_before and self.retained_source(case) == source_before
        assert not destination.exists() and self.record(case).read_bytes() == original
        recovery = self.run(case, ["installs", "recovery", "inspect", "tx-public-move"])
        assert recovery["classification"] == "no_provider_effect" and recovery["action"] == "close_no_provider_effect"
        recovery_args = ["installs", "recovery", "apply", "tx-public-move", recovery["plan_id"],
                         "--digest", recovery["plan_digest"], "--confirm", "APPLY"]
        self.run(case, recovery_args)
        assert self.guards(case) == {} and self.record(case).read_bytes() == original and not destination.exists()
        assert self.inventory(case/"setup-state") == provider_before and self.retained_source(case) == source_before
        before = self.inventory(case)
        self.run(case, recovery_args)
        assert self.inventory(case) == before


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--facman", type=Path, required=True)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--scenario", choices=["all", "streaming", "genesis", "earliest", "verification", "coordination", "move-preview", "move-apply"], default="all")
    args = parser.parse_args()
    if os.name != "nt":
        parser.error("this proof covers the admitted Windows portable ZIP recipe")
    proof_type = OwnedMoveProof if args.scenario == "move-apply" else OwnedCoordinationProof if args.scenario == "coordination" else PublicInstallProof
    proof = proof_type(args.facman, args.root)
    try:
        if args.scenario == "move-apply":
            proof.moves()
        elif args.scenario == "coordination":
            proof.coordination()
        elif args.scenario == "move-preview":
            proof.move_preview()
        elif args.scenario == "verification":
            proof.verification()
        elif args.scenario != "all":
            proof.interrupt_provider(args.scenario)
        else:
            proof.exercise()
    except Exception:
        proof.receipt("fail")
        raise
    result = "partial" if proof.open_gaps else "pass"
    proof.receipt(result)
    print(f"managed-install-public-proof: {result} ({len(proof.steps)} fresh CLI processes; scope={args.scenario})")
    return 1 if proof.open_gaps else 0


if __name__ == "__main__":
    raise SystemExit(main())
