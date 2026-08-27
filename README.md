# FacMan - an unofficial launcher and isolated instance manager for Factorio

FacMan is a third-party Factorio launcher focused on isolated, reproducible
environments. It discovers existing installs, creates per-instance data roots,
generates dry-run launch plans, and delegates bounded portable-install mutation
to Universal Setup while ordinary live-target apply remains gated.

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

Release artifacts are now derived from a deterministic FacMan-owned
composition graph. The v2 release model separates reviewed lineage from an
out-of-tree observation of the actual build source, then binds exact product,
provider, toolchain, component, path, authority, compatibility, claim, and
qualification truth under one domain-separated root. Packages receive only a
bounded runtime projection of that external evidence graph. See
[Composition Compiler](docs/release/COMPOSITION_COMPILER.md).
The wider provider/product constitution, SDK-conformance boundary,
multi-consumer adoption law, and dependency-ordered preparation register are
ratified in the [Universal Product Runtime and Delivery Programme](docs/architecture/universal_multi_consumer_productization.md).

Retired roots are intentionally blocked: `source/`, `src/`, `data/`,
`schemas/`, and `packaging/` must not return. Universal setup and universal
launcher code live in their own sibling repositories, not in this Factorio
product repo.

Runtime folders are domain folders, not language-version buckets. C/C++ files
belong under the product domain they implement; folders like `c11/` and
`cpp11/` are intentionally blocked. `contracts/` is broader than schemas, and
`release/profiles/` names concrete target lanes such as
`windows_legacy_winforms`, `macos_legacy_appkit`, and `linux_x11_gtk`.

FacMan has one product/application authority and multiple projections. CLI
JSON is the normative machine contract; bounded human CLI and `facman tui`
share one terminal executable; native GUIs project the same snapshots and
semantic actions through platform controls. The finite `0.1.0` Windows
Technical Preview requires CLI JSON, same-binary TUI ordinary-workflow parity,
and WinForms, with human CLI for diagnostic and recovery surfaces. `1.0.0`
adds AppKit and one primary Linux GUI initially GTK. Qt, a local service,
WinUI/SwiftUI, web/mobile, executable plugins, remote administration, and AI
assistance require separate evidence-driven admission. See the
[unified interaction platform](docs/architecture/unified_interaction_platform.v1.md).
The concrete module, dependency, compatibility, portability, UX,
customization, service, machine/agent, verification, and delivery plan is
the [interaction platform execution programme](docs/architecture/interaction_platform_execution_programme.v1.md).

Universal Launcher and Universal Setup each retain a C-compatible semantic
kernel (ULK/USK) and capability-selected host/provider layer (ULU/USU).
FacMan owns Factorio meaning, policy, presentation, acquisition decisions,
release selection, and the resolved product graph. The repositories are not
merged and no fourth common implementation repository is planned.

FacMan's long-term role is to prove the universal launcher with a real product:

```text
Factorio proves the universal launcher.
Dominium proves the universal setup.
FacMan ships as the first serious Factorio product binding.
```

<!-- FACMAN-PROJECT-STATUS:BEGIN -->
## Current Status

**Phase:** `facman_4_0_0_final_distribution`. **Active WorkUnit:** `FACMAN-4.0.0-FINAL-DISTRIBUTION-01`. **Next:** `protected_review_and_main_merge_by_authorized_maintainer`.

> Create any number of independent Factorio setups, select one, and launch the normal game as though it had always been installed and configured exactly that way.

The golden journey is:
`find Factorio -> select/create instance -> choose version/preset/profiles/modpack/accounts -> inspect readiness -> prepare if needed -> Play to menu -> start/load/join/edit -> exit -> preserve state -> relaunch`.
M3 existing-portable adoption is authorised backlog after the playable alpha, not the current critical path.
This tracked checkout enumerates 127 commands, 382 schemas, and 244 refusal codes. These are integrated development-state counts, not release, playability, or authority claims.
Canonical providers are:
- ULK `5479939ca5cbc9ee0f901608a92012778b4752ae`;
- USK `d2a2aae7e61c47035c92334b0522143b4fea3880`.
FacMan's exact consumed providers are:
- ULK `5479939ca5cbc9ee0f901608a92012778b4752ae`;
- USK `d2a2aae7e61c47035c92334b0522143b4fea3880`.
Repository identity is sourced from `release/index/repository_identity.v1.toml`.
Its FacMan row binds stable role `facman` and numeric ID `1293124404`.
The canonical slug is `Julesc013/factorio-launcher`; the deferred future slug is `Julesc013/facman`.
The GitHub rename remains deferred and current source closure uses factorio-launcher.
The adoption candidate closes source/package conformance, exact SDK consumption, atomic pin reconciliation, and sole ULK Last Run authority.
The immutable route v2 remains historical, strictly non-authorizing, and invalidated for current use by the provider-pin change.

