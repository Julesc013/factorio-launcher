# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools import play_evidence_stable_io as STABLE_IO


def response(
    operation: str,
    *,
    payload: dict | None = None,
    error: dict | None = None,
) -> bytes:
    core = {
        "schema": STABLE_IO.RESULT_SCHEMA,
        "operation": operation,
        "status": "ok" if error is None else "refused",
        **({"payload": payload} if error is None else {"error": error}),
    }
    return json.dumps(
        {**core, "record_digest": STABLE_IO.digest_value(core)},
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


class PlayEvidenceStableIoTests(unittest.TestCase):
    def test_closed_native_result_is_digest_verified(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            probe = Path(temporary) / "probe.exe"
            probe.write_bytes(b"probe")
            boundary = STABLE_IO.EvidenceIo(probe)
            completed = subprocess.CompletedProcess(
                [],
                0,
                stdout=response(
                    "read_bounded_json",
                    payload={
                        "document": {"schema": "test.v1"},
                        "file": {
                            "content_sha256": "a" * 64,
                            "bytes_read": 1,
                        },
                    },
                ),
                stderr=b"",
            )
            with patch.object(
                STABLE_IO.subprocess, "run", return_value=completed
            ) as invoked:
                result = boundary.read_json(Path(temporary) / "record.json")

            self.assertEqual(
                result["payload"]["document"], {"schema": "test.v1"}
            )
            self.assertNotIn("shell", invoked.call_args.kwargs)
            self.assertFalse(invoked.call_args.kwargs["check"])

    def test_forged_or_open_result_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            probe = Path(temporary) / "probe.exe"
            probe.write_bytes(b"probe")
            boundary = STABLE_IO.EvidenceIo(probe)
            forged = json.loads(
                response(
                    "hash_file",
                    payload={
                        "file": {
                            "content_sha256": "a" * 64,
                            "bytes_read": 1,
                        }
                    },
                )
            )
            forged["unexpected"] = True
            completed = subprocess.CompletedProcess(
                [],
                0,
                stdout=json.dumps(forged).encode("utf-8"),
                stderr=b"",
            )
            with (
                patch.object(
                    STABLE_IO.subprocess, "run", return_value=completed
                ),
                self.assertRaises(STABLE_IO.StableIoError),
            ):
                boundary.hash_file(Path(temporary) / "record.json")

    def test_refusal_is_not_converted_to_success(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            probe = Path(temporary) / "probe.exe"
            probe.write_bytes(b"probe")
            boundary = STABLE_IO.EvidenceIo(probe)
            completed = subprocess.CompletedProcess(
                [],
                3,
                stdout=response(
                    "inspect_file",
                    error={
                        "code": "evidence_io_refused",
                        "message": "identity changed",
                        "path": "record.json",
                    },
                ),
                stderr=b"",
            )
            with (
                patch.object(
                    STABLE_IO.subprocess, "run", return_value=completed
                ),
                self.assertRaises(STABLE_IO.StableIoError),
            ):
                boundary.inspect_file(Path(temporary) / "record.json")

    def test_durable_json_bytes_are_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            probe = Path(temporary) / "probe.exe"
            probe.write_bytes(b"probe")
            boundary = STABLE_IO.EvidenceIo(probe)
            completed = subprocess.CompletedProcess(
                [],
                0,
                stdout=response(
                    "write_new_durable",
                    payload={
                        "file": {
                            "content_sha256": "a" * 64,
                            "bytes_read": 1,
                        }
                    },
                ),
                stderr=b"",
            )
            with patch.object(
                STABLE_IO.subprocess, "run", return_value=completed
            ) as invoked:
                boundary.write_new_json(
                    Path(temporary) / "record.json",
                    {"z": 1, "a": 2},
                )
            self.assertEqual(
                invoked.call_args.kwargs["input"],
                b'{\n  "a": 2,\n  "z": 1\n}\n',
            )

    def test_exact_member_rejects_suffix_and_traversal_selection(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            probe = Path(temporary) / "probe.exe"
            probe.write_bytes(b"probe")
            boundary = STABLE_IO.EvidenceIo(probe)
            for member in (
                "../factorio.exe",
                "/factorio.exe",
                "Factorio\\bin\\factorio.exe",
                "Factorio/bin/..",
                "./Factorio/bin/factorio.exe",
                "C:/Factorio/bin/factorio.exe",
                "Factorio//bin/factorio.exe",
            ):
                with self.assertRaises(STABLE_IO.StableIoError):
                    boundary.extract_exact_member(
                        Path("source.zip"),
                        member,
                        Path("factorio.exe"),
                    )
                with self.assertRaises(STABLE_IO.StableIoError):
                    boundary.inspect_exact_member(
                        Path("source.zip"),
                        member,
                    )

    def test_exact_member_inspection_is_native_and_bounded(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            probe = Path(temporary) / "probe.exe"
            probe.write_bytes(b"probe")
            boundary = STABLE_IO.EvidenceIo(probe)
            completed = subprocess.CompletedProcess(
                [],
                0,
                stdout=response(
                    "inspect_exact_member",
                    payload={
                        "archive_inspection": {},
                        "archive_inspection_digest": "a" * 64,
                        "member": {
                            "path": "Factorio_2.0.77/bin/x64/factorio.exe",
                            "size": 1,
                            "content_sha256": "b" * 64,
                        },
                    },
                ),
                stderr=b"",
            )
            with patch.object(
                STABLE_IO.subprocess, "run", return_value=completed
            ) as invoked:
                boundary.inspect_exact_member(
                    Path("source.zip"),
                    "Factorio_2.0.77/bin/x64/factorio.exe",
                )
            self.assertEqual(
                invoked.call_args.args[0][1:4],
                [
                    "inspect-exact-member",
                    str(Path(os.path.abspath("source.zip"))),
                    "Factorio_2.0.77/bin/x64/factorio.exe",
                ],
            )

    def test_native_copy_and_resource_revalidation_are_exactly_scoped(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            probe = root / "probe.exe"
            probe.write_bytes(b"probe")
            boundary = STABLE_IO.EvidenceIo(probe)
            copy_result = subprocess.CompletedProcess(
                [],
                0,
                stdout=response(
                    "copy_file_durable",
                    payload={"source": {}, "destination": {}},
                ),
                stderr=b"",
            )
            validate_result = subprocess.CompletedProcess(
                [],
                0,
                stdout=response(
                    "revalidate_resource_specification",
                    payload={
                        "preflight_digest": "a" * 64,
                        "resource_set_digest": "b" * 64,
                        "valid": True,
                    },
                ),
                stderr=b"",
            )
            with patch.object(
                STABLE_IO.subprocess,
                "run",
                side_effect=[copy_result, validate_result],
            ) as invoked:
                boundary.copy_file(
                    root / "source.bin",
                    root / "destination.bin",
                    maximum_bytes=4096,
                )
                boundary.revalidate_resource_specification(
                    root / "preflight.json",
                    "a" * 64,
                    "b" * 64,
                )
            copy_command = invoked.call_args_list[0].args[0]
            self.assertEqual(copy_command[1], "copy-file-durable")
            self.assertEqual(
                copy_command[2:4],
                [
                    str(root / "source.bin"),
                    str(root / "destination.bin"),
                ],
            )
            self.assertEqual(
                invoked.call_args_list[1].args[0][-2:],
                ["a" * 64, "b" * 64],
            )

    def test_digest_helper_matches_canonical_sorted_json(self) -> None:
        value = {"z": [2, 1], "a": {"b": True}}
        expected = hashlib.sha256(
            b'{"a":{"b":true},"z":[2,1]}'
        ).hexdigest()
        self.assertEqual(STABLE_IO.digest_value(value), expected)


if __name__ == "__main__":
    unittest.main()
