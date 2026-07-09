from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import unittest
import zipfile
from pathlib import Path

from native_cli import invoke

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
                self.assertEqual(first["redacted_text"], expected)
                self.assertEqual(second["redacted_text"], expected)
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
                    self.assertEqual(redacted_again["redacted_text"], expected)
                    self.assertEqual(redacted_again["redaction_report"]["summary"]["redacted_fields"], 0)
                    assert_no_secret_values(self, stdout)

    def test_diagnostic_bundle_and_doctor_do_not_leak_secret_corpus(self) -> None:
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
            assert_no_secret_values(self, stdout)

            with zipfile.ZipFile(bundle) as archive:
                names = sorted(archive.namelist())
                combined = b"".join(archive.read(name) for name in names)
                manifest = json.loads(archive.read("manifest/diagnostic-bundle.v1.json"))
                redaction_report = json.loads(archive.read("redaction/report.v1.json"))

            assert_no_secret_values(self, combined)
            self.assertIn(b"[FACMAN_REDACTED]", combined)
            self.assertNotIn(str(workspace).encode("utf-8"), combined)
            self.assertNotIn("instance/account_refs/account_refs.json", names)
            self.assertNotIn("instance/steam/userdata/login.json", names)
            self.assertNotIn("instance/logs/mixed_binary_file.bin", names)
            self.assertNotIn("instance/logs/unsafe_archive.zip", names)

            expected_manifest = json.loads(
                (GOLDENS / "diagnostic_bundle.valid.redacted_manifest.v1.json").read_text(encoding="utf-8")
            )
            self.assertEqual(manifest["schema"], expected_manifest["schema"])
            self.assertEqual(manifest["bundle_version"], expected_manifest["bundle_version"])
            self.assertEqual(manifest["instance_id"], expected_manifest["instance_id"])
            self.assertEqual(manifest["redaction"], expected_manifest["redaction"])

            expected_report = json.loads(
                (GOLDENS / "diagnostic_bundle.redaction_report.v1.json").read_text(encoding="utf-8")
            )
            self.assertEqual(redaction_report["schema"], expected_report["schema"])
            self.assertEqual(redaction_report["policy_schema"], expected_report["policy_schema"])
            self.assertEqual(redaction_report["marker"], expected_report["marker"])
            self.assertEqual(redaction_report["summary"], expected_report["summary"])
            event_codes = {event["code"] for event in redaction_report["events"]}
            self.assertIn("diagnostic_secret_redacted", event_codes)
            self.assertIn("diagnostic_path_excluded", event_codes)
            self.assertIn("diagnostic_binary_skipped", event_codes)
            self.assertIn("diagnostic_archive_unsafe", event_codes)

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
            self.assertEqual(doctor["schema"], "factorio.diagnostic_report.v1")
            self.assertIn("diagnostic_bundle", doctor)
            assert_no_secret_values(self, doctor_stdout)

            with zipfile.ZipFile(doctor_bundle) as archive:
                doctor_combined = b"".join(archive.read(name) for name in archive.namelist())
            assert_no_secret_values(self, doctor_combined)
            self.assertNotIn(str(workspace).encode("utf-8"), doctor_combined)

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

            pack_bytes = pack.read_bytes()
            self.assertIn(b"[FACMAN_REDACTED]", pack_bytes)
            self.assertNotIn(str(workspace).encode("utf-8"), pack_bytes)
            assert_no_secret_values(self, pack_bytes)
