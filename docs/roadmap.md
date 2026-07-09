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

## FACMAN-DISCOVERY-FIXTURES-02

- Deterministic fake install matrix under `tests/fixtures/factorio_installs/`.
- Fixture manifests declare source, ownership, platform, capability,
  validation, and setup-mutation expectations.
- `facman installs scan --search-root <root> --json` classifies fixture roots
  without host-machine discovery.
- `facman doctor --search-root <root> --json` reports invalid explicit
  candidates without mutating fixture trees.
- Golden reports under `tests/golden/discovery/` pin read-only discovery
  summaries.
- Real Steam VDF, Windows registry, macOS Spotlight, and Linux package-manager
  scanning remain deferred.

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

## FACMAN-MODZIP-DEPTH-02

- Deterministic synthetic local mod ZIP matrix under
  `tests/fixtures/factorio_mods/`.
- `info.json` parsing for name, title, version, Factorio version, author,
  description, dependencies, optional dependencies, hidden-optional
  dependencies, and incompatibilities.
- Lockfiles pin local filenames, SHA-1, SHA-256, source, enabled state, and
  structured dependency declarations.
- Goldens under `tests/golden/modsets/` pin valid lockfiles and invalid ZIP
  refusals.
- Mutation-invariant tests prove source ZIPs are not modified and invalid
  imports do not partially install.
- Mod Portal networking, account login, remote dependency solving, and setup
  mutation remain deferred.

## FACMAN-SAVE-ROUNDTRIP-02

- Deterministic synthetic save fixture matrix under
  `tests/fixtures/factorio_saves/`.
- Save backup writes sidecar manifests with source, destination, timestamp,
  SHA-1, and SHA-256 metadata.
- Save backup, clone, export, and import refuse existing targets instead of
  overwriting silently.
- Malformed save ZIPs return structured `save_malformed` refusals before
  backup, clone, or export writes outputs.
- Instance import preflights archive safety and target existence before writing
  restored instance files.
- Export/import tests prove saves roundtrip, config secrets are redacted, and
  source save fixtures are not mutated.
- Steam Cloud mutation, deep save parsing, map preview, save benchmarking, and
  save-associated modset inference remain deferred.

## FacMan-SETUP-HANDOFF-01

- Managed install commands call Universal Setup.
- Ownership classes distinguish managed, foreign-owned, imported, and portable
  installs.
- Steam remains foreign-owned.

## FacMan-GUI-01

- WinForms, WinUI, AppKit, SwiftUI, GTK, and Qt frontends render the same
  command graph from OS-first GUI lanes.
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
  fixture-backed discovery classification
  isolated instances
  dry-run and execute
  local modsets
  workspace invariants and package layout skeletons

R3 - Safe beta
  save backups
  export/import
  package layouts
  diagnostics

R4 - Managed install alpha
  Universal Setup local archive install
  verify/uninstall managed only

R5 - Native GUI preview
  WinForms/AppKit first shells over command graph

R6 - v1.0
  stable CLI
  stable schemas
  portable packages
  no known boundary violations
```

## Future Contract Layers

The next layer is tracked in
[`docs/architecture/future_layers_plan.md`](architecture/future_layers_plan.md).
That plan keeps capability/effect policy, refusal codes, workspace contracts,
package contracts, customization, accessibility, redaction, runtime/client
ownership, Universal Setup transaction work, and diagnostic intelligence as
bounded work units on top of the current structure.

R2 product hardening status and follow-up work units are tracked in
[`docs/product/r2_alpha_hardening.md`](product/r2_alpha_hardening.md).