Two execution modes are accepted product designs but remain unproven:
Normal-host `instance_isolated` and enforced `hermetic`.
`run.execute` remains unavailable for the current reason:
`route_v4_exact_green_non_authorizing_pending_normal_protected_integration_final_tree_rebinding_and_fresh_d3_d4_authorization`.
No real-play gate has passed.
Readiness is playability `not_evaluated_no_gameplay_executed`, workflow `typed_frontend_v2_and_f100_f210_qualified_distribution_verified`, user validation `not_started`, and release authenticity `not_proven_unsigned`.
Historical M2 setup proof remains preserved and does not promote execution, existing-install adoption, network, credential, signing, or publication authority.
Installation model v2 is closed as a read-only, evidence-bound planning layer.
Gate 2 portable InstanceSpec, local InstanceBinding, and computed readiness are closed as menu-first read-only projections. Saves/worlds remain optional instance content.
Gate 3 exact permit infrastructure is closed with provider-side revalidation and no product issuance.
Gates 0-3 are canonically promoted and dev-synchronized without authority promotion. Gate 4A retains the canonical process-tree-hermetic policy.
The Windows instance-isolated policy is canonical and synchronized. Its exact candidate is technically complete without a real Factorio run, human verdict, public Play route, or authority promotion.
The planned host-environment spine is a non-blocking parallel support lane; it starts read-only and grants no host mutation or privileged authority.
Packages are unsigned and unpublished. The public C ABI and installed SDK remain experimental; neither carries a stable compatibility promise.
Contributor status command: `py -3 tools/project_state.py --summary`.
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
facman play space-age-main  # safely refused until a real-play gate passes
```

When running directly from a checkout, use:

```powershell
$buildRoot = Join-Path ([IO.Path]::GetTempPath()) 'FacMan\manual\native-smoke'
cmake -S . -B $buildRoot
cmake --build $buildRoot --config Debug
& "$buildRoot\Debug\facman.exe" --version
```

The packaged console command is `facman`. Python is used for repository
tooling, validators, and tests; it is not a FacMan product runtime.

The current functional terminal frontend is opt-in at build time and uses the
same direct client and generated command law. `facman-tui` is an unpublished
migration target; the ratified package target is `facman tui` from the same
binary as CLI JSON and human CLI:

```powershell
$tuiRoot = Join-Path ([IO.Path]::GetTempPath()) 'FacMan\manual\tui'
cmake -S . -B $tuiRoot -DFACMAN_BUILD_TUI=ON
cmake --build $tuiRoot --config Debug
& "$tuiRoot\Debug\facman-tui.exe" --list
& "$tuiRoot\Debug\facman-tui.exe" --command workspace.status --json
```

Target-specific Windows, Linux, and macOS x64 TUI profiles are package-preview
lanes. The older OS-neutral `portable_tui_x64` scaffold remains unpublished
and is not used as product proof. The successor package profiles must prove
that `facman` alone supplies every required terminal mode.

## Permanent Rule

```text
Universal Setup mutates installed-software state.
Universal Launcher owns generic runnable/session lifecycle.
FacMan owns the Factorio product, instances, readiness, and launch intent.
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
FacMan Product/Application    Factorio commands, workflows, state, readiness
        |
Presentation + Session        snapshots, actions, identity, revision, recovery
        |
CLI / TUI / WinForms / WinUI / AppKit / SwiftUI / GTK / Qt frontends
```

This repo owns only the Factorio product binding and Factorio-facing app
frontends. Install, repair, uninstall, rollback, and destructive setup mutation
belong to `universal-setup`. Generic runnable references and durable
operation/session/Last Run lifecycle belong to `universal-launcher`. Factorio
installations, instances, profiles, configuration, mods/modsets, saves,
readiness, launch intent, presentation, release, and support belong to FacMan.

## Safety Defaults

- No bundled Factorio binaries.
- No passwords or tokens in manifests.
- No repair or uninstall for Steam or otherwise foreign-owned installs.
- No undisclosed writes to external Factorio, Steam, or platform state.
- No global mod folder swapping.
- Launch planning and preflight are available. Execution remains unavailable
  until either the Steam-aware instance-isolated or standalone hermetic
  real-play gate passes; fake-process supervision proof grants no real-product
  authority.
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
The bounded process, admission, and session-journal design is described in the
[execution-foundation architecture](docs/architecture/execution_foundation.md).
Cross-repository ownership and temporary launcher incubators are recorded in
the [component-ownership architecture](docs/architecture/component_ownership.md)
and its machine-readable manifest.

## AIDE Lite

This repo includes AIDE Lite as development governance tooling only. It is not
part of the launcher runtime and must not be bundled in production packages.
See [docs/architecture/aide_lite_integration.md](docs/architecture/aide_lite_integration.md).
Current machine-readable truth is `.aide/memory/project-state.v2.json`; the
compact reviewed-checkpoint product view is
`release/index/current_state.v1.toml`, and the human summary is generated from
the same canonical inputs. Live checkout/provider identity is emitted outside
the source tree by `tools/current_checkout_observation.py`. Its provider-ref
evidence is an offline, policy-bound local tracking-ref observation, not a live
remote query or the separate empty-clone source-closure proof; tracked state
does not impersonate either. Closed task
evidence is hash-indexed under `.aide/history/` and excluded from ordinary
context packets.

Before large native implementation work, review
[docs/architecture/pre_code_structure_review.md](docs/architecture/pre_code_structure_review.md).

## Roadmap

The executable plan lives in [release/index/plan.v1.toml](release/index/plan.v1.toml),
with generated operator views in [todo.md](todo.md) and
[docs/roadmap/current.md](docs/roadmap/current.md). Durable product architecture
remains in [docs/product/master_plan.md](docs/product/master_plan.md), while the
historical detailed roadmap remains in [docs/roadmap.md](docs/roadmap.md).
The current target is the smallest trustworthy path from selecting an instance
to opening Factorio's menu with that environment active; managed-install
expansion resumes after playable alpha.
