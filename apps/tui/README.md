# Factorio TUI App

Terminal UI frontend. `generated_command_catalog.hpp` is generated from the
same command law as the desktop clients. The executable consumes that record
set through `FacManClient`; it does not own backend behavior.

Modes:

```text
facman-tui --interactive
facman-tui --list [--json]
facman-tui --command <contract-or-runtime-id> [--payload <json>] [--json]
```

Workspace writes require `--apply`; otherwise the shared backend receives a
dry-run request. `run.execute` cannot be promoted by `--apply` and remains
behind the real-Factorio operator gates. Redirected input/output uses the
noninteractive path, `NO_COLOR` avoids presentation assumptions, results are
bounded to 1 MiB, and Windows uses the UTF-8/long-path process manifest.

The target-specific preview profiles are `windows_portable_tui_x64`,
`linux_portable_tui_x64`, and `macos_portable_tui_x64`. Each includes both the
CLI and TUI so package integrity can be checked by the authoritative CLI before
the TUI catalog/status smoke. The legacy `portable_tui_x64` profile remains an
unpublished historical scaffold claim.
