# Roadmap

FacMan proves the universal launcher with real Factorio workflows while
leaving setup mutation to Universal Setup.

## FACMAN-INTEGRATION-HARDEN-01

- Cross-repo boundary proof for `factorio-launcher`, `universal-launcher`, and
  `universal-setup`.
- Command, result, refusal, diagnostic, and golden-output contracts.
- Stale-doc and package-layout readiness checks.
- Product-only and full sibling-workspace validation modes.

## FacMan-CANON-01

- Repo structure uses `runtime/content/contracts/release`.
- Product identity is FacMan.
- Python product runtime is retired; Python remains tooling/tests only.
- Native CLI/TUI/daemon scaffold builds.
- Native CLI owns the initial smoke commands for product inspect, doctor,
  install import, instance create, launch-plan preview, and dry-run run.
- Validators block retired roots and old GUI app layout.

## ULAUNCH-MIN-01

- Minimal Universal Launcher owns product registry, install refs, instances,
  profiles, account refs, artifact sets, launch plans, diagnostics, and command
  JSON I/O.
- No Factorio logic enters Universal Launcher.

## FacMan-DISCOVERY-01

- `facman product inspect`
- `facman doctor`
- `facman installs scan`
- `facman installs inspect <install-id>`
- `facman installs import <path>`
- JSON output for read-only reports.
- No installing, repairing, uninstalling, or downloading.

## FacMan-INSTANCE-01

- `facman instances create <name> --install <install-id>`
- `facman instances list`
- `facman launch-plan <instance>`
- `facman run <instance> --execute`
- Default run mode remains dry-run.
- No silent writes to global Factorio data.

## FacMan-MODSET-01

- Local ZIP mod import.
- Modset lockfile generation.
- Modset verification.
- Modset export.

## FacMan-SETUP-HANDOFF-01

- Managed install commands call Universal Setup.
- Ownership classes distinguish managed, foreign-owned, imported, and portable
  installs.
- Steam remains foreign-owned.

## FacMan-GUI-01

- Win32/WinForms, AppKit, GTK, and optional Qt frontends render the same command
  graph.
- No GUI-only behavior.

## Release Readiness Ladder

```text
R0 - Architecture baseline
  validators pass
  contracts exist
  cross-repo builds pass

R1 - Developer preview
  fake fixtures
  dry-run launch plans
  no real mutation

R2 - Local power-user alpha
  real install import
  isolated instances
  dry-run and execute
  local modsets

R3 - Safe beta
  save backups
  export/import
  package layouts
  diagnostics

R4 - Managed install alpha
  Universal Setup local archive install
  verify/uninstall managed only

R5 - Native GUI preview
  Win32/AppKit/GTK shells over command graph

R6 - v1.0
  stable CLI
  stable schemas
  portable packages
  no known boundary violations
```
