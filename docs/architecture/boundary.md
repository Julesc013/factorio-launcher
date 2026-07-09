# Architecture Boundary

## Universal Setup Owns

- install
- verify
- repair
- uninstall
- stage, commit, rollback
- installed-state manifests
- audit logs
- ownership boundaries

## Universal Launcher Owns

- product registry
- install references
- instances
- profiles
- modsets as opaque artifact sets
- accounts
- launch plans
- universal command graph
- export/import
- diagnostics
- schemas, dry-run, audit, and error model

## Factorio Binding Owns

- Factorio install discovery
- Factorio version detection
- Factorio application and user-data layout rules
- Mod Portal adapter
- dependency and modset resolver
- command-line templates
- account token handling
- server workflows
- modder workflows

Frontends must not stack on top of each other as real architecture. CLI, TUI,
WinForms, WinUI, AppKit, SwiftUI, GTK, and Qt all call the same command
graph/native launcher service/C ABI.

`factorio-launcher` must not directly implement repair, uninstall, or managed
install mutation.
