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
apps/       native CLI/TUI/GUI frontends and an unavailable daemon placeholder
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
include CLI, TUI, and proven GUI entrypoints together. A daemon entrypoint may
join them only after its protocol and lifecycle receive runtime proof; the
current daemon target is an unavailable placeholder.

FacMan's long-term role is to prove the universal launcher with a real product:

```text
Factorio proves the universal launcher.
Dominium proves the universal setup.
FacMan ships as the first serious Factorio product binding.
```

<!-- FACMAN-PROJECT-STATUS:BEGIN -->
## Current Status

R3.7 is complete and `eb629caaec9d62536a272336e940c0d3003fdaae` is the exact H1 candidate.
The current contract surface contains 111 commands, 216 schemas, and 213 refusal codes.

The next authority gate is **H1**. `run.execute` remains `unavailable` with `steam_external_state_not_isolated`.
The operator verdict is `Fail` and Safe beta remains unpromoted.
Packages are unsigned and unpublished. The public C ABI and installed SDK remain experimental; neither carries a stable compatibility promise.
<!-- FACMAN-PROJECT-STATUS:END -->

The native CLI-first slice includes:

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

The functional terminal frontend is opt-in at build time and uses the same
direct client and generated command law:

```bash
cmake -S . -B build/tui -DFACMAN_BUILD_TUI=ON
cmake --build build/tui
facman-tui --list
facman-tui --command workspace.status --json
facman-tui --command diagnostics.export \
  --payload '{"instance_id":"space-age-main","output_path":"diagnostics.zip"}' --apply
```

Target-specific Windows, Linux, and macOS x64 TUI profiles are package-preview
lanes. The older OS-neutral `portable_tui_x64` scaffold remains unpublished
and is not used as product proof.

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
- Diagnostic bundle export accepts only reviewed local formats, reads each
  selected file through a stable no-follow handle, redacts before staging, and
  self-verifies a transaction-journaled production ZIP before success.
- The Linux x64 CLI package-preview lane is scoped to the Ubuntu 24.04 runner,
  records its glibc/toolchain and inspected system dependencies, and proves an
  unsigned, unpublished tarball with zero required skips. It is not a
  universal Unix or fully static claim.

## Development

```bash
py -3 tools/workspace_config.py doctor
py -3 tools/dev.py test --affected
py -3 tools/dev.py test --fast
py -3 tools/dev.py test --full
py -3 tools/dev.py verify-all
```

See [CONTRIBUTING.md](CONTRIBUTING.md) and the
[development getting-started guide](docs/development/getting-started.md).

## AIDE Lite

This repo includes AIDE Lite as development governance tooling only. It is not
part of the launcher runtime and must not be bundled in production packages.
See [docs/architecture/aide_lite_integration.md](docs/architecture/aide_lite_integration.md).
Current machine-readable truth is `.aide/memory/project-state.v2.json`; the
human summary is generated from it. Closed task evidence is hash-indexed under
`.aide/history/` and excluded from ordinary context packets.

Before large native implementation work, review
[docs/architecture/pre_code_structure_review.md](docs/architecture/pre_code_structure_review.md).

## Roadmap

The detailed roadmap lives in [docs/roadmap.md](docs/roadmap.md). The first
useful target is read-only install discovery plus isolated instance creation
and launch-plan preview.
