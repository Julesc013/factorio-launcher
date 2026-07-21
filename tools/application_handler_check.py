# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APPLICATION = ROOT / "runtime/factorio/application"
MAX_COMPOSITION_LINES = 270


def validate() -> list[str]:
    problems: list[str] = []
    required = [
        "application_configuration",
        "application_context",
        "application_types",
        "command_admission",
        "command_dispatch",
        "command_result",
    ]
    for stem in required:
        if not (APPLICATION / f"{stem}.h").is_file():
            problems.append(f"missing application boundary header: {stem}.h")
    for stem in (
        "application_configuration",
        "application_context",
        "command_admission",
        "command_dispatch",
        "command_result",
    ):
        if not (APPLICATION / f"{stem}.cpp").is_file():
            problems.append(f"missing application boundary implementation: {stem}.cpp")

    handler_names = (
        "product",
        "doctor",
        "installs",
        "instances",
        "intelligence",
        "launch",
        "mods",
        "modsets",
        "saves",
        "snapshots",
        "profiles",
        "diagnostics",
        "recovery",
        "setup",
        "unavailable",
    )
    handlers = APPLICATION / "handlers"
    modules = APPLICATION / "modules"
    for name in handler_names:
        for suffix in (".h", ".cpp"):
            if not (handlers / f"{name}{suffix}").is_file():
                problems.append(f"missing typed command-family handler: {name}{suffix}")
    for module in ("installation_module", "instance_module", "launch_module"):
        for suffix in (".h", ".cpp"):
            if not (modules / f"{module}{suffix}").is_file():
                problems.append(f"missing application module seam: {module}{suffix}")

    entrypoint = (APPLICATION / "flb_factorio_application.cpp").read_text(encoding="utf-8")
    dispatch = (APPLICATION / "command_dispatch.cpp").read_text(encoding="utf-8")
    if len(entrypoint.splitlines()) > MAX_COMPOSITION_LINES:
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
    admission_route = "admit_command(context_.configuration(), request.command)"
    setup_route = "if (handlers::is_setup_command(request.command))"
    if admission_route not in entrypoint:
        problems.append("application entrypoint does not apply global effect/capability admission")
    elif setup_route not in entrypoint or entrypoint.index(admission_route) > entrypoint.index(setup_route):
        problems.append("setup commands bypass global effect/capability admission")
    if "launch_module_.handles(request.command)" not in entrypoint:
        problems.append("application entrypoint does not route through the launch module seam")
    if "installation_module_.handles(request.command)" not in entrypoint:
        problems.append("application entrypoint does not route through the installation module seam")
    if "instance_module_.handles(request.command)" not in entrypoint:
        problems.append("application entrypoint does not route through the instance projection module seam")
    for migrated in (
        "case CommandId::launch_plan_build:",
        "case CommandId::launch_plan_preflight:",
        "case CommandId::run_preview:",
        "case CommandId::run_execute:",
    ):
        if migrated in entrypoint:
            problems.append(f"launch command leaked back into the fallback switch: {migrated}")
    for migrated in (
        "case CommandId::install_list:",
        "case CommandId::install_scan:",
        "case CommandId::install_import:",
        "case CommandId::install_inspect:",
        "case CommandId::installs_describe:",
        "case CommandId::installs_reconcile_plan:",
    ):
        if migrated in entrypoint:
            problems.append(f"installation command leaked back into the fallback switch: {migrated}")

    combined_handlers = "\n".join(
        path.read_text(encoding="utf-8") for path in sorted(handlers.glob("*.cpp"))
    )
    for forbidden in ("std::cout", "std::cerr", "printf(", "json::parse(", "PayloadReader"):
        if forbidden in combined_handlers:
            problems.append(f"typed handler owns frontend output or raw JSON parsing: {forbidden}")
    for anchor in (
        "handlers::inspect_product(",
        "handlers::run_doctor(",
        "handlers::workspace_status(",
        "handlers::onboarding_plan(",
        "handlers::list_instances(",
        "handlers::dispatch_setup(",
        "handlers::unavailable(",
    ):
        if anchor not in entrypoint:
            problems.append(f"authoritative application route missing: {anchor}")
    installation_module = (modules / "installation_module.cpp").read_text(encoding="utf-8")
    for anchor in ("handlers::list_installs(", "handlers::describe_install(",
                   "handlers::plan_install_reconciliation("):
        if anchor not in installation_module:
            problems.append(f"authoritative installation module route missing: {anchor}")
    instance_module = (modules / "instance_module.cpp").read_text(encoding="utf-8")
    for anchor in ("handlers::describe_instance(", "handlers::readiness_instance("):
        if anchor not in instance_module:
            problems.append(f"authoritative instance projection module route missing: {anchor}")
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
