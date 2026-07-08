# Architecture

FacMan is the Factorio-facing product binding and app shell for a future
universal launcher ecosystem.

```text
Universal Setup Kernel        C89 public ABI, C/C++ internal
Universal Launcher Kernel     C89 public ABI, C/C++ internal
        |
Universal Command Graph       stable command model, schemas, dry-run, audit
        |
Factorio Product Binding      C ABI outward, C11/C++11 internally
        |
CLI / TUI / WinForms / AppKit / GTK / Qt frontends
```

The CLI is the first frontend and may expose JSON for early GUI integration,
but it is not the foundation of the GUI. Every frontend calls the same command
graph/native service/C ABI.

The universal launcher should understand artifact sets, launch plans,
instances, profiles, and diagnostics. It should not understand Factorio mods.
