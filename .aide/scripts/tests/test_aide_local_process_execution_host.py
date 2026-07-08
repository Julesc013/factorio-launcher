from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.execution import local_process_host as host


def write_text(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def run_git(root: Path, *args: str) -> str:
    result = subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True, text=True, shell=False)
    return result.stdout.strip()


def create_aide_fixture(root: Path) -> str:
    root.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", str(root)], check=True, capture_output=True, text=True, shell=False)
    run_git(root, "config", "user.email", "aide-tests@example.invalid")
    run_git(root, "config", "user.name", "AIDE Tests")
    source_worker = REPO_ROOT / host.FIXTURE_WORKER_REL
    write_text(root, host.FIXTURE_WORKER_REL.as_posix(), source_worker.read_text(encoding="utf-8"))
    write_text(root, host.HOST_MODULE_REL.as_posix(), "fixture local_process_host module\n")
    write_text(root, host.PROVIDER_REL.as_posix(), "fixture registered process provider\n")
    write_text(root, host.PROCESS_INVOCATION_REL.as_posix(), "fixture process invocation\n")
    write_text(root, host.EXECUTION_RECEIPT_REL.as_posix(), "fixture execution receipt\n")
    write_text(root, host.AIDE_LITE_REL.as_posix(), "fixture aide lite\n")
    run_git(root, "add", ".")
    run_git(root, "commit", "-m", "fixture: add local process host sources")
    return run_git(root, "rev-parse", "HEAD")


def stable_json(data: object) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def event(kind: str, sequence: int, payload: dict | None = None, *, run_ref: str = host.RUN_REF) -> dict:
    return {
        "schema_version": host.FIXTURE_EVENT_SCHEMA,
        "run_ref": run_ref,
        "sequence": sequence,
        "event_kind": kind,
        "timestamp": host.DETERMINISTIC_TIMESTAMP,
        "payload": payload or {},
    }


def stream_from_events(events: list[dict]) -> str:
    return "\n".join(json.dumps(item, sort_keys=True) for item in events) + "\n"


def event_stream(
    *,
    artifact_path: str = host.ARTIFACT_MEMBER,
    artifact_text: str | None = None,
    run_ref: str = host.RUN_REF,
    artifact_digest: str | None = None,
    artifact_size: int | None = None,
    terminal_kind: str = "run_completed",
) -> str:
    if artifact_text is None:
        artifact_text = stable_json({"fixture_version": "test", "result": "PASS", "run_ref": host.RUN_REF, "workunit_ref": host.TASK_ID})
    digest = artifact_digest or host.sha256_text(artifact_text)
    size = len(artifact_text.encode("utf-8")) if artifact_size is None else artifact_size
    events = [
        event("run_created", 1, {"workunit_ref": host.WORKUNIT_REF}, run_ref=run_ref),
        event("run_started", 2, {"worker_kind": "local_reference_worker"}, run_ref=run_ref),
        event("worker_message", 3, {"message": "fixture worker executed"}, run_ref=run_ref),
        event("artifact_produced", 4, {"path": artifact_path, "media_type": "application/json", "byte_count": size, "sha256": digest}, run_ref=run_ref),
        event("usage_updated", 5, {"events": 6, "artifacts": 1, "processes": 1}, run_ref=run_ref),
        event(terminal_kind, 6, {"result": "PASS"}, run_ref=run_ref),
    ]
    return stream_from_events(events)


