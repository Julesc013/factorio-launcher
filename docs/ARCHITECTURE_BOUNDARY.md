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
- export/import
- diagnostics
- command graph

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

`factorio-launcher` must not directly implement repair, uninstall, or managed
install mutation.

