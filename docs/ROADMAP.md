# Roadmap

## v0.1 - Repo Foundation and Product Boundary

- `factorio-launcher --version`
- `factorio-launcher product inspect`
- `factorio-launcher doctor`
- C ABI policy, command graph policy, schemas, docs, fixtures, native scaffold,
  and current Python CLI prototype

## v0.2 - Read-only Install Discovery

- `installs scan`
- `installs list`
- `installs inspect <install-id>`
- `installs import <path>`

No installing, repairing, or uninstalling.

## v0.3 - Isolated Instances and Launch Plans

- `instances create`
- `instances list`
- `launch-plan <instance>`
- dry-run `run <instance>`

## v0.4 - Local Modsets

- local ZIP import
- lockfile generation
- lockfile verification

## v0.5 - Mod Portal Adapter

- search
- install
- update

## v0.6 - Save Manager and Export/Import

- save import
- save backup
- instance export/import

## v0.7 - Universal Setup Integration

- managed install flow through universal setup
- setup audit handoff

## v0.8 - Server Manager

- headless registration
- server create/start/stop/export

## v0.9 - Modder Tools

- dump data
- benchmark
- instrument mod
- bug report bundles

## v1.0 - Stable CLI and Portable Release

- stable schemas
- stable CLI names
- portable workspace mode
- safe instance isolation
- no known token leakage
- no known Steam-owned install mutation

## v1.1+ - TUI and GUI

Only after the command graph stabilizes. CLI, TUI, WinForms, AppKit, GTK, and
Qt are all frontends over the same command graph/native service/C ABI.
