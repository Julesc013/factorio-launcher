# FacMan Technical Preview census checkpoint

Status: Phase B candidate complete locally; stacked draft PR and hosted CI are
required before this checkpoint can be treated as synchronized.

## Exact base and branch

- branch: `task/facman-technical-preview-census-01`
- exact base: `51047053760557b52a9bf06cff1b79bf6614dafb`
- base branch: `task/facman-dev-reconciliation-01`
- canonical remote `origin/dev` behind the stack:
  `4da0bf2c4c1df92d8e3a4d2d7eae39ebf65cba2f`

## Frozen Technical Preview

- Windows x64;
- WinForms primary ordinary-user projection;
- CLI JSON normative automation/test contract;
- human CLI required for Doctor, diagnostics, status, support, and recovery;
- TUI retained and tested as a grammar-generated command explorer, not an
  ordinary-workflow parity blocker;
- unsigned internal candidate only.

The product matrix contains 37 user outcomes: 28 required and 9 deferred. The
separate generated ledger contains all 125 command/runtime identities and
their schemas, refusals, effects, transports, frontend observations, runtime
capabilities, and zero-or-more product-outcome mappings. Registration and
schemas do not infer implementation or completion.

## Corrected authority

- FacMan: Factorio installation classification, instances, profiles,
  configuration, mods/modsets, saves, readiness, launch intent, presentation,
  release, and support;
- Universal Launcher: opaque runnable references and generic
  operation/process/session/Last Run lifecycle only;
- Universal Setup: installed-software mutation, installed state, setup
  transactions, recovery, and audit.

Instance-local modsets are `instance_content_mutation`, not Setup mutation.
The path-based human-readable JSON/TOML workspace store remains canonical.
SQLite is deferred and may later be used only as a rebuildable index after
measured need.

## Required generated reports

- `docs/generated/technical_preview/product-capabilities.md`
- `docs/generated/technical_preview/command-api-conformance.md`
- `docs/generated/technical_preview/frontend-requirements.md`
- `docs/generated/technical_preview/persistence-authority.md`
- `docs/generated/technical_preview/incubator-debt.md`
- `docs/generated/technical_preview/scope.md`
- `docs/generated/technical_preview/deferred-capabilities.md`
- `docs/generated/technical_preview/release-compiler-targets.md`
- `release/generated/technical_preview_command_api_conformance.v1.json`

## Local validation

- `python tools/technical_preview_census.py --check`: pass;
- `python tools/release_programme_check.py`: pass;
- focused plan/census/programme suite: 45/45 pass;
- `python tools/facman_release.py validate`: pass, 11 existing release input
  files; no second resolver created;
- `python tools/strict_check.py`: pass;
- full Python discovery: 969 tests executed with 321 skips; one initially stale
  generated-plan view was regenerated and its focused test now passes; the
  remaining error is the expected local absence of
  `build/native-smoke/Debug/facman.exe` for the Windows package proof. Hosted
  clean CI is the required package-build evidence.

## Explicit deferrals and no-effect statement

Managed installation, selected-save launch, accounts, acquisition, network,
self-update, storefront mutation, system installation, elevation, native
installer work, server execution, other platforms, public provider APIs,
daemon, remote administration, and plugins remain deferred.

This phase did not run Factorio, mutate Setup or a live Factorio installation,
read private archives, edit ULK or USK, change IR4, write `main` or `dev`, move
a tag, sign, publish, or create a release. The unresolved route/version choice
remains explicit: target 2.0.77 versus retained corpus 2.1.14; silent
substitution is forbidden.
