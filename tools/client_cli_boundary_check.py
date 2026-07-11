from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def validate() -> list[str]:
    problems: list[str] = []
    header = (ROOT / "runtime/client/facman_client.h").read_text(encoding="utf-8")
    source = (ROOT / "runtime/client/facman_client.cpp").read_text(encoding="utf-8")
    cli = (ROOT / "apps/cli/command_dispatch.cpp").read_text(encoding="utf-8")
    cmake = "\n".join(path.read_text(encoding="utf-8") for path in [
        ROOT / "CMakeLists.txt",
        ROOT / "cmake/FacManOptions.cmake",
        ROOT / "apps/cli/CMakeLists.txt",
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
    ):
        if anchor not in header:
            problems.append(f"client API is missing anchor: {anchor}")
    for anchor in (
        "fl_command_client_execute_cabi_v1(",
        "client_response_invalid",
        "cli_process_transport_unavailable",
        "daemon_transport_unavailable",
    ):
        if anchor not in source:
            problems.append(f"client implementation is missing anchor: {anchor}")

    if "facman::client::FacManClient" not in cli or "call(options," not in cli:
        problems.append("CLI does not dispatch through FacManClient")
    for token in (
        "std::filesystem",
        "fl_path_safety",
        "fl_transaction",
        "fl_archive",
        "fl_runtime_",
        "fl_json",
        "json::",
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
