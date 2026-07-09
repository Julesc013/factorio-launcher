# GUI Frontend Policy

No frontend is the foundation for another frontend.

Do not build:

```text
WinForms GUI -> TUI -> CLI -> core
```

Build:

```text
Universal Setup Kernel        C89 public ABI, C/C++ internal
Universal Launcher Kernel     C89 public ABI, C/C++ internal
        |
Universal Command Graph       schemas, dry-run, audit, errors
        |
Factorio Product Binding      C ABI outward, native C/C++ internally
        |
CLI / TUI / WinForms / WinUI / AppKit / SwiftUI / GTK / Qt frontends
```

The CLI is the first frontend because it is scriptable and easy to test. It is
not the long-term foundation of the GUI. GUIs may initially call CLI JSON mode,
then move to the daemon or C ABI where useful.

Every frontend must render the same command graph. GUI-only behavior is a
product bug unless it is purely presentational.

Each distribution package may include CLI, TUI, daemon, and GUI binaries. Each
executable remains a distinct frontend shell.
