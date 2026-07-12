# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from native_cli import facman_executable

ROOT = Path(__file__).resolve().parents[1]


class MachineTransportTests(unittest.TestCase):
    def invoke(self, request: dict | str) -> tuple[int, dict, str]:
        text = request if isinstance(request, str) else json.dumps(request, ensure_ascii=False)
        completed = subprocess.run(
            [str(facman_executable()), "rpc", "--stdio"],
            cwd=ROOT,
            input=text,
            check=False,
            encoding="utf-8",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        lines = completed.stdout.splitlines()
        self.assertEqual(len(lines), 1)
        return completed.returncode, json.loads(lines[0]), completed.stderr

    def test_request_id_and_unicode_payload_round_trip(self) -> None:
        with tempfile.TemporaryDirectory(prefix="facman rpc space ") as temporary:
            request = {
                "schema": "facman.transport_request.v1",
                "protocol_version": 1,
                "request_id": "request-ß-quoted-\"",
                "workspace": temporary,
                "command": "product.inspect",
                "dry_run": True,
                "payload": {},
            }
            code, response, stderr = self.invoke(request)
            self.assertEqual(code, 0)
            self.assertEqual(stderr, "")
            self.assertEqual(response["request_id"], request["request_id"])
            self.assertEqual(response["protocol_version"], 1)
            self.assertEqual(response["command"], "product.inspect")
            self.assertEqual(response["outcome"], "ok")
            self.assertEqual(response["payload"]["product_id"], "factorio")

    def test_invalid_protocol_returns_one_machine_envelope(self) -> None:
        code, response, stderr = self.invoke(
            {
                "schema": "facman.transport_request.v1",
                "protocol_version": 2,
                "request_id": "bad-version",
                "command": "product.inspect",
                "dry_run": True,
                "payload": {},
            }
        )
        self.assertEqual(code, 1)
        self.assertEqual(stderr, "")
        self.assertEqual(response["request_id"], "bad-version")
        self.assertEqual(response["error"]["code"], "transport_protocol_invalid")

    def test_input_budget_is_enforced(self) -> None:
        code, response, _ = self.invoke(" " * (1024 * 1024 + 1))
        self.assertEqual(code, 1)
        self.assertEqual(response["error"]["code"], "transport_input_too_large")


if __name__ == "__main__":
    unittest.main()