class FakeRunner:
    def __init__(
        self,
        *,
        stdout: str = "",
        stderr: str = "",
        returncode: int = 0,
        timeout: bool = False,
        artifact_text: str | None = None,
        artifact_path: str = host.ARTIFACT_MEMBER,
        unexpected_member: str | None = None,
        mutate: Path | None = None,
    ):
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode
        self.timeout = timeout
        self.artifact_text = artifact_text
        self.artifact_path = artifact_path
        self.unexpected_member = unexpected_member
        self.mutate = mutate
        self.calls: list[dict] = []

    def __call__(self, argv, cwd, env, timeout):
        self.calls.append(
            {
                "argv": list(argv),
                "cwd": cwd,
                "env": dict(env),
                "timeout": timeout,
                "shell": False,
                "staged_worker_existed": Path(argv[1]).is_file(),
            }
        )
        if self.mutate is not None:
            self.mutate.write_text("changed\n", encoding="utf-8")
        if self.timeout:
            raise subprocess.TimeoutExpired(list(argv), timeout, output="", stderr="timeout")
        if self.artifact_text is not None:
            artifact = host.resolve_workspace_member(Path(cwd), self.artifact_path)
            artifact.parent.mkdir(parents=True, exist_ok=True)
            artifact.write_text(self.artifact_text, encoding="utf-8", newline="\n")
        if self.unexpected_member is not None:
            unexpected = host.resolve_workspace_member(Path(cwd), self.unexpected_member)
            unexpected.parent.mkdir(parents=True, exist_ok=True)
            unexpected.write_text("unexpected\n", encoding="utf-8")
        return subprocess.CompletedProcess(list(argv), self.returncode, self.stdout, self.stderr)


