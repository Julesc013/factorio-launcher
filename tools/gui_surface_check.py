# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import sys
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GUI_ROOT = ROOT / "apps" / "gui"

PROVIDERS = {
    "windows/winforms": "CommandClient.cs",
    "windows/winui": "CommandClient.cs",
    "macos/appkit": "CommandClient.mm",
    "macos/swiftui": "CommandClient.swift",
    "linux/gtk": "command_client.c",
    "linux/qt": "command_client.cpp",
}

FORBIDDEN_SOURCE_MARKERS = (
    "CreateProcess",
    "Process.Start",
    "execv",
    "fork(",
    "std::filesystem",
    "mod_portal",
    "repair_install",
    "uninstall_install",
)

WINFORMS_REQUIRED_COMMANDS = {
    "help",
    "version",
    "doctor",
    "product.inspect",
    "command_graph.inspect",
    "installs.scan",
    "installs.import",
    "installs.inspect",
    "instances.list",
    "instances.create",
    "launch_plan.build",
    "launch_plan.preflight",
    "run.preview",
    "diagnostics.export",
}

WINFORMS_DEFERRED_COMMANDS = {
    "run.execute",
    "modsets.lock",
    "saves.backup",
    "instance.export",
    "instance.import",
    "setup.preview",
}

WINFORMS_REQUIRED_SCREENS = {
    "Dashboard",
    "Doctor",
    "Installs",
    "Instances",
    "Launch Plan",
    "Diagnostics",
    "Settings/About",
}

APPKIT_REQUIRED_SCREENS = WINFORMS_REQUIRED_SCREENS
GENERATED_CATALOG = ROOT / "contracts" / "generated-index" / "frontend_command_catalog.v1.json"


def generated_commands() -> list[dict[str, object]]:
    return list(json.loads(GENERATED_CATALOG.read_text(encoding="utf-8")).get("commands", []))


def main() -> int:
    problems: list[str] = []
    for provider, command_client in PROVIDERS.items():
        provider_root = GUI_ROOT / provider
        if not provider_root.is_dir():
            problems.append(f"missing GUI provider: apps/gui/{provider}")
            continue
        if not (provider_root / "README.md").is_file():
            problems.append(f"missing provider README: apps/gui/{provider}/README.md")
        if not (provider_root / command_client).is_file():
            problems.append(f"missing command client: apps/gui/{provider}/{command_client}")
        problems.extend(check_provider_source(provider_root))
    problems.extend(check_winforms_shell())
    problems.extend(check_appkit_shell())

    if problems:
        for problem in problems:
            print(f"gui-surface-check: {problem}", file=sys.stderr)
        return 1
    print("gui-surface-check: ok")
    return 0


def check_provider_source(provider_root: Path) -> list[str]:
    problems: list[str] = []
    for path in provider_root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in {".c", ".cpp", ".cs", ".m", ".mm", ".swift"}:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for marker in FORBIDDEN_SOURCE_MARKERS:
            if marker in text:
                problems.append(f"{path.relative_to(ROOT)} contains backend marker {marker}")
    return problems


