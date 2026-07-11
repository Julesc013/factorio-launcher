from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path

from native_cli import facman_executable, invoke

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_INSTALL = ROOT / "tests" / "fixtures" / "fake_factorio_install"
FIXTURES = ROOT / "tests" / "fixtures" / "redaction"
GOLDENS = ROOT / "tests" / "golden" / "diagnostics"


def run_json(args: list[str]) -> tuple[int, dict, str, str]:
    code, stdout, stderr = invoke(args)
    if stdout.strip():
        return code, json.loads(stdout), stdout, stderr
    return code, {}, stdout, stderr


def tree_snapshot(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def secret_values() -> list[str]:
    corpus = json.loads((FIXTURES / "secrets_corpus.v1.json").read_text(encoding="utf-8"))
    return corpus["values"]


def assert_no_secret_values(testcase: unittest.TestCase, blob: bytes | str) -> None:
    if isinstance(blob, bytes):
        text = blob.decode("utf-8", errors="ignore")
    else:
        text = blob
    for value in secret_values():
        testcase.assertNotIn(value, text)


def normalize_newlines(text: str) -> str:
    return text.replace("\r\n", "\n")


def setup_redaction_workspace(workspace: Path) -> Path:
    code, _stdout, stderr = invoke(
        [
            "--workspace",
            str(workspace),
            "installs",
            "import",
            str(FIXTURE_INSTALL),
            "--id",
            "fixture",
        ]
    )
    assert code == 0, stderr
    code, _stdout, stderr = invoke(
        [
            "--workspace",
            str(workspace),
            "instances",
            "create",
            "Redaction Proof",
            "--install",
            "fixture",
            "--id",
            "redaction-proof",
        ]
    )
    assert code == 0, stderr

    instance_root = workspace / "instances" / "redaction-proof"
    config_root = instance_root / "config"
    logs_root = instance_root / "logs"
    config_root.mkdir(parents=True, exist_ok=True)
    logs_root.mkdir(parents=True, exist_ok=True)

    config_text = (
        (FIXTURES / "config_with_password.ini").read_text(encoding="utf-8")
        + "\n"
        + (FIXTURES / "config_with_token.ini").read_text(encoding="utf-8")
    )
    (config_root / "config.ini").write_text(config_text, encoding="utf-8")
    shutil.copyfile(FIXTURES / "server_settings_with_rcon_password.json", config_root / "server-settings.json")
    shutil.copyfile(FIXTURES / "log_with_token.txt", logs_root / "factorio-current.log")
    shutil.copyfile(FIXTURES / "log_with_cookie.txt", logs_root / "cookie.log")
    shutil.copyfile(FIXTURES / "mixed_binary_file.bin", logs_root / "mixed_binary_file.bin")
    shutil.copyfile(
        FIXTURES / "nested_archive_like_fixture" / "unsafe_archive.zip",
        logs_root / "unsafe_archive.zip",
    )

    account_root = instance_root / "account_refs"
    account_root.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(FIXTURES / "account_refs_with_secret_like_values.json", account_root / "account_refs.json")

    steam_root = instance_root / "steam" / "userdata"
    steam_root.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(
        FIXTURES / "steam_userdata_like_tree" / "steam" / "userdata" / "login.json",
        steam_root / "login.json",
    )
    return instance_root


class DiagnosticRedactionTests(unittest.TestCase):
    def test_redact_command_matches_goldens_and_is_deterministic(self) -> None:
        cases = [
            ("config_with_password.ini", "config.redacted.ini"),
            ("log_with_token.txt", "log.redacted.txt"),
        ]
        for fixture_name, golden_name in cases:
            with self.subTest(fixture=fixture_name):
                fixture = FIXTURES / fixture_name
                expected = (GOLDENS / golden_name).read_text(encoding="utf-8")

                first_code, first, first_stdout, first_stderr = run_json(
                    ["diagnostics", "redact", str(fixture), "--json"]
                )
                second_code, second, second_stdout, second_stderr = run_json(
                    ["diagnostics", "redact", str(fixture), "--json"]
                )
                self.assertEqual(first_code, 0, first_stderr)
                self.assertEqual(second_code, 0, second_stderr)
                self.assertEqual(normalize_newlines(first["redacted_text"]), normalize_newlines(expected))
                self.assertEqual(normalize_newlines(second["redacted_text"]), normalize_newlines(expected))
                self.assertEqual(first["redaction_report"]["summary"], second["redaction_report"]["summary"])
                assert_no_secret_values(self, first_stdout)
                assert_no_secret_values(self, second_stdout)

                with tempfile.TemporaryDirectory() as tmp:
                    redacted_path = Path(tmp) / fixture_name
                    redacted_path.write_bytes(first["redacted_text"].encode("utf-8"))
                    code, redacted_again, stdout, stderr = run_json(
                        ["diagnostics", "redact", str(redacted_path), "--json"]
                    )
                    self.assertEqual(code, 0, stderr)
                    self.assertEqual(normalize_newlines(redacted_again["redacted_text"]), normalize_newlines(expected))
                    self.assertEqual(redacted_again["redaction_report"]["summary"]["redacted_fields"], 0)
                    assert_no_secret_values(self, stdout)

    def test_multiline_json_values_are_redacted_and_malformed_json_fails_closed(self) -> None:
        fixture = FIXTURES / "multiline_json_secret.json"
        code, report, stdout, stderr = run_json(["diagnostics", "redact", str(fixture), "--json"])
        self.assertEqual(code, 0, stderr)
        redacted = report["redacted_text"]
        self.assertNotIn("fixture-multiline-token-value", redacted)
        self.assertNotIn("fixture-multiline-password-value", redacted)
        self.assertEqual(redacted.count("[FACMAN_REDACTED]"), 2)
        self.assertEqual(report["redaction_report"]["summary"]["redacted_fields"], 2)
        self.assertNotIn("fixture-multiline-token-value", stdout)

        with tempfile.TemporaryDirectory() as tmp:
            malformed = Path(tmp) / "malformed.json"
            malformed.write_text('{"token": "secret-value-no-close\n', encoding="utf-8")
            code, refusal, stdout, _stderr = run_json(
                ["diagnostics", "redact", str(malformed), "--json"]
            )
            self.assertEqual(code, 1)
            self.assertEqual(refusal["refusal"]["code"], "diagnostic_structured_input_invalid")
            self.assertNotIn("secret-value-no-close", stdout)

    def test_malformed_sensitive_ini_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            malformed = Path(tmp) / "server-settings.ini"
            malformed.write_text("[server\npassword=must-not-escape\n", encoding="utf-8")
            code, refusal, stdout, _stderr = run_json(
                ["diagnostics", "redact", str(malformed), "--json"]
            )
            self.assertEqual(code, 1)
            self.assertEqual(refusal["refusal"]["code"], "diagnostic_structured_input_invalid")
            self.assertNotIn("must-not-escape", stdout)

    def test_export_route_has_no_cli_backend_or_legacy_zip_writer(self) -> None:
        dispatch = (ROOT / "apps" / "cli" / "command_dispatch.cpp").read_text(encoding="utf-8")
        diagnostics = (ROOT / "runtime/factorio/diagnostics/flb_factorio_diagnostics.cpp").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("write_diagnostic_stored_zip_quarantined", dispatch)
        self.assertNotIn("write_diagnostic_bundle(", dispatch)
        self.assertIn('"diagnostics.export"', dispatch)
        self.assertIn("route_factorio_command(", dispatch)
        self.assertIn("stable_read_relative(", diagnostics)
        self.assertIn("write_to_new_owned_staging(", diagnostics)

    @unittest.skipUnless(os.name == "nt", "Windows junction proof")
    def test_bounded_collector_refuses_a_real_windows_junction(self) -> None:
        smoke = facman_executable().with_name("facman_diagnostic_traversal_smoke.exe")
        self.assertTrue(smoke.is_file(), smoke)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "instance"
            external = Path(tmp) / "external"
            (root / "logs").mkdir(parents=True)
            external.mkdir()
            (external / "secret.log").write_text("must not be selected\n", encoding="utf-8")
            linked = root / "logs" / "linked"
            created = subprocess.run(
                ["cmd", "/c", "mklink", "/J", str(linked), str(external)],
                check=False,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            self.assertEqual(created.returncode, 0, created.stderr or created.stdout)
            checked = subprocess.run(
                [str(smoke), "--check-link-root", str(root)],
                check=False,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            self.assertEqual(checked.returncode, 0, checked.stderr or checked.stdout)

    def test_diagnostic_bundle_and_doctor_alias_are_safe_and_self_verified(self) -> None:
        fixtures_before = tree_snapshot(FIXTURES)
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            setup_redaction_workspace(workspace)
            bundle = workspace / "diagnostics.zip"

            code, report, stdout, stderr = run_json(
                [
                    "--workspace",
                    str(workspace),
                    "diagnostics",
                    "export",
                    "--instance",
                    "redaction-proof",
                    "--out",
                    str(bundle),
                    "--json",
                ]
            )
            self.assertEqual(code, 0, stderr)
            self.assertEqual(report["schema"], "factorio.diagnostic_bundle_export.v1")
            self.assertTrue(report["self_verified"])
            self.assertTrue(bundle.is_file())
            assert_no_secret_values(self, stdout)

            with zipfile.ZipFile(bundle) as archive:
                names = set(archive.namelist())
                payload = b"".join(archive.read(name) for name in names)
                manifest = json.loads(archive.read("manifest/diagnostic-bundle.v1.json"))
                omissions = json.loads(archive.read("reports/omissions.v1.json"))
                reads = json.loads(archive.read("reports/file-reads.v1.json"))
            self.assertIn("reports/traversal.v1.json", names)
            self.assertIn("reports/redaction.v1.json", names)
            self.assertIn("reports/file-reads.v1.json", names)
            self.assertIn("reports/omissions.v1.json", names)
            self.assertEqual(manifest["policy_version"], "facman.diagnostic_export.v1")
            self.assertEqual(manifest["source_identity_policy"], "sha256-pseudonymous")
            self.assertTrue(all(item["consistent"] for item in reads["files"]))
            omission_reasons = {item["reason"] for item in omissions["omissions"]}
            self.assertIn("unknown_format", omission_reasons)
            self.assertIn("archive_format_omitted", omission_reasons)
            self.assertNotIn(str(workspace).encode("utf-8"), payload)
            assert_no_secret_values(self, payload)

            doctor_bundle = workspace / "doctor-diagnostics.zip"
            code, doctor, doctor_stdout, stderr = run_json(
                [
                    "--workspace",
                    str(workspace),
                    "doctor",
                    "--instance",
                    "redaction-proof",
                    "--diagnostic-bundle",
                    str(doctor_bundle),
                    "--json",
                ]
            )
            self.assertEqual(code, 0, stderr)
            self.assertEqual(doctor["command"], "diagnostics.export")
            self.assertTrue(doctor["self_verified"])
            self.assertTrue(doctor_bundle.is_file())
            assert_no_secret_values(self, doctor_stdout)

        self.assertEqual(tree_snapshot(FIXTURES), fixtures_before)

    def test_instance_export_uses_shared_redaction_marker_and_no_raw_secret_values(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            setup_redaction_workspace(workspace)
            pack = workspace / "instance-export.zip"

            code, exported, stdout, stderr = run_json(
                [
                    "--workspace",
                    str(workspace),
                    "export",
                    "instance",
                    "redaction-proof",
                    str(pack),
                    "--json",
                ]
            )
            self.assertEqual(code, 0, stderr)
            expected = json.loads((GOLDENS / "export.redacted.v1.json").read_text(encoding="utf-8"))
            self.assertEqual(exported["schema"], expected["schema"])
            self.assertEqual(exported["redactions"], expected["redactions"])
            assert_no_secret_values(self, stdout)

            with zipfile.ZipFile(pack) as archive:
                payload = b"".join(archive.read(name) for name in archive.namelist())
            self.assertIn(b"[FACMAN_REDACTED]", payload)
            self.assertNotIn(str(workspace).encode("utf-8"), payload)
            assert_no_secret_values(self, payload)
