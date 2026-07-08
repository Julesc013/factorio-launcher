from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GUI_ROOT = ROOT / "apps" / "gui"

PROVIDERS = {
    "win32": "CommandClient.cs",
    "appkit": "CommandClient.mm",
    "gtk": "command_client.c",
    "qt": "command_client.cpp",
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

    if problems:
        for problem in problems:
            print(f"gui-surface-check: {problem}", file=sys.stderr)
        return 1
    print("gui-surface-check: ok")
    return 0


def check_provider_source(provider_root: Path) -> list[str]:
    problems: list[str] = []
    for path in provider_root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in {".c", ".cpp", ".cs", ".m", ".mm"}:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for marker in FORBIDDEN_SOURCE_MARKERS:
            if marker in text:
                problems.append(f"{path.relative_to(ROOT)} contains backend marker {marker}")
    return problems


if __name__ == "__main__":
    raise SystemExit(main())
