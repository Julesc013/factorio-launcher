from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.interop.eureka import public_alpha_readonly_process_adapter as adapter


def write_text(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def run_git(root: Path, *args: str) -> str:
    result = subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True, text=True)
    return result.stdout.strip()


def create_eureka_fixture(root: Path, *, remote: str = adapter.EXPECTED_REMOTE_URL) -> str:
    root.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", str(root)], check=True, capture_output=True, text=True)
    run_git(root, "config", "user.email", "aide-tests@example.invalid")
    run_git(root, "config", "user.name", "AIDE Tests")
    run_git(root, "remote", "add", "origin", remote)
    write_text(
        root,
        adapter.SELECTED_COMMAND_REL.as_posix(),
        "from tools.release.public_alpha_smoke import main\nraise SystemExit(main())\n",
    )
    write_text(
        root,
        adapter.SELECTED_COMMAND_IMPL_REL.as_posix(),
        "def main():\n    print('{\"status\":\"passed\"}')\n    return 0\n",
    )
    write_text(root, "AGENTS.md", "Fixture Eureka instructions.\n")
    run_git(root, "add", ".")
    run_git(root, "commit", "-m", "fixture: add eureka readonly command")
    return run_git(root, "rev-parse", "HEAD")


def success_stdout(extra: str = "") -> str:
    payload = {
        "created_by_slice": "public_alpha_deployment_readiness_review_v0",
        "mode": "public_alpha",
        "status": "passed",
        "total_checks": 1,
        "passed_checks": 1,
        "failed_checks": 0,
        "checks": [{"id": "fixture", "status": "passed", "detail": extra}],
    }
    return json.dumps(payload, sort_keys=True)


def failed_stdout() -> str:
    payload = {
        "created_by_slice": "public_alpha_deployment_readiness_review_v0",
        "mode": "public_alpha",
        "status": "failed",
        "total_checks": 1,
        "passed_checks": 0,
        "failed_checks": 1,
        "checks": [{"id": "fixture", "status": "failed"}],
    }
    return json.dumps(payload, sort_keys=True)


class FakeRunner:
    def __init__(
        self,
        *,
        stdout: str = "",
        stderr: str = "",
        returncode: int = 0,
        timeout: bool = False,
        mutate: Path | None = None,
    ):
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode
        self.timeout = timeout
        self.mutate = mutate
        self.calls: list[dict] = []

    def __call__(self, argv, cwd, env, timeout):
        self.calls.append({"argv": list(argv), "cwd": cwd, "env": dict(env), "timeout": timeout, "shell": False})
        if self.mutate is not None:
            self.mutate.write_text("changed\n", encoding="utf-8")
        if self.timeout:
            raise subprocess.TimeoutExpired(list(argv), timeout, output="", stderr="timeout")
        return subprocess.CompletedProcess(list(argv), self.returncode, self.stdout, self.stderr)


