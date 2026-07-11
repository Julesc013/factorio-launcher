# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APPLICATION = ROOT / "runtime/factorio/application"


def validate() -> list[str]:
    problems: list[str] = []
    required = [
        "application_context",
        "application_types",
        "command_dispatch",
        "command_result",
    ]
    for stem in required:
        if not (APPLICATION / f"{stem}.h").is_file():
            problems.append(f"missing application boundary header: {stem}.h")
    for stem in ("application_context", "command_dispatch", "command_result"):
        if not (APPLICATION / f"{stem}.cpp").is_file():
            problems.append(f"missing application boundary implementation: {stem}.cpp")

    handler_names = (
        "product",
        "doctor",
        "installs",
        "instances",
        "launch",
        "mods",
        "modsets",
        "saves",
        "diagnostics",
        "recovery",
        "setup",
        "unavailable",
    )
    handlers = APPLICATION / "handlers"
    for name in handler_names:
        for suffix in (".h", ".cpp"):
            if not (handlers / f"{name}{suffix}").is_file():
                problems.append(f"missing typed command-family handler: {name}{suffix}")

    entrypoint = (APPLICATION / "flb_factorio_application.cpp").read_text(encoding="utf-8")
    dispatch = (APPLICATION / "command_dispatch.cpp").read_text(encoding="utf-8")
    if len(entrypoint.splitlines()) > 220:
        problems.append("application entrypoint regrew beyond the composition boundary")
    for forbidden in (
        "json::parse(",
        "PayloadReader",
        "write_text_new_atomic(",
        "inspect_archive(",
        "TransactionSession::begin(",
        "std::cout",
        "std::cerr",
    ):
        if forbidden in entrypoint:
            problems.append(f"application entrypoint owns backend or codec behavior: {forbidden}")
    if "json::parse(" not in dispatch or "ApplicationRequest" not in dispatch:
        problems.append("command dispatch does not own bounded JSON-to-typed decoding")

    combined_handlers = "\n".join(
        path.read_text(encoding="utf-8") for path in sorted(handlers.glob("*.cpp"))
    )
    for forbidden in ("std::cout", "std::cerr", "printf(", "json::parse(", "PayloadReader"):
        if forbidden in combined_handlers:
            problems.append(f"typed handler owns frontend output or raw JSON parsing: {forbidden}")
    for anchor in (
        "handlers::inspect_product(",
        "handlers::run_doctor(",
        "handlers::list_installs(",
        "handlers::list_instances(",
        "handlers::preview_setup(",
        "handlers::unavailable(",
    ):
        if anchor not in entrypoint:
            problems.append(f"authoritative application route missing: {anchor}")
    return problems


def main() -> int:
    problems = validate()
    if problems:
        for problem in problems:
            print(f"application-handler-check: {problem}", file=sys.stderr)
        return 1
    print("application-handler-check: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
