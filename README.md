# FacMan - an unofficial launcher and isolated instance manager for Factorio

FacMan is a third-party Factorio launcher focused on isolated, reproducible
environments. It discovers existing installs, creates per-instance data roots,
generates dry-run launch plans, and keeps install mutation behind a future
universal setup adapter.

This project is not affiliated with or endorsed by Wube Software. It does not
bundle Factorio binaries, bypass ownership checks, or use official Factorio
branding assets.

## Durable Layout

```text
include/    Factorio binding public C ABI headers only
runtime/    reusable private implementation for the Factorio binding, clients,
            package locator, and platform adapters
apps/       native CLI, TUI, daemon, and OS-first GUI frontends
content/    Factorio product templates, discovery rules, launch templates,
            instance templates, redaction rules, and policy
contracts/  ABI notes, command law, policies, and versioned JSON schemas
release/    package manifests and release profiles
docs/       human documentation
tests/      unit, contract, integration, fixture, and golden proof
tools/      validators and repository automation
```

Retired roots are intentionally blocked: `source/`, `src/`, `data/`,
`schemas/`, and `packaging/` must not return. Universal setup and universal
launcher code live in their own sibling repositories, not in this Factorio
product repo.

Runtime folders are domain folders, not language-version buckets. C/C++ files
belong under the product domain they implement; folders like `c11/` and
`cpp11/` are intentionally blocked. `contracts/` is broader than schemas, and
`release/profiles/` names concrete target lanes such as
`windows_legacy_winforms`, `macos_legacy_appkit`, and `linux_x11_gtk`.

The CLI is the first frontend, not the foundation of every other frontend.
CLI, TUI, WinForms, WinUI, AppKit, SwiftUI, GTK, and Qt all sit over the same
command graph, native launcher service, and C ABI. Distribution packages may
include CLI, TUI, daemon, and GUI entrypoints together, but each executable
remains a separate frontend shell.

FacMan's long-term role is to prove the universal launcher with a real product:

```text
Factorio proves the universal launcher.
Dominium proves the universal setup.
FacMan ships as the first serious Factorio product binding.
```

## Current Slice

The repository starts with a native CLI-first vertical slice:

```bash
facman --version
facman product inspect
facman doctor
facman installs scan
facman installs import <factorio-dir> --id <install-id>
facman instances create space-age-main --install <install-id>
facman launch-plan space-age-main
facman run space-age-main
```

When running directly from a checkout, use:

```bash
cmake -S . -B build/native-smoke
cmake --build build/native-smoke
.\build\native-smoke\Debug\facman.exe --version
```

The packaged console command is `facman`. Python is used for repository
tooling, validators, and tests; it is not a FacMan product runtime.

## Permanent Rule

```text
Universal setup mutates installed software state.
Universal launcher orchestrates runnable product state.
Factorio binding interprets Factorio-specific facts.
Frontends present commands and reports.
Contracts preserve compatibility.
Validators prevent regression.
```

## Architecture Boundary

```text
Universal Setup Kernel        C-compatible public ABI, C/C++ internal
Universal Launcher Kernel     C-compatible public ABI, C/C++ internal
        |
Universal Command Graph       stable command model, schemas, dry-run, audit
        |
Factorio Product Binding      C ABI outward, C/C++ internally
        |
CLI / TUI / WinForms / WinUI / AppKit / SwiftUI / GTK / Qt frontends
```

This repo owns only the Factorio product binding and Factorio-facing app
frontends. Install, repair, uninstall, rollback, and destructive setup mutation
belong to `universal-setup`. Cross-product orchestration, the command graph,
instances, profiles, install references, and launch plans belong to
`universal-launcher`.

## Safety Defaults

- No bundled Factorio binaries.
- No passwords or tokens in manifests.
- No repair or uninstall for Steam or otherwise foreign-owned installs.
- No silent writes to the default Factorio data directory.
- No global mod folder swapping.
- Launch planning is dry-run only. `run --execute` returns
  `isolation_not_proven` until an operator-supplied real Factorio smoke proves
  effective write-data isolation.
- Diagnostic bundle export returns `diagnostic_export_not_safe` until
  structured redaction and bounded no-follow traversal are proven.

## Development

```bash
py -3 tools/workspace_config.py doctor
cmake -S . -B build/native-smoke
cmake --build build/native-smoke
$env:FACMAN_CLI_EXE = "$PWD\build\native-smoke\Debug\facman.exe"
python -m unittest discover -s tests -v
python tools/structure_policy_check.py
python tools/schema_validate.py
python tools/security_policy_check.py
python tools/package_check.py
python tools/strict_check.py
.\build\native-smoke\Debug\facman.exe doctor
```

## AIDE Lite

This repo includes AIDE Lite as development governance tooling only. It is not
part of the launcher runtime and must not be bundled in production packages.
See [docs/architecture/aide_lite_integration.md](docs/architecture/aide_lite_integration.md).

Before large native implementation work, review
[docs/architecture/pre_code_structure_review.md](docs/architecture/pre_code_structure_review.md).

## Roadmap

The detailed roadmap lives in [docs/roadmap.md](docs/roadmap.md). The first
useful target is read-only install discovery plus isolated instance creation
and launch-plan preview.