def check_winforms_shell() -> list[str]:
    problems: list[str] = []
    root = GUI_ROOT / "windows" / "winforms"
    project = root / "FacMan.WinForms.csproj"
    catalog = root / "CommandCatalog.cs"
    generated = root / "GeneratedCommandCatalog.cs"
    form = root / "MainForm.cs"
    models = root / "CommandModels.cs"
    client = root / "CommandClient.cs"
    transport = root / "CliProcessClient.cs"
    for path in [project, catalog, generated, form, models, client, transport]:
        if not path.is_file():
            problems.append(f"WinForms shell missing {path.relative_to(ROOT)}")
            return problems

    project_text = project.read_text(encoding="utf-8", errors="ignore")
    if "<TargetFrameworkVersion>v4.8</TargetFrameworkVersion>" not in project_text:
        problems.append("WinForms shell must stay on .NET Framework 4.8")
    for source_name in ["CommandCatalog.cs", "GeneratedCommandCatalog.cs", "CommandModels.cs", "CommandClient.cs", "CliProcessClient.cs", "MainForm.cs"]:
        if f'<Compile Include="{source_name}" />' not in project_text:
            problems.append(f"WinForms project does not compile {source_name}")

    catalog_text = catalog.read_text(encoding="utf-8", errors="ignore")
    generated_text = generated.read_text(encoding="utf-8", errors="ignore")
    if "GeneratedCommandCatalog.All()" not in catalog_text or "commands.Add" in catalog_text:
        problems.append("WinForms catalog adapter must consume the generated catalog without manual records")
    for command in generated_commands():
        command_id = str(command["command_id"])
        runtime_id = str(command["runtime_id"])
        if f'"{command_id}"' not in generated_text or f'"{runtime_id}"' not in generated_text:
            problems.append(f"WinForms generated command catalog missing {command_id} -> {runtime_id}")
    if '"diagnostics.run"' in generated_text:
        problems.append("WinForms generated catalog misroutes diagnostics.export")

    form_text = form.read_text(encoding="utf-8", errors="ignore")
    if "CollectGeneratedInputs(" not in form_text or "AddGeneratedCategoryTab(" not in form_text:
        problems.append("WinForms shell does not render generated command fields/categories")
    for manual in ("Inputs(params", "AddTextInput(", "inputProvider"):
        if manual in form_text:
            problems.append(f"WinForms shell retains manual command form mapping: {manual}")
    for screen in sorted(WINFORMS_REQUIRED_SCREENS):
        if f'"{screen}"' not in form_text:
            problems.append(f"WinForms shell missing screen {screen}")

    combined = "\n".join(
        path.read_text(encoding="utf-8", errors="ignore")
        for path in [models, catalog, generated, client, transport, form]
    )
    for marker in [
        "common.refusal.v1",
        "winforms_command_deferred",
        "frontend_backend_unavailable",
        "CLI JSON",
    ]:
        if marker not in combined:
            problems.append(f"WinForms shell missing frontend refusal/transport marker {marker}")
    return problems


def check_appkit_shell() -> list[str]:
    problems: list[str] = []
    root = GUI_ROOT / "macos" / "appkit"
    required_files = [
        root / "AppDelegate.m",
        root / "CommandClient.h",
        root / "CommandClient.mm",
        root / "CliProcessClient.h",
        root / "CliProcessClient.mm",
        root / "MainWindowController.h",
        root / "MainWindowController.m",
        root / "FacManGeneratedCommandCatalog.h",
        root / "FacManGeneratedCommandCatalog.m",
    ]
    for path in required_files:
        if not path.is_file():
            problems.append(f"AppKit shell missing {path.relative_to(ROOT)}")
            return problems

    catalog_text = (root / "CommandClient.mm").read_text(encoding="utf-8", errors="ignore")
    generated_text = (root / "FacManGeneratedCommandCatalog.m").read_text(encoding="utf-8", errors="ignore")
    if "FacManGeneratedCommandCatalog()" not in catalog_text or "FacManImplemented(" in catalog_text:
        problems.append("AppKit command client must consume the generated catalog without manual records")
    for command in generated_commands():
        command_id = str(command["command_id"])
        runtime_id = str(command["runtime_id"])
        if f'@"{command_id}"' not in generated_text or f'@"{runtime_id}"' not in generated_text:
            problems.append(f"AppKit generated command catalog missing {command_id} -> {runtime_id}")
    if '@"diagnostics.run"' in generated_text:
        problems.append("AppKit generated catalog misroutes diagnostics.export")

    form_text = (root / "MainWindowController.m").read_text(encoding="utf-8", errors="ignore")
    if "generatedInputsForCommand:" not in form_text or "addGeneratedCommandsToView:" not in form_text:
        problems.append("AppKit shell does not render generated command fields/categories")
    for manual in ("inputsForCommandId:", "copyInput:"):
        if manual in form_text:
            problems.append(f"AppKit shell retains manual command form mapping: {manual}")
    for screen in sorted(APPKIT_REQUIRED_SCREENS):
        if f'@"{screen}"' not in form_text:
            problems.append(f"AppKit shell missing screen {screen}")

    combined = "\n".join(
        path.read_text(encoding="utf-8", errors="ignore")
        for path in required_files
    )
    for marker in [
        "common.refusal.v1",
        "appkit_command_deferred",
        "frontend_backend_unavailable",
        "CLI JSON",
    ]:
        if marker not in combined:
            problems.append(f"AppKit shell missing frontend refusal/transport marker {marker}")
    return problems


if __name__ == "__main__":
    raise SystemExit(main())