class LocalProcessExecutionHostRepairTests(unittest.TestCase):
    def test_disposable_workspace_exact_argv_environment_artifacts_and_cleanup(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "aide"
            revision = create_aide_fixture(root)
            artifact_text = stable_json({"fixture_version": "test", "result": "PASS", "run_ref": host.RUN_REF, "workunit_ref": host.TASK_ID})
            fake = FakeRunner(stdout=event_stream(artifact_text=artifact_text), artifact_text=artifact_text)

            result = host.run_host(
                root,
                expected_revision=revision,
                python_executable=sys.executable,
                runner=fake,
                write_reports=False,
            )

            self.assertEqual(result["result"], "PASS")
            self.assertEqual(result["process_call_count"], 1)
            self.assertTrue(result["reference_worker_process_started"])
            self.assertTrue(result["local_process_execution_host_implemented"])
            self.assertEqual(result["provider_ref"], "registered_process_execution_provider_v0")
            self.assertEqual(len(fake.calls), 1)
            call = fake.calls[0]
            self.assertEqual(call["argv"][0], str(Path(sys.executable).resolve()))
            self.assertTrue(call["staged_worker_existed"])
            self.assertNotEqual(Path(call["cwd"]).resolve(), root.resolve())
            self.assertFalse(host.is_under(Path(call["cwd"]), root))
            self.assertEqual(call["argv"][2:], ["--run-id", host.RUN_REF, "--workunit-ref", host.TASK_ID, "--event-stream"])
            self.assertEqual(Path(call["argv"][1]).parent.parent, Path(call["cwd"]))
            self.assertFalse(call["shell"])
            self.assertEqual(call["env"]["PYTHONDONTWRITEBYTECODE"], "1")
            self.assertEqual(call["env"]["PYTHONNOUSERSITE"], "1")
            self.assertEqual(call["env"]["PYTHONUTF8"], "1")
            self.assertEqual(call["env"]["PYTHONHASHSEED"], "0")
            self.assertTrue(result["workspace_cleanup"]["removed"])
            self.assertTrue(result["raw_event_stream_artifact"]["persisted"])
            self.assertEqual(result["worker_artifacts"][0]["sha256"], host.sha256_text(artifact_text))
            self.assertEqual(result["worker_run_lifecycle"]["final_state"], "completed")
            descriptor = host.build_host_descriptor(result)
            self.assertEqual(descriptor["supported_operations"], ["probe", "create_run"])
            self.assertIn("cancel", descriptor["unsupported_operations"])

    def test_invalid_requests_launch_zero_processes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "aide"
            revision = create_aide_fixture(root)
            fake = FakeRunner(stdout=event_stream(), artifact_text=stable_json({"result": "PASS"}))

            unsupported = host.run_host(root, expected_revision=revision, capability_id="aide.future.unsupported", python_executable=sys.executable, runner=fake, write_reports=False)
            self.assertEqual(unsupported["reason_code"], host.REFUSAL_CODES["unsupported_capability"])
            self.assertEqual(unsupported["process_call_count"], 0)

            wrong_revision = host.run_host(root, expected_revision="0" * 40, python_executable=sys.executable, runner=fake, write_reports=False)
            self.assertEqual(wrong_revision["reason_code"], host.REFUSAL_CODES["revision_mismatch"])
            self.assertEqual(wrong_revision["process_call_count"], 0)

            changed_digests = {rel.as_posix(): "sha256:" + ("0" * 64) for rel in host.RELEVANT_SOURCE_RELS}
            digest_mismatch = host.run_host(root, expected_revision=revision, python_executable=sys.executable, expected_digests=changed_digests, runner=fake, write_reports=False)
            self.assertEqual(digest_mismatch["reason_code"], host.REFUSAL_CODES["digest_mismatch"])
            self.assertEqual(digest_mismatch["process_call_count"], 0)

            inside_workspace = host.run_host(root, expected_revision=revision, python_executable=sys.executable, runner=fake, write_reports=False, workspace_root=root / "tmp" / "inside")
            self.assertEqual(inside_workspace["reason_code"], host.REFUSAL_CODES["workspace_inside_source"])
            self.assertEqual(inside_workspace["process_call_count"], 0)
            self.assertEqual(fake.calls, [])

    def test_workspace_containment_rejects_portable_absolute_traversal_and_links(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "workspace"
            workspace.mkdir()
            safe = host.resolve_workspace_member(workspace, "nested/file.txt")
            safe.parent.mkdir(parents=True)
            safe.write_text("ok\n", encoding="utf-8")
            self.assertEqual(safe, workspace.resolve() / "nested" / "file.txt")
            artifact_dir_file = host.resolve_workspace_member(workspace, "artifacts/nested/result.json", artifact=True)
            artifact_dir_file.parent.mkdir(parents=True, exist_ok=True)
            artifact_dir_file.write_text("ok\n", encoding="utf-8")
            self.assertEqual(artifact_dir_file, workspace.resolve() / "artifacts" / "nested" / "result.json")
            cases = [
                ("../outside.txt", "workspace_path_traversal", False),
                ("nested/../../outside.txt", "workspace_path_traversal", False),
                ("nested/../outside.txt", "workspace_path_traversal", False),
                ("/outside.txt", "workspace_path_absolute", False),
                ("C:/outside.txt", "workspace_path_absolute", False),
                (r"C:\outside.txt", "workspace_path_absolute", False),
                (r"\\server\share\outside.txt", "workspace_path_absolute", False),
                (r"\rooted\outside.txt", "workspace_path_absolute", False),
                ("/outside.txt", "artifact_path_escape", True),
                ("../outside.txt", "artifact_path_escape", True),
            ]
            for member, reason_key, artifact in cases:
                with self.subTest(member=member, artifact=artifact):
                    with self.assertRaises(host.LocalProcessHostError) as raised:
                        host.resolve_workspace_member(workspace, member, artifact=artifact)
                    self.assertEqual(raised.exception.reason_code, host.REFUSAL_CODES[reason_key])
            link = workspace / "link"
            try:
                link.symlink_to(Path(tmp))
            except OSError:
                self.skipTest("symlink creation unavailable")
            with self.assertRaises(host.LocalProcessHostError) as symlink:
                host.resolve_workspace_member(workspace, "link/file.txt")
            self.assertEqual(symlink.exception.reason_code, host.REFUSAL_CODES["workspace_symlink_escape"])
            final_link = workspace / "final-link.txt"
            final_link.symlink_to(Path(tmp) / "outside-final.txt")
            with self.assertRaises(host.LocalProcessHostError) as final_symlink:
                host.resolve_workspace_member(workspace, "final-link.txt", must_exist=True, regular_file=True)
            self.assertEqual(final_symlink.exception.reason_code, host.REFUSAL_CODES["workspace_symlink_escape"])
            if os.name == "nt":
                reparse_status = "platform-specific reparse checks exercised by has_reparse_point when such a fixture exists"
            else:
                reparse_status = "skipped: reparse point fixtures are Windows-specific"
            self.assertIn("reparse", reparse_status)

    def test_event_stream_fail_closed_matrix(self) -> None:
        base_completed = [event("run_created", 1), event("run_started", 2), event("run_completed", 3)]
        malformed_cases = [
            ("empty output", "\n", "empty_output"),
            ("malformed json", "not json\n", "malformed_event_stream"),
            ("non object json", "[]\n", "malformed_event_stream"),
            ("missing schema", stream_from_events([{k: v for k, v in event("run_created", 1).items() if k != "schema_version"}]), "malformed_event_stream"),
            ("wrong schema", stream_from_events([dict(event("run_created", 1), schema_version="wrong")]), "malformed_event_stream"),
            ("missing run_ref", stream_from_events([{k: v for k, v in event("run_created", 1).items() if k != "run_ref"}]), "wrong_run_ref"),
            ("wrong run_ref", event_stream(run_ref="aide://wrong-run"), "wrong_run_ref"),
            ("missing sequence", stream_from_events([{k: v for k, v in event("run_created", 1).items() if k != "sequence"}]), "malformed_event_stream"),
            ("noninteger sequence", stream_from_events([dict(event("run_created", 1), sequence="1")]), "malformed_event_stream"),
            ("duplicate sequence", stream_from_events([event("run_created", 1), event("run_started", 1)]), "event_sequence_duplicate"),
            ("decreasing sequence", stream_from_events([event("run_created", 1), event("run_started", 0)]), "event_sequence_decrease"),
            ("sequence gap", stream_from_events([event("run_created", 2)]), "event_sequence_gap"),
            ("missing event kind", stream_from_events([{k: v for k, v in event("run_created", 1).items() if k != "event_kind"}]), "malformed_event_stream"),
            ("unsupported event kind", stream_from_events([event("future_event", 1)]), "malformed_event_stream"),
            ("missing payload", stream_from_events([{k: v for k, v in event("run_created", 1).items() if k != "payload"}]), "malformed_event_stream"),
            ("nonobject payload", stream_from_events([dict(event("run_created", 1), payload=[])]), "malformed_event_stream"),
            ("missing terminal", stream_from_events([event("run_created", 1), event("run_started", 2)]), "terminal_event_missing"),
            ("duplicate run_completed", stream_from_events(base_completed + [event("run_completed", 4)]), "duplicate_terminal_event"),
            ("run_completed then run_failed", stream_from_events(base_completed + [event("run_failed", 4)]), "duplicate_terminal_event"),
            ("run_failed then run_completed", stream_from_events([event("run_created", 1), event("run_started", 2), event("run_failed", 3), event("run_completed", 4)]), "duplicate_terminal_event"),
            ("run_timed_out then terminal", stream_from_events([event("run_created", 1), event("run_started", 2), event("run_timed_out", 3), event("run_failed", 4)]), "duplicate_terminal_event"),
            ("nonterminal after terminal", stream_from_events(base_completed + [event("worker_message", 4)]), "event_after_terminal"),
            ("truncated final json", json.dumps(event("run_created", 1)) + "\n{\"schema_version\"", "malformed_event_stream"),
            ("artifact missing path", stream_from_events([event("run_created", 1), event("run_started", 2), event("artifact_produced", 3, {"media_type": "application/json", "byte_count": 1, "sha256": "sha256:" + "0" * 64})]), "malformed_event_stream"),
            ("artifact missing digest", stream_from_events([event("run_created", 1), event("run_started", 2), event("artifact_produced", 3, {"path": host.ARTIFACT_MEMBER, "media_type": "application/json", "byte_count": 1})]), "malformed_event_stream"),
            ("artifact missing size", stream_from_events([event("run_created", 1), event("run_started", 2), event("artifact_produced", 3, {"path": host.ARTIFACT_MEMBER, "media_type": "application/json", "sha256": "sha256:" + "0" * 64})]), "malformed_event_stream"),
            ("nonzero with completed", event_stream(), "nonzero_exit", 7),
        ]
        for item in malformed_cases:
            name, text, reason_key = item[:3]
            returncode = item[3] if len(item) == 4 else 0
            with self.subTest(name=name):
                with self.assertRaises(host.LocalProcessHostError) as raised:
                    host.parse_fixture_event_stream(text, returncode)
                self.assertEqual(raised.exception.reason_code, host.REFUSAL_CODES[reason_key])

        decoder_cases = [
            ("run_failed result", event_stream(terminal_kind="run_failed"), "worker_failed"),
            ("run_timed_out result", event_stream(terminal_kind="run_timed_out"), "timeout"),
            ("run_cancelled result", event_stream(terminal_kind="run_cancelled"), "worker_cancelled"),
            ("reconciliation required", stream_from_events([event("run_created", 1), event("run_started", 2), event("reconciliation_required", 3)]), "reconciliation_required"),
        ]
        decoder = host.LocalReferenceWorkerOutputDecoder()
        for name, text, reason_key in decoder_cases:
            with self.subTest(name=name):
                decoded = decoder.decode(text, "", 0)
                self.assertEqual(decoded.decoder_outcome, "refused")
                self.assertEqual(decoded.reason_code, host.REFUSAL_CODES[reason_key])

    def test_artifact_integrity_failures_are_refusals(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "aide"
            revision = create_aide_fixture(root)
            declared = stable_json({"fixture_version": "test", "result": "PASS", "run_ref": host.RUN_REF, "workunit_ref": host.TASK_ID})
            wrong = stable_json({"fixture_version": "test", "result": "WRONG"})

            mismatch = host.run_host(root, expected_revision=revision, python_executable=sys.executable, runner=FakeRunner(stdout=event_stream(artifact_text=declared), artifact_text=wrong), write_reports=False)
            self.assertEqual(mismatch["reason_code"], host.REFUSAL_CODES["artifact_digest_mismatch"])

            missing = host.run_host(root, expected_revision=revision, python_executable=sys.executable, runner=FakeRunner(stdout=event_stream(artifact_text=declared)), write_reports=False)
            self.assertEqual(missing["reason_code"], host.REFUSAL_CODES["artifact_missing"])

            unexpected = host.run_host(root, expected_revision=revision, python_executable=sys.executable, runner=FakeRunner(stdout=event_stream(artifact_text=declared), artifact_text=declared, unexpected_member="artifacts/extra.json"), write_reports=False)
            self.assertEqual(unexpected["reason_code"], host.REFUSAL_CODES["artifact_unexpected"])

            escape = host.run_host(root, expected_revision=revision, python_executable=sys.executable, runner=FakeRunner(stdout=event_stream(artifact_path="../escape.json", artifact_text=declared), artifact_text=declared, artifact_path=host.ARTIFACT_MEMBER), write_reports=False)
            self.assertEqual(escape["reason_code"], host.REFUSAL_CODES["artifact_path_escape"])

    def test_artifact_integrity_matrix_direct_collection(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            payload = b'{"ok": true}\n'
            digest = host.sha256_bytes(payload)
            declaration = {"path": host.ARTIFACT_MEMBER, "media_type": "application/json", "byte_count": len(payload), "sha256": digest}

            def workspace_with(files: dict[str, bytes] | None = None) -> Path:
                workspace = Path(tempfile.mkdtemp(prefix="artifact-workspace-", dir=tmp))
                for rel, content in (files or {host.ARTIFACT_MEMBER: payload}).items():
                    target = workspace / rel
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(content)
                return workspace

            valid = host.collect_worker_artifacts(repo, workspace_with(), [declaration])
            self.assertEqual(valid[0]["sha256"], digest)
            self.assertTrue((repo / valid[0]["path"]).is_file())

            duplicate_cases = [
                [declaration, dict(declaration)],
                [declaration, dict(declaration, sha256="sha256:" + "0" * 64)],
                [declaration, dict(declaration, byte_count=len(payload) + 1)],
            ]
            for declarations in duplicate_cases:
                with self.subTest(kind="duplicate"):
                    with self.assertRaises(host.LocalProcessHostError) as raised:
                        host.collect_worker_artifacts(repo, workspace_with(), declarations)
                    self.assertEqual(raised.exception.reason_code, host.REFUSAL_CODES["artifact_duplicate_declaration"])

            shared_workspace = workspace_with({host.ARTIFACT_MEMBER: payload, "artifacts/copy.json": payload})
            copied = host.collect_worker_artifacts(
                repo,
                shared_workspace,
                [
                    declaration,
                    {"path": "artifacts/copy.json", "media_type": "application/json", "byte_count": len(payload), "sha256": digest},
                ],
            )
            self.assertEqual([item["sha256"] for item in copied], [digest, digest])

            oversized_payload = b"x" * (host.MAX_WORKER_ARTIFACT_BYTES + 1)
            bad_declarations = [
                ("byte count mismatch", {host.ARTIFACT_MEMBER: payload}, dict(declaration, byte_count=len(payload) + 1), "artifact_size_mismatch"),
                ("digest mismatch", {host.ARTIFACT_MEMBER: payload}, dict(declaration, sha256="sha256:" + "1" * 64), "artifact_digest_mismatch"),
                ("absolute path", {host.ARTIFACT_MEMBER: payload}, dict(declaration, path="/outside.json"), "artifact_path_escape"),
                ("traversal path", {host.ARTIFACT_MEMBER: payload}, dict(declaration, path="../outside.json"), "artifact_path_escape"),
                ("oversized", {"artifacts/large.bin": oversized_payload}, {"path": "artifacts/large.bin", "media_type": "application/octet-stream", "byte_count": len(oversized_payload), "sha256": host.sha256_bytes(oversized_payload)}, "artifact_oversized"),
                ("zero byte", {"artifacts/zero.bin": b""}, {"path": "artifacts/zero.bin", "media_type": "application/octet-stream", "byte_count": 0, "sha256": host.sha256_bytes(b"")}, ""),
            ]
            for name, files, bad, reason_key in bad_declarations:
                with self.subTest(name=name):
                    if reason_key:
                        with self.assertRaises(host.LocalProcessHostError) as raised:
                            host.collect_worker_artifacts(repo, workspace_with(files), [bad])
                        self.assertEqual(raised.exception.reason_code, host.REFUSAL_CODES[reason_key])
                    else:
                        self.assertEqual(host.collect_worker_artifacts(repo, workspace_with(files), [bad])[0]["byte_count"], 0)

            dir_workspace = workspace_with({})
            directory = dir_workspace / "artifacts/directory.json"
            directory.parent.mkdir(parents=True, exist_ok=True)
            directory.mkdir()
            with self.assertRaises(host.LocalProcessHostError) as directory_error:
                host.collect_worker_artifacts(repo, dir_workspace, [{"path": "artifacts/directory.json", "media_type": "application/json", "byte_count": 1, "sha256": digest}])
            self.assertEqual(directory_error.exception.reason_code, host.REFUSAL_CODES["artifact_link_rejected"])

            try:
                link_workspace = workspace_with({})
                final_link = link_workspace / "artifacts/final-link.json"
                final_link.parent.mkdir(parents=True, exist_ok=True)
                final_link.symlink_to(Path(tmp) / "outside.json")
                with self.assertRaises(host.LocalProcessHostError) as final_link_error:
                    host.collect_worker_artifacts(repo, link_workspace, [{"path": "artifacts/final-link.json", "media_type": "application/json", "byte_count": len(payload), "sha256": digest}])
                self.assertEqual(final_link_error.exception.reason_code, host.REFUSAL_CODES["artifact_link_rejected"])

                intermediate_workspace = workspace_with({})
                link_dir = intermediate_workspace / "link-dir"
                link_dir.symlink_to(Path(tmp), target_is_directory=True)
                with self.assertRaises(host.LocalProcessHostError) as intermediate_link_error:
                    host.collect_worker_artifacts(repo, intermediate_workspace, [{"path": "link-dir/outside.json", "media_type": "application/json", "byte_count": len(payload), "sha256": digest}])
                self.assertEqual(intermediate_link_error.exception.reason_code, host.REFUSAL_CODES["artifact_link_rejected"])
            except OSError:
                self.skipTest("symlink creation unavailable")

    def test_artifact_access_hook_revalidates_replaced_members(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            workspace = Path(tmp) / "workspace"
            repo.mkdir()
            workspace.mkdir()
            payload = b'{"ok": true}\n'
            digest = host.sha256_bytes(payload)
            artifact = workspace / host.ARTIFACT_MEMBER
            artifact.parent.mkdir(parents=True)
            artifact.write_bytes(payload)
            declaration = {"path": host.ARTIFACT_MEMBER, "media_type": "application/json", "byte_count": len(payload), "sha256": digest}

            def replace_with_directory(path: Path) -> None:
                path.unlink()
                path.mkdir()

            host.set_artifact_access_hook(replace_with_directory)
            try:
                with self.assertRaises(host.LocalProcessHostError) as raised:
                    host.collect_worker_artifacts(repo, workspace, [declaration])
                self.assertEqual(raised.exception.reason_code, host.REFUSAL_CODES["artifact_link_rejected"])
            finally:
                host.set_artifact_access_hook(None)

    def test_lifecycle_transitions_and_unsupported_operations(self) -> None:
        parsed = host.parse_fixture_event_stream(event_stream(), 0)
        lifecycle = host.validate_lifecycle(parsed.events)
        self.assertEqual(lifecycle["initial_state"], "proposed")
        self.assertEqual(lifecycle["final_state"], "completed")
        self.assertIn("cancelled", lifecycle["allowed_terminal_states"])
        self.assertIn("running->reconciliation_required", lifecycle["allowed_transitions"])
        invalid_events = [event("run_created", 1), event("worker_message", 2)]
        with self.assertRaises(host.LocalProcessHostError) as raised:
            host.validate_lifecycle(invalid_events)
        self.assertEqual(raised.exception.reason_code, host.REFUSAL_CODES["invalid_lifecycle_transition"])
        terminal_transition_events = [event("run_created", 1), event("run_started", 2), event("run_completed", 3), event("worker_message", 4)]
        with self.assertRaises(host.LocalProcessHostError) as terminal_transition:
            host.validate_lifecycle(terminal_transition_events)
        self.assertEqual(terminal_transition.exception.reason_code, host.REFUSAL_CODES["terminal_state_transition"])
        self.assertEqual(host.validate_lifecycle([event("run_created", 1), event("run_started", 2), event("run_timed_out", 3)])["final_state"], "timed_out")
        self.assertEqual(host.validate_lifecycle([event("run_created", 1), event("run_started", 2), event("run_cancelled", 3)])["final_state"], "cancelled")
        self.assertEqual(host.validate_lifecycle([event("run_created", 1), event("run_started", 2), event("reconciliation_required", 3)])["final_state"], "reconciliation_required")
        self.assertEqual(host.validate_required_operations(["probe", "create_run"])["result"], "PASS")
        unsupported = host.validate_required_operations(["probe", "cancel"])
        self.assertEqual(unsupported["result"], "REFUSED")
        self.assertEqual(unsupported["reason_code"], host.REFUSAL_CODES["unsupported_operation"])
        refusal = host.refuse_unsupported_operation("cancel")
        self.assertEqual(refusal["result"], "REFUSED")
        self.assertEqual(refusal["operation"], "cancel")

    def test_deterministic_projection_report_scrubbing_and_mutation_detection(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "aide"
            revision = create_aide_fixture(root)
            artifact_text = stable_json({"fixture_version": "test", "result": "PASS", "run_ref": host.RUN_REF, "workunit_ref": host.TASK_ID})
            secret_like = "sk-" + "testsecret000000"
            stderr = f"path={root} token={secret_like}"

            first = host.run_host(root, expected_revision=revision, python_executable=sys.executable, runner=FakeRunner(stdout=event_stream(artifact_text=artifact_text), artifact_text=artifact_text, stderr=stderr))
            first_projection = (root / host.PROJECTION_JSON).read_text(encoding="utf-8")
            second = host.run_host(root, expected_revision=revision, python_executable=sys.executable, runner=FakeRunner(stdout=event_stream(artifact_text=artifact_text), artifact_text=artifact_text, stderr=stderr))
            second_projection = (root / host.PROJECTION_JSON).read_text(encoding="utf-8")

            self.assertEqual(first["validation_status"], "PASS_WITH_WARNINGS")
            self.assertEqual(second["validation_status"], "PASS_WITH_WARNINGS")
            self.assertEqual(first_projection, second_projection)
            for path in (root / host.REPORT_ROOT).rglob("*"):
                if path.is_file():
                    text = path.read_text(encoding="utf-8", errors="replace")
                    self.assertNotIn(str(root), text)
                    self.assertNotIn(secret_like, text)

            mutated = host.run_host(root, expected_revision=revision, python_executable=sys.executable, runner=FakeRunner(stdout=event_stream(artifact_text=artifact_text), artifact_text=artifact_text, mutate=root / host.FIXTURE_WORKER_REL), write_reports=False)
            self.assertEqual(mutated["reason_code"], host.REFUSAL_CODES["unexpected_mutation"])
            self.assertEqual(mutated["process_call_count"], 1)
            self.assertFalse(mutated["workspace_state_unchanged"])


if __name__ == "__main__":
    unittest.main()
