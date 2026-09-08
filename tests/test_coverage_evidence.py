# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT
from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from tools import coverage_evidence


class CoverageEvidenceTests(unittest.TestCase):
    def test_channel_storage_is_bounded_while_digest_covers_all_bytes(self) -> None:
        payload = b"a" * (coverage_evidence.MAX_CHANNEL_BYTES + 17)

        record = coverage_evidence.drain(io.BytesIO(payload))

        self.assertEqual(record["bytes"], len(payload))
        self.assertEqual(record["stored_bytes"], coverage_evidence.MAX_CHANNEL_BYTES)
        self.assertTrue(record["truncated"])
        self.assertEqual(record["sha256"], hashlib.sha256(payload).hexdigest())

    def test_failed_collection_retains_bounded_diagnostics(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "source"
            build = Path(temporary) / "build"
            source.mkdir()
            build.mkdir()
            process = {
                "exit_code": 64,
                "timed_out": False,
                "stdout": {"bytes": 0, "sha256": hashlib.sha256(b"").hexdigest(),
                           "stored_bytes": 0, "truncated": False, "text": ""},
                "stderr": {"bytes": 18, "sha256": "digest", "stored_bytes": 18,
                           "truncated": False, "text": "suspicious counter"},
            }
            diagnostic = build / "coverage-diagnostic.json"

            with mock.patch.object(coverage_evidence, "run_bounded", return_value=process):
                result = coverage_evidence.collect(
                    source, build, build / "coverage.json", diagnostic, 600.0)

            self.assertEqual(result, 64)
            receipt = json.loads(diagnostic.read_text(encoding="utf-8"))
            self.assertEqual(receipt["result"], "fail")
            self.assertEqual(receipt["process"]["stderr"]["text"], "suspicious counter")
            self.assertFalse(receipt["report"]["present"])

    def test_start_failure_records_consistent_stderr_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            build = root / "build"
            build.mkdir()
            diagnostic = build / "coverage-diagnostic.json"
            with mock.patch.object(
                coverage_evidence,
                "run_bounded",
                side_effect=OSError("gcovr unavailable"),
            ):
                exit_code = coverage_evidence.collect(
                    root,
                    build,
                    build / "coverage.json",
                    diagnostic,
                    1.0,
                )

            self.assertEqual(exit_code, 127)
            receipt = json.loads(diagnostic.read_text(encoding="utf-8"))
            recorded = receipt["process"]["stderr"]
            expected = b"gcovr unavailable"
            self.assertEqual(recorded["bytes"], len(expected))
            self.assertEqual(recorded["stored_bytes"], len(expected))
            self.assertEqual(recorded["sha256"], hashlib.sha256(expected).hexdigest())
            self.assertEqual(recorded["text"], expected.decode())

    def test_outputs_cannot_escape_or_clobber_the_build_root(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            build = root / "build"
            build.mkdir()
            outside = root / "outside.json"
            with self.assertRaises(ValueError):
                coverage_evidence.output_path(build, outside)
            existing = build / "existing.json"
            existing.write_text("preserve", encoding="utf-8")
            with self.assertRaises(FileExistsError):
                coverage_evidence.output_path(build, existing)
        for value in ("0", "901", "not-a-number"):
            with self.subTest(value=value), self.assertRaises(argparse.ArgumentTypeError):
                coverage_evidence.bounded_seconds(value)

    def test_report_and_diagnostic_paths_must_be_distinct(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            build = root / "build"
            build.mkdir()
            shared = build / "coverage.json"

            with self.assertRaisesRegex(ValueError, "must be distinct"):
                coverage_evidence.collect(root, build, shared, shared, 1.0)

    def test_oversized_report_is_not_loaded_and_retains_diagnostic(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            build = root / "build"
            build.mkdir()
            report = build / "coverage.json"
            diagnostic = build / "coverage-diagnostic.json"

            def produce_report(*_args, **_kwargs):
                report.write_bytes(b"12345")
                return {
                    "exit_code": 0,
                    "timed_out": False,
                    "stdout": coverage_evidence.channel_record(b""),
                    "stderr": coverage_evidence.channel_record(b""),
                }

            with mock.patch.object(coverage_evidence, "MAX_REPORT_BYTES", 4), \
                 mock.patch.object(coverage_evidence, "run_bounded", side_effect=produce_report), \
                 mock.patch.object(Path, "read_bytes", side_effect=AssertionError("oversized read")):
                exit_code = coverage_evidence.collect(
                    root, build, report, diagnostic, 1.0)

            self.assertEqual(exit_code, 73)
            receipt = json.loads(diagnostic.read_text(encoding="utf-8"))
            self.assertEqual(receipt["report"]["bytes"], 5)
            self.assertFalse(receipt["report"]["within_size_limit"])
            self.assertNotIn("sha256", receipt["report"])
            self.assertEqual(receipt["result"], "fail")


if __name__ == "__main__":
    unittest.main()
