# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APPLICATION = ROOT / "runtime/factorio/application"
MAX_COMPOSITION_LINES = 210


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
    for module in (
        "content_module",
        "diagnostics_module",
        "installation_module",
        "instance_module",
        "launch_module",
        "profile_module",
        "recovery_module",
        "setup_module",
        "workspace_module",
    ):
        for suffix in (".h", ".cpp"):
            if not (modules / f"{module}{suffix}").is_file():
                problems.append(f"missing application module seam: {module}{suffix}")
    if not (modules / "application_module.h").is_file():
        problems.append("missing common application module contract: application_module.h")

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
    if admission_route not in entrypoint:
        problems.append("application entrypoint does not apply global effect/capability admission")
    for anchor in (
        "std::array<const ApplicationModule*, 9> modules_",
        "module_for(request.command)",
        "module->requires_workspace(request.command)",
        "module->accepts_denied_admission(admission)",
        "module->execute(context_, request, admission, current_command_)",
    ):
        if anchor not in entrypoint:
            problems.append(f"application entrypoint is missing module-composition anchor: {anchor}")
    if "switch (request.command)" in entrypoint or "case CommandId::" in entrypoint:
        problems.append("application entrypoint directly enumerates product commands")
    for module in (
        "workspace_module_",
        "setup_module_",
        "installation_module_",
        "instance_module_",
        "profile_module_",
        "content_module_",
        "recovery_module_",
        "diagnostics_module_",
        "launch_module_",
    ):
        if f"&{module}" not in entrypoint:
            problems.append(f"application module is not registered: {module}")

    combined_handlers = "\n".join(
        path.read_text(encoding="utf-8") for path in sorted(handlers.glob("*.cpp"))
    )
    for forbidden in ("std::cout", "std::cerr", "printf(", "json::parse(", "PayloadReader"):
        if forbidden in combined_handlers:
            problems.append(f"typed handler owns frontend output or raw JSON parsing: {forbidden}")
    if "handlers::unavailable(" not in entrypoint:
        problems.append("global admission refusal route is missing")
    route_expectations = {
        "workspace_module.cpp": (
            "handlers::inspect_product(",
            "handlers::run_doctor(",
            "handlers::workspace_status(",
            "handlers::onboarding_plan(",
        ),
        "setup_module.cpp": ("handlers::dispatch_setup(",),
        "instance_module.cpp": (
            "handlers::list_instances(",
            "handlers::dispatch_instance_lifecycle(",
        ),
        "profile_module.cpp": ("handlers::dispatch_profiles(",),
        "content_module.cpp": (
            "handlers::dispatch_snapshots(",
            "handlers::dispatch_mod_inventory(",
            "handlers::dispatch_modset_solver(",
            "handlers::dispatch_save_index(",
            "handlers::dispatch_server_plan(",
        ),
        "recovery_module.cpp": (
            "handlers::recovery_inspect(",
            "handlers::migration(",
        ),
        "diagnostics_module.cpp": (
            "handlers::export_diagnostics(",
            "handlers::create_bug_report(",
        ),
    }
    for filename, anchors in route_expectations.items():
        module_text = (modules / filename).read_text(encoding="utf-8")
        for anchor in anchors:
            if anchor not in module_text:
                problems.append(f"authoritative route missing from {filename}: {anchor}")
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
