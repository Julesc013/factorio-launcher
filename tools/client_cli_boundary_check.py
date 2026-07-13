# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def validate() -> list[str]:
    problems: list[str] = []
    headers = "\n".join(
        (ROOT / "runtime/client" / name).read_text(encoding="utf-8")
        for name in (
            "facman_client_model.h",
            "facman_transport_direct.h",
            "facman_transport_process.h",
            "facman_transport_daemon.h",
        )
    )
    model_source = (ROOT / "runtime/client/facman_client.cpp").read_text(encoding="utf-8")
    direct_source = (ROOT / "runtime/client/facman_transport_direct.cpp").read_text(encoding="utf-8")
    process_transport = (ROOT / "runtime/client/facman_transport_process.cpp").read_text(encoding="utf-8")
    daemon_source = (ROOT / "runtime/client/facman_transport_daemon.cpp").read_text(encoding="utf-8")
    process_source = (ROOT / "runtime/client/facman_process_windows.cpp").read_text(encoding="utf-8")
    process_source += (ROOT / "runtime/client/facman_process_posix.cpp").read_text(encoding="utf-8")
    cli = (ROOT / "apps/cli/command_dispatch.cpp").read_text(encoding="utf-8")
    cmake = "\n".join(path.read_text(encoding="utf-8") for path in [
        ROOT / "CMakeLists.txt",
        ROOT / "cmake/FacManOptions.cmake",
        ROOT / "apps/cli/CMakeLists.txt",
        ROOT / "runtime/client/CMakeLists.txt",
        ROOT / "runtime/factorio/CMakeLists.txt",
    ])

    for anchor in (
        "struct CommandRequest",
        "struct CommandResponse",
        "class Transport",
        "class DirectFlbTransport",
        "class CliProcessTransport",
        "class DaemonTransport",
        "class FacManClient",
        "class CancellationToken",
        "class ProgressSink",
    ):
        if anchor not in headers:
            problems.append(f"client API is missing anchor: {anchor}")
    for source_name, source, anchors in (
        ("model", model_source, ("client_response_invalid", "client_transport_missing")),
        ("direct", direct_source, ("fl_command_client_execute_cabi_v1(", "waiting_for_direct_transport")),
        ("process", process_transport, ("cli_process_timeout", "facman.transport_request.v1")),
        ("daemon", daemon_source, ("daemon_transport_unavailable",)),
    ):
        for anchor in anchors:
            if anchor not in source:
                problems.append(f"{source_name} client implementation is missing anchor: {anchor}")
    for anchor in ("JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE", "TerminateJobObject", "setpgid(", "kill(-child", "maximum_standard_output"):
        if anchor not in process_source:
            problems.append(f"CLI process transport is missing safety anchor: {anchor}")

    if "facman::client::FacManClient" not in cli or "call(options," not in cli:
        problems.append("CLI does not dispatch through FacManClient")
    for token in (
        "std::filesystem",
        "fl_path_safety",
        "fl_transaction",
        "fl_archive",
        "fl_runtime_",
        "flb_factorio_",
        "usk/",
        "CreateProcess",
        "fork(",
        "execv",
    ):
        if token in cli:
            problems.append(f"CLI contains forbidden backend token: {token}")

    cli_target = re.search(r"add_executable\(facman_cli\s+([^\)]*)\)", cmake, re.DOTALL)
    if not cli_target or "apps/cli/json_mode.c" in cli_target.group(1):
        problems.append("CLI target still contains the legacy JSON backend source")
    links = re.search(r"target_link_libraries\(facman_cli\s+PRIVATE\s+([^\)]*)\)", cmake)
    if not links or links.group(1).split() != ["facman_client_static"]:
        problems.append("CLI target must link only facman_client_static")
    if "option(FACMAN_WITH_SETUP" not in cmake or "if(FACMAN_WITH_SETUP" not in cmake:
        problems.append("CMake does not expose the optional setup boundary")
    for target in (
        "facman_client_model_static",
        "facman_transport_direct_static",
        "facman_transport_process_static",
        "facman_transport_daemon_static",
        "facman_client_static",
    ):
        if f"add_library({target} " not in cmake:
            problems.append(f"split client target is missing: {target}")
    model_block = cmake.split("add_library(facman_client_model_static", 1)[-1].split(
        "add_library(facman_workspace_resolver_static", 1
    )[0]
    process_block = cmake.split("add_library(facman_transport_process_static", 1)[-1].split(
        "add_library(facman::transport_process", 1
    )[0]
    if "flb_factorio" in model_block or "flaunch_runtime" in model_block:
        problems.append("client model target inherits a product backend or process runtime")
    if "flb_factorio" in process_block:
        problems.append("process transport target inherits the embedded Factorio backend")
    return problems


def main() -> int:
    problems = validate()
    if problems:
        for problem in problems:
            print(f"client-cli-boundary-check: {problem}", file=sys.stderr)
        return 1
    print("client-cli-boundary-check: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
