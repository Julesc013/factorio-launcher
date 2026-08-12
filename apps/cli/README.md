# Factorio CLI App

The `facman` executable is the canonical terminal host. Today this directory
owns the CLI entrypoint and command dispatcher. The dependency-ordered
single-binary migration will make it route three explicit projections without
duplicating product behavior:

```text
facman <command>          bounded human CLI
facman <command> --json   normative machine contract
facman tui                interactive terminal UI
```

The router, stdout/stderr and exit law, compatibility policy, and package
boundary are specified in
[`unified_interaction_platform.v1.md`](../../docs/architecture/unified_interaction_platform.v1.md).
CLI JSON never auto-enters a TUI, prompts, or emits terminal control. Native
GUIs consume the same application/presentation contracts but do not automate
the CLI renderer.
