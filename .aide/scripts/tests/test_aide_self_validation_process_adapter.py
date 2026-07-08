from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.interop.aide import self_validation_process_adapter as adapter


def write_text(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def run_git(root: Path, *args: str) -> str:
    result = subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True, text=True)
    return result.stdout.strip()


def create_aide_fixture(root: Path) -> str:
    root.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", str(root)], check=True, capture_output=True, text=True)
    run_git(root, "config", "user.email", "aide-tests@example.invalid")
    run_git(root, "config", "user.name", "AIDE Tests")
    write_text(root, ".aide/scripts/aide_lite.py", "print('AIDE Lite validate')\nprint('status: PASS')\n")
    run_git(root, "add", ".")
    run_git(root, "commit", "-m", "fixture: add aide lite validate")
    return run_git(root, "rev-parse", "HEAD")


def success_stdout(extra: str = "") -> str:
    suffix = f"\n{extra}" if extra else ""
    return f"AIDE Lite validate\nstatus: PASS\nchecks: fixture{suffix}\n"


class FakeRunner:
    def __init__(self, *, stdout: str = "", stderr: str = "", returncode: int = 0, timeout: bool = False, mutate: Path | None = None):
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


class AideSelfValidationProcessAdapterTests(unittest.TestCase):
    def test_exact_argv_environment_and_exactly_one_process_call(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "aide"
            revision = create_aide_fixture(root)
            fake = FakeRunner(stdout=success_stdout())
            result = adapter.run_adapter(
                root,
                expected_revision=revision,
                python_executable=sys.executable,
                runner=fake,
                write_reports=False,
            )
            self.assertEqual(result["result"], "PASS")
            self.assertEqual(result["process_call_count"], 1)
            self.assertTrue(result["actual_aide_validate_process_spawned"])
            self.assertEqual(result["provider_ref"], "registered_process_execution_provider_v0")
            self.assertEqual(len(fake.calls), 1)
            call = fake.calls[0]
            self.assertEqual(call["argv"][0], str(Path(sys.executable).resolve()))
            self.assertEqual(Path(call["argv"][1]), root / adapter.AIDE_VALIDATE_SCRIPT_REL)
            self.assertEqual(call["argv"][2:], ["validate"])
            self.assertFalse(call["shell"])
            self.assertEqual(call["env"]["PYTHONDONTWRITEBYTECODE"], "1")
            self.assertEqual(call["env"]["PYTHONNOUSERSITE"], "1")
            self.assertEqual(call["env"]["PYTHONUTF8"], "1")
            self.assertEqual(call["env"]["PYTHONHASHSEED"], "0")

    def test_unsupported_capability_and_wrong_revision_cause_zero_process_calls(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "aide"
            revision = create_aide_fixture(root)
            fake = FakeRunner(stdout=success_stdout())
            unsupported = adapter.run_adapter(
                root,
                expected_revision=revision,
                capability_id="aide.future.unsupported",
                python_executable=sys.executable,
                runner=fake,
                write_reports=False,
            )
            self.assertEqual(unsupported["result"], "REFUSED")
            self.assertEqual(unsupported["reason_code"], adapter.REFUSAL_CODES["unsupported_capability"])
            self.assertEqual(unsupported["process_call_count"], 0)
            self.assertEqual(fake.calls, [])

            wrong_revision = adapter.run_adapter(
                root,
                expected_revision="0" * 40,
                python_executable=sys.executable,
                runner=fake,
                write_reports=False,
            )
            self.assertEqual(wrong_revision["reason_code"], adapter.REFUSAL_CODES["revision_mismatch"])
            self.assertEqual(wrong_revision["process_call_count"], 0)
            self.assertEqual(fake.calls, [])

    def test_timeout_malformed_and_nonzero_refusals_are_typed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "aide"
            revision = create_aide_fixture(root)
            timeout = adapter.run_adapter(
                root,
                expected_revision=revision,
                python_executable=sys.executable,
                runner=FakeRunner(timeout=True),
                write_reports=False,
            )
            self.assertEqual(timeout["reason_code"], adapter.REFUSAL_CODES["timeout"])
            self.assertEqual(timeout["process_call_count"], 1)

            malformed = adapter.run_adapter(
                root,
                expected_revision=revision,
                python_executable=sys.executable,
                runner=FakeRunner(stdout="not validate output"),
                write_reports=False,
            )
            self.assertEqual(malformed["reason_code"], adapter.REFUSAL_CODES["malformed_output"])
            self.assertEqual(malformed["process_call_count"], 1)

            nonzero = adapter.run_adapter(
                root,
                expected_revision=revision,
                python_executable=sys.executable,
                runner=FakeRunner(stdout=success_stdout(), returncode=2),
                write_reports=False,
            )
            self.assertEqual(nonzero["reason_code"], adapter.REFUSAL_CODES["nonzero_exit"])
            self.assertEqual(nonzero["process_call_count"], 1)
            self.assertEqual(nonzero["aide_validate_result"]["status"], "PASS")

    def test_deterministic_projection_report_scrubbing_and_shared_models(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "aide"
            revision = create_aide_fixture(root)
            secret_like = "sk-" + "testsecret000000"
            stderr = f"path={root} token={secret_like}"
            first = adapter.run_adapter(
                root,
                expected_revision=revision,
                python_executable=sys.executable,
                runner=FakeRunner(stdout=success_stdout(str(root)), stderr=stderr),
            )
            first_projection = (root / adapter.PROJECTION_JSON).read_text(encoding="utf-8")
            second = adapter.run_adapter(
                root,
                expected_revision=revision,
                python_executable=sys.executable,
                runner=FakeRunner(stdout=success_stdout(str(root)), stderr=stderr),
            )
            second_projection = (root / adapter.PROJECTION_JSON).read_text(encoding="utf-8")
            self.assertEqual(first["validation_status"], "PASS_WITH_WARNINGS")
            self.assertEqual(second["validation_status"], "PASS_WITH_WARNINGS")
            self.assertEqual(first_projection, second_projection)
            receipt = adapter.read_json(root / adapter.EXECUTION_RECEIPT_JSON)
            outcome = adapter.read_json(root / adapter.CAPABILITY_OUTCOME_JSON)
            self.assertEqual(receipt["provider_ref"], "registered_process_execution_provider_v0")
            self.assertEqual(outcome["domain_outcome"], "typed_result")
            for path in (root / adapter.REPORT_ROOT).rglob("*"):
                if path.is_file():
                    text = path.read_text(encoding="utf-8", errors="replace")
                    self.assertNotIn(str(root), text)
                    self.assertNotIn(secret_like, text)

    def test_unexpected_repository_mutation_is_refused_after_process(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "aide"
            revision = create_aide_fixture(root)
            target = root / adapter.AIDE_VALIDATE_SCRIPT_REL
            result = adapter.run_adapter(
                root,
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
