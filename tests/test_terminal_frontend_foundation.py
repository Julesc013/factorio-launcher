# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import tomllib
import unittest
from pathlib import Path

from tests.native_cli import facman_executable
from tools import json_contract

ROOT = Path(__file__).resolve().parents[1]


def invoke(
    args: list[str],
    *,
    stdin: str | None = None,
    environment: dict[str, str | None] | None = None,
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    if environment:
        for name, value in environment.items():
            if value is None:
                env.pop(name, None)
            else:
                env[name] = value
    return subprocess.run(
        [str(facman_executable()), *args],
        cwd=ROOT,
        input=stdin,
        check=False,
        text=True,
        encoding="utf-8",
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=30,
    )


class TerminalFrontendFoundationTests(unittest.TestCase):
    def test_no_color_requires_a_nonempty_value_without_changing_stream_capability(self) -> None:
        for value in (None, "", "1", "0"):
            with self.subTest(no_color=value):
                result = invoke(
                    ["tui", "--capabilities", "--json"], environment={"NO_COLOR": value}
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stderr, "")
                document = json.loads(result.stdout)
                self.assertEqual(document["terminal"]["no_color"], bool(value))
                self.assertEqual(document["selection_reason"], "redirected_stream")
                self.assertEqual(document["selected_renderer"], "linear")

    def test_router_keeps_bare_help_and_selects_machine_format_explicitly(self) -> None:
        help_result = invoke([])
        self.assertEqual(help_result.returncode, 0, help_result.stderr)
        self.assertIn("tui [--advanced|--list|--capabilities]", help_result.stdout)
        self.assertNotIn("\x1b", help_result.stdout)

        machine = invoke(["workspace", "status", "--format", "json"])
        self.assertEqual(machine.returncode, 0, machine.stderr)
        self.assertEqual(machine.stderr, "")
        envelope = json.loads(machine.stdout)
        self.assertEqual(envelope["schema"], "facman.transport_response.v2")
        self.assertEqual(envelope["command"], "workspace.status")

    def test_rpc_alias_is_equivalent_to_the_bounded_stdio_host(self) -> None:
        with tempfile.TemporaryDirectory(prefix="facman-rpc-alias-") as temporary:
            request = {
                "schema": "facman.transport_request.v2",
                "protocol_version": 2,
                "request_id": "request.rpc-alias",
                "operation_id": "operation.rpc-alias",
                "attempt_id": "attempt.rpc-alias",
                "workspace": str(Path(temporary) / "workspace"),
                "command": "workspace.status",
                "dry_run": True,
                "payload": {},
            }
            result = invoke(["--rpc"], stdin=json.dumps(request))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "")
        response = json.loads(result.stdout)
        self.assertEqual(response["schema"], "facman.transport_response.v2")
        self.assertEqual(response["request_id"], request["request_id"])
        self.assertEqual(response["operation"]["operation_id"], request["operation_id"])

    def test_same_binary_tui_has_bounded_linear_and_advanced_paths(self) -> None:
        capabilities = invoke(["tui", "--capabilities", "--json"])
        self.assertEqual(capabilities.returncode, 0, capabilities.stderr)
        self.assertEqual(capabilities.stderr, "")
        document = json.loads(capabilities.stdout)
        schema = json_contract.load_schema(
            ROOT / "contracts/schema/ui/terminal_capabilities.v1.schema.json"
        )
        self.assertEqual(json_contract.validate(document, schema), [])
        self.assertEqual(document["selected_renderer"], "linear")
        self.assertEqual(document["selection_reason"], "redirected_stream")

        catalog = invoke(["tui", "--list", "--json"])
        self.assertEqual(catalog.returncode, 0, catalog.stderr)
        catalog_document = json.loads(catalog.stdout)
        self.assertEqual(catalog_document["schema"], "facman.tui_catalog.v1")
        self.assertGreaterEqual(len(catalog_document["commands"]), 56)

        landing = invoke(["tui"], environment={"TERM": "dumb", "NO_COLOR": "1"})
        self.assertEqual(landing.returncode, 0, landing.stderr)
        self.assertIn("FacMan terminal UI (linear mode)", landing.stdout)
        self.assertNotIn("\x1b", landing.stdout)
        self.assertNotIn("Choose category", landing.stdout)

    def test_direct_and_process_tui_commands_share_the_frontend_session(self) -> None:
        with tempfile.TemporaryDirectory(prefix="facman-session-equivalence-Ω-") as temporary:
            workspace = Path(temporary) / "uncreated workspace"
            direct = invoke(
                [
                    "tui", "--workspace", str(workspace), "--command",
                    "workspace.status", "--json",
                ]
            )
            process = invoke(
                [
                    "tui", "--workspace", str(workspace), "--command",
                    "workspace.status", "--transport", "process", "--cli-path",
                    str(facman_executable()), "--json",
                ]
            )
            self.assertFalse(workspace.exists())
        self.assertEqual(direct.returncode, 0, direct.stderr)
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertEqual(json.loads(direct.stdout), json.loads(process.stdout))

    def test_release_profiles_require_one_terminal_executable(self) -> None:
        expected = {
            "windows_portable_tui_x64": "bin/facman.exe",
            "linux_portable_tui_x64": "bin/facman",
            "macos_portable_tui_x64": "bin/facman",
        }
        for profile_name, entrypoint in expected.items():
            with (ROOT / "release/profiles" / profile_name / "profile.toml").open("rb") as handle:
                profile = tomllib.load(handle)
            self.assertEqual(profile["entrypoints"]["cli"], entrypoint)
            self.assertEqual(profile["entrypoints"]["tui"], entrypoint)
            self.assertEqual(profile["required_components"]["binaries"], [entrypoint])


if __name__ == "__main__":
    unittest.main()
