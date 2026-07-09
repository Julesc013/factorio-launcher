from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SOURCE_SUFFIXES = {".c", ".cc", ".cpp", ".cs", ".h", ".hpp", ".m", ".mm", ".swift"}

ALLOWED_CSHARP_ROOTS = (
    ROOT / "apps" / "gui" / "windows" / "winforms",
    ROOT / "apps" / "gui" / "windows" / "winui",
)
ALLOWED_SWIFT_ROOTS = (ROOT / "apps" / "gui" / "macos" / "swiftui",)
ALLOWED_OBJC_ROOTS = (ROOT / "apps" / "gui" / "macos" / "appkit",)

PROTECTED_ROOTS = (
    ROOT / "include",
    ROOT / "runtime",
    ROOT / "apps" / "cli",
    ROOT / "apps" / "tui",
    ROOT / "apps" / "daemon",
)

TOOLKIT_MARKERS = {
    "System.Windows.Forms": "WinForms",
    "Microsoft.UI.Xaml": "WinUI",
    "SwiftUI": "SwiftUI",
    "AppKit": "AppKit",
    "<gtk/": "GTK",
    "gtk/gtk.h": "GTK",
    "<QApplication": "Qt",
    "<QtWidgets": "Qt",
}


def main() -> int:
    problems: list[str] = []
    problems.extend(check_language_roots())
    problems.extend(check_protected_roots())
    if problems:
        for problem in problems:
            print(f"language-runtime-policy-check: {problem}", file=sys.stderr)
        return 1
    print("language-runtime-policy-check: ok")
    return 0


def check_language_roots() -> list[str]:
    problems: list[str] = []
    for path in ROOT.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in SOURCE_SUFFIXES:
            continue
        if ".git" in path.parts:
            continue
        if path.suffix.lower() == ".cs" and not is_relative_to_any(path, ALLOWED_CSHARP_ROOTS):
            problems.append(f"C# is isolated to Windows GUI shells: {path.relative_to(ROOT)}")
        if path.suffix.lower() == ".swift" and not is_relative_to_any(path, ALLOWED_SWIFT_ROOTS):
            problems.append(f"Swift is isolated to the SwiftUI GUI shell: {path.relative_to(ROOT)}")
        if path.suffix.lower() in {".m", ".mm"} and not is_relative_to_any(path, ALLOWED_OBJC_ROOTS):
            problems.append(f"Objective-C is isolated to the AppKit GUI shell: {path.relative_to(ROOT)}")
    return problems


def check_protected_roots() -> list[str]:
    problems: list[str] = []
    for root in PROTECTED_ROOTS:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in SOURCE_SUFFIXES:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            for marker, label in TOOLKIT_MARKERS.items():
                if marker in text:
                    problems.append(
                        f"{label} marker must not leak into {path.relative_to(ROOT)}; keep it under apps/gui/"
                    )
    return problems


def is_relative_to_any(path: Path, roots: tuple[Path, ...]) -> bool:
    return any(is_relative_to(path, root) for root in roots)


def is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


if __name__ == "__main__":
    raise SystemExit(main())