class EurekaReadonlyProcessAdapterTests(unittest.TestCase):
    def test_exact_argv_environment_and_exactly_one_process_call(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            aide_root = Path(tmp) / "aide"
            eureka_root = Path(tmp) / "eureka"
            aide_root.mkdir()
            revision = create_eureka_fixture(eureka_root)
            fake = FakeRunner(stdout=success_stdout())

            result = adapter.run_adapter(
                aide_root,
                eureka_root=eureka_root,
                expected_revision=revision,
                python_executable=sys.executable,
                runner=fake,
                write_reports=False,
            )

            self.assertEqual(result["result"], "PASS")
            self.assertEqual(result["process_call_count"], 1)
            self.assertTrue(result["actual_eureka_process_spawned"])
            self.assertEqual(result["provider_ref"], "registered_process_execution_provider_v0")
            self.assertEqual(result["result_origin"], "eureka_public_alpha_smoke_json")
            self.assertEqual(len(fake.calls), 1)
            call = fake.calls[0]
            self.assertEqual(call["argv"][0], str(Path(sys.executable).resolve()))
            self.assertEqual(Path(call["argv"][1]), eureka_root / adapter.SELECTED_COMMAND_REL)
            self.assertEqual(call["argv"][2:], ["--json"])
            self.assertEqual(Path(call["cwd"]), eureka_root)
            self.assertFalse(call["shell"])
            self.assertEqual(call["env"]["PYTHONDONTWRITEBYTECODE"], "1")
            self.assertEqual(call["env"]["PYTHONNOUSERSITE"], "1")
            self.assertEqual(call["env"]["PYTHONUTF8"], "1")
            self.assertEqual(call["env"]["PYTHONHASHSEED"], "0")

    def test_invalid_preconditions_cause_zero_process_calls(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            aide_root = Path(tmp) / "aide"
            eureka_root = Path(tmp) / "eureka"
            aide_root.mkdir()
            revision = create_eureka_fixture(eureka_root)
            fake = FakeRunner(stdout=success_stdout())

            unsupported = adapter.run_adapter(
                aide_root,
                eureka_root=eureka_root,
                expected_revision=revision,
                capability_id="eureka.future.unsupported",
                python_executable=sys.executable,
                runner=fake,
                write_reports=False,
            )
            self.assertEqual(unsupported["reason_code"], adapter.REFUSAL_CODES["unsupported_capability"])
            self.assertEqual(unsupported["process_call_count"], 0)

            wrong_revision = adapter.run_adapter(
                aide_root,
                eureka_root=eureka_root,
                expected_revision="0" * 40,
                python_executable=sys.executable,
                runner=fake,
                write_reports=False,
            )
            self.assertEqual(wrong_revision["reason_code"], adapter.REFUSAL_CODES["revision_mismatch"])
            self.assertEqual(wrong_revision["process_call_count"], 0)

            changed_digests = {rel.as_posix(): "sha256:" + ("0" * 64) for rel in adapter.COMMAND_SOURCE_RELS}
            digest_mismatch = adapter.run_adapter(
                aide_root,
                eureka_root=eureka_root,
                expected_revision=revision,
                python_executable=sys.executable,
                expected_digests=changed_digests,
                runner=fake,
                write_reports=False,
            )
            self.assertEqual(digest_mismatch["reason_code"], adapter.REFUSAL_CODES["digest_mismatch"])
            self.assertEqual(digest_mismatch["process_call_count"], 0)
            self.assertEqual(fake.calls, [])

    def test_repository_identity_and_dirty_checkout_refuse_without_launch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            aide_root = Path(tmp) / "aide"
            wrong_remote_root = Path(tmp) / "wrong-remote"
            dirty_root = Path(tmp) / "dirty"
            aide_root.mkdir()
            wrong_revision = create_eureka_fixture(wrong_remote_root, remote="https://example.invalid/eureka.git")
            dirty_revision = create_eureka_fixture(dirty_root)
            write_text(dirty_root, "untracked.txt", "dirty\n")
            fake = FakeRunner(stdout=success_stdout())

            wrong_remote = adapter.run_adapter(
                aide_root,
                eureka_root=wrong_remote_root,
                expected_revision=wrong_revision,
                python_executable=sys.executable,
                runner=fake,
                write_reports=False,
            )
            self.assertEqual(wrong_remote["reason_code"], adapter.REFUSAL_CODES["repository_identity_mismatch"])

            dirty = adapter.run_adapter(
                aide_root,
                eureka_root=dirty_root,
                expected_revision=dirty_revision,
                python_executable=sys.executable,
                runner=fake,
                write_reports=False,
            )
            self.assertEqual(dirty["reason_code"], adapter.REFUSAL_CODES["dirty_checkout"])
            self.assertEqual(fake.calls, [])

    def test_timeout_malformed_nonzero_and_failed_status_are_typed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            aide_root = Path(tmp) / "aide"
            eureka_root = Path(tmp) / "eureka"
            aide_root.mkdir()
            revision = create_eureka_fixture(eureka_root)

            timeout = adapter.run_adapter(
                aide_root,
                eureka_root=eureka_root,
                expected_revision=revision,
                python_executable=sys.executable,
                runner=FakeRunner(timeout=True),
                write_reports=False,
            )
            self.assertEqual(timeout["reason_code"], adapter.REFUSAL_CODES["timeout"])
            self.assertEqual(timeout["process_call_count"], 1)

            malformed = adapter.run_adapter(
                aide_root,
                eureka_root=eureka_root,
                expected_revision=revision,
                python_executable=sys.executable,
                runner=FakeRunner(stdout="not json"),
                write_reports=False,
            )
            self.assertEqual(malformed["reason_code"], adapter.REFUSAL_CODES["malformed_json"])

            inconsistent = adapter.run_adapter(
                aide_root,
                eureka_root=eureka_root,
                expected_revision=revision,
                python_executable=sys.executable,
                runner=FakeRunner(stdout=success_stdout(), returncode=2),
                write_reports=False,
            )
            self.assertEqual(inconsistent["reason_code"], adapter.REFUSAL_CODES["inconsistent_returncode"])

            failed = adapter.run_adapter(
                aide_root,
                eureka_root=eureka_root,
                expected_revision=revision,
                python_executable=sys.executable,
                runner=FakeRunner(stdout=failed_stdout(), returncode=1),
                write_reports=False,
            )
            self.assertEqual(failed["reason_code"], adapter.REFUSAL_CODES["validation_failed"])
            self.assertEqual(failed["eureka_result"]["status"], "invalid")

    def test_deterministic_projection_report_scrubbing_and_shared_models(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            aide_root = Path(tmp) / "aide"
            eureka_root = Path(tmp) / "eureka"
            aide_root.mkdir()
            revision = create_eureka_fixture(eureka_root)
            secret_like = "sk-" + "testsecret000000"
            stderr = f"path={eureka_root} token={secret_like}"

            first = adapter.run_adapter(
                aide_root,
                eureka_root=eureka_root,
                expected_revision=revision,
                python_executable=sys.executable,
                runner=FakeRunner(stdout=success_stdout(str(eureka_root)), stderr=stderr),
            )
            first_projection = (aide_root / adapter.PROJECTION_JSON).read_text(encoding="utf-8")
            second = adapter.run_adapter(
                aide_root,
                eureka_root=eureka_root,
                expected_revision=revision,
                python_executable=sys.executable,
                runner=FakeRunner(stdout=success_stdout(str(eureka_root)), stderr=stderr),
            )
            second_projection = (aide_root / adapter.PROJECTION_JSON).read_text(encoding="utf-8")

            self.assertEqual(first["validation_status"], "PASS_WITH_WARNINGS")
            self.assertEqual(second["validation_status"], "PASS_WITH_WARNINGS")
            self.assertEqual(first_projection, second_projection)
            receipt = adapter.read_json(aide_root / adapter.EXECUTION_RECEIPT_JSON)
            outcome = adapter.read_json(aide_root / adapter.CAPABILITY_OUTCOME_JSON)
            self.assertEqual(receipt["provider_ref"], "registered_process_execution_provider_v0")
            self.assertEqual(outcome["domain_outcome"], "typed_result")
            for path in (aide_root / adapter.REPORT_ROOT).rglob("*"):
                if path.is_file():
                    text = path.read_text(encoding="utf-8", errors="replace")
                    self.assertNotIn(str(aide_root), text)
                    self.assertNotIn(str(eureka_root), text)
                    self.assertNotIn(secret_like, text)

    def test_unexpected_repository_mutation_is_refused_after_process(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            aide_root = Path(tmp) / "aide"
            eureka_root = Path(tmp) / "eureka"
            aide_root.mkdir()
            revision = create_eureka_fixture(eureka_root)
            target = eureka_root / adapter.SELECTED_COMMAND_REL

            result = adapter.run_adapter(
                aide_root,
                eureka_root=eureka_root,
                expected_revision=revision,
                python_executable=sys.executable,
                runner=FakeRunner(stdout=success_stdout(), mutate=target),
                write_reports=False,
            )

            self.assertEqual(result["reason_code"], adapter.REFUSAL_CODES["unexpected_mutation"])
            self.assertEqual(result["process_call_count"], 1)
            self.assertFalse(result["workspace_state_unchanged"])


if __name__ == "__main__":
    unittest.main()
