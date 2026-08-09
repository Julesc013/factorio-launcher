# Product Charter

FacMan is an unofficial, native, portable, scriptable, instance-centric
launcher and environment manager for Factorio.

Its user promise is:

> FacMan lets players create any number of independent Factorio setups, select
> one, and launch the normal game as though Factorio had always been installed
> and configured exactly that way.

Its long-term outcome is to make every player-defined Factorio environment
understandable, playable, reproducible, repairable, portable, and recoverable
without silently taking ownership of foreign software or data.

The primary persona is a Factorio player who wants multiple complete, isolated
game environments without rebuilding versions, mods, profiles, accounts,
settings, and resources by hand or learning launcher internals.

Its value is not simply launching Factorio. Its value is:

```text
many installations and Factorio versions, safely selected
many isolated instances, each independently reproducible
many profiles and presets, explicitly composed
many modpacks and modsets, reproducibly locked
many account references, provider-scoped and secret-free
many saves/worlds per instance, protected and backed up
many frontends, one command graph
many platforms, one native core
many products later, one universal launcher pattern
```

The golden journey is:

```text
Find Factorio,
create, clone, import, or select an instance,
choose its version, profile, preset, modpack, account, settings, and resources,
review readiness and the advertised isolation guarantee,
press Play and arrive at Factorio's main menu,
select or create a save inside Factorio,
save and exit,
then relaunch the same instance with an explainable last-run result.
```

Saves/worlds are optional content inside an instance, not the required launch
aggregate. Direct save loading may exist as an explicit launch intent, but
`facman play <instance>` opens the game menu by default.

Any requested combination can be represented, compared, planned, and
explained. Only compatible, player-owned, provider-supported, policy-admitted
combinations can be prepared or executed; FacMan does not emulate entitlement
or silently substitute versions, mods, accounts, installations, or settings.

Advanced installation, instance, profile, preset, modpack/modset, account,
save, diagnostic, and automation surfaces remain available through the CLI,
TUI, and command explorer.

## Product and platform ownership

FacMan is the Factorio product. It owns Factorio meaning, compatibility,
instances, readiness, content, launch intent, policy, acquisition decisions,
native presentation, support, release selection and the exact resolved product
graph.

The sibling providers remain separately releasable:

- ULK is the Universal Launcher semantic kernel; ULU is its experimental
  process/session/persistence and platform-provider host.
- USK is the Universal Setup semantic kernel; USU is its experimental
  source/archive/filesystem/elevation/trust provider host.

Those four layers live in the existing Universal Launcher and Universal Setup
repositories. They do not create a fourth repository or justify a mass rewrite.
Product-neutral behavior moves only through characterized, additive and
reversible provider/consumer changes.

## Release milestones

C1 is the internal alpha foundation for one exact Windows route, bounded
WinForms journey, package and recovery evidence. It does not equal the first
public version.

`0.1.0` is the first public beta. It is complete only when every capability in
the frozen finite Windows 10/11 x64 matrix is implemented end to end through
one semantic backend, CLI, TUI and WinForms, including its required refusals,
recovery, package proof, accessibility and documentation. A required ordinary
journey may not be fixture-only, a scaffold, permanently disabled, hidden in
Advanced or dependent on an undocumented command.

`1.0.0` is the measurable full supported release. Every admitted ordinary
capability must be complete through CLI, TUI, WinForms, AppKit, GTK and Qt Widgets on
its exact supported profiles, with no required matrix gap, no known P0/P1
defect, and complete migration, rollback, package, accessibility, support and
reconstruction evidence. This is a finite completion contract, not a promise
to implement every conceivable integration or to eliminate every possible
future defect.

The exact Windows scope is frozen in the
[0.1 Windows Public Beta contract](facman_0_1_windows_public_beta.md). The
mandatory `1.0` Qt projection is Qt 6 Widgets; Qt Quick/Kirigami is optional
post-`1.0` work.

Autonomous alpha construction and qualification proceed between gates. Human
validation is concentrated at the end of beta, release-candidate and stable
trains after automated evidence is complete.

The governing planning records are
[`version_train.v1.toml`](../../release/index/version_train.v1.toml),
[`autonomy_policy.v1.toml`](../../release/index/autonomy_policy.v1.toml),
[`plan.v1.toml`](../../release/index/plan.v1.toml),
[`capability_frontend_matrix.v1.toml`](../../release/index/capability_frontend_matrix.v1.toml),
and the [append-only release ledger](../../release/ledger/README.md).
Their activation gates grant no present tag, execution, signing, publication,
support or withdrawal authority.

## Execution Guarantees

FacMan must never describe all execution as simply "isolated." It supports two
separate product modes, each with its own evidence gate:

- **Instance-isolated:** FacMan-owned instance data is isolated. Enumerated
  Steam or platform-owned state may change only after explicit disclosure and
  acknowledgement. This mode cannot carry the hermetic claim.
- **Hermetic standalone:** no persistent change may occur outside the
  authorised FacMan workspace. Any external change fails the claim.

Both modes are accepted product designs and currently unproven. Automated
fake-process tests can validate the supervisor; only revision-pinned real
Factorio evidence and human review can promote either execution claim.

## Product Rules

- No bundled Factorio binaries.
- No ownership bypass.
- No official branding assets.
- Portable interface semantics, native platform presentation, constrained OEM+
  branding, and explicit capability adaptation.
- No toolkit object or frontend-owned authority crosses the presentation
  boundary.
- System Native appearance and accessibility enforcement remain available
  regardless of theme choice.
- No undisclosed writes to external Factorio, Steam, or platform state.
- No global mod folder swapping.
- Dry-run launch plans before execution.
- Managed install operations go through Universal Setup.

## `1.0.0` shape

`1.0.0` is complete when it has proven supported Play routes, read-only install
discovery, ownership classification, multiple isolated instances, portable
instance specifications with explicit local rebinding, profiles, presets,
modpacks and exact modset locks, provider-scoped account references, computed
readiness, dry-run launch/preparation plans, safe launch execution, local
content preparation, save backup, rollback/recovery, managed standalone
lifecycle, diagnostics, signed primary packages, a task-oriented GUI, complete
CLI and TUI coverage, complete WinForms, AppKit, GTK and Qt Widgets projections for the
admitted matrix, and a documented stable workflow-contract subset.

`1.0.0` does not require WinUI, SwiftUI, a web frontend, every legacy operating
system, every storefront, every server or development workflow, remote
administration, AI recommendations, cloud synchronization, or a cross-product
marketplace unless one is explicitly admitted into the frozen `1.0.0` matrix.
Legacy support uses separately qualified target profiles, binaries, providers,
runtime closures and bounded sidecars rather than one binary for all hosts.

## Non-Goals

Do not block the C1 foundation on full GUI parity. Do not make WinForms, Python tooling, or any
frontend the backend. Do not put Mod Portal logic in Universal Launcher. Do not make
Universal Launcher huge before Factorio proves it. Do not make Universal Setup
huge before Dominium proves it. Do not bundle Factorio binaries, repair Steam
installs, manipulate Steam state, touch Steam Cloud files silently, store
Factorio passwords, or make a single executable the architecture. Do not add a
dynamic in-process plugin framework, daemon, or AI action layer before a real
consumer earns the complexity.

Conversely, do not call public `0.1.0` complete while a required Windows
CLI/TUI/WinForms matrix cell is missing, or call `1.0.0` complete while a
required CLI/TUI/WinForms/AppKit/GTK/Qt Widgets cell or its evidence remains open.
