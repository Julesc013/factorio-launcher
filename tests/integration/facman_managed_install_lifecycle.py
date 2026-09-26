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
import zipfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools import development_layout  # noqa: E402

VERSION = "2.0.77"
BYTES = b"harmless non-executable fixture bytes"


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def shared_journal(path: Path) -> dict:
    """Observe atomic journal replacement without introducing Windows sharing failures."""
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
        data = stream.read(4*1024*1024+1)
    if len(data) > 4*1024*1024:
        raise ValueError("provider journal exceeds the proof's observation bound")
    return json.loads(data)


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
        (self.root/"receipt.json").write_text(json.dumps(document, indent=2))

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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--facman", type=Path, required=True)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--scenario", choices=["all", "streaming", "genesis", "earliest"], default="all")
    args = parser.parse_args()
    if os.name != "nt":
        parser.error("this proof covers the admitted Windows portable ZIP recipe")
    proof = PublicInstallProof(args.facman, args.root)
    try:
        if args.scenario != "all":
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
