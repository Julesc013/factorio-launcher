# Language And Runtime Policy

FacMan keeps the backend conservative and lets GUI frontends use the language
required by their toolkit only inside their app-shell lane.

## Backend Policy

```text
include/flb/              C ABI only
runtime/base/             native portable support code
runtime/client/           frontend-neutral command clients
runtime/factorio/         Factorio product behavior in C/C++ only
runtime/package/          package/runtime location
runtime/platform/         native platform adapters
apps/cli/                 native CLI shell
apps/tui/                 native TUI shell
apps/daemon/              native daemon/job shell
```

The public ABI must not expose C++ classes, STL types, exceptions, templates,
C# types, Swift types, Objective-C classes, GUI toolkit objects, or platform UI
handles. Public data uses explicit size/version fields and explicit ownership.

## GUI Policy

```text
apps/gui/windows/winforms/  C# / .NET Framework 4.8
apps/gui/windows/winui/     C# / .NET / WinUI
apps/gui/macos/appkit/      Objective-C / Objective-C++
apps/gui/macos/swiftui/     Swift / SwiftUI
apps/gui/linux/gtk/         C / GTK
apps/gui/linux/qt/          C++ / Qt
```

Toolkit-required language levels do not raise the language floor for
`include/`, `runtime/`, CLI, TUI, daemon, Universal Launcher, or Universal
Setup. Qt can require a modern C++ toolchain in its own frontend lane without
making the Factorio backend or universal kernels C++17 projects.

## Enforcement

`tools/language_runtime_policy_check.py` blocks C#, Swift, Objective-C, and GUI
toolkit markers from leaking into protected runtime and app-shell roots. It is
part of `tools/strict_check.py`.
