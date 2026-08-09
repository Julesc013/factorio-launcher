---
document_id: FACMAN-C1-RELEASE-CONTRACT
schema_version: "1.0"
status: accepted
release: FacMan-C1-internal-alpha-foundation
legacy_release_label: FacMan-0.1.0-C1
accepted: 2026-08-01
last_reviewed: 2026-08-10
workunit: FACMAN-C1-CUTLINE-01
---

# FacMan C1 internal-alpha foundation contract

## Product outcome

FacMan C1 is complete when a player can open a native FacMan GUI, select
or create one isolated vanilla instance backed by an existing standalone
Factorio installation, understand readiness, choose Play, reach the ordinary
Factorio menu, observe the session, exit, relaunch, and receive a truthful
recovery path after interruption.

This is the complete bounded internal-alpha foundation. It is not public
`0.1.0`, a stable support claim, or the complete long-term FacMan vision.

## Relationship to public releases

C1 proves the first end-to-end route, semantic projection, package and
recovery spine from which the larger product can be built. It deliberately
does not close the public capability matrix.

Public `0.1.0` requires every admitted Windows 10/11 x64 capability to be real
and complete through the shared backend, CLI, TUI and WinForms. `1.0.0`
requires the complete admitted matrix through CLI, TUI, WinForms, AppKit, GTK
and Qt on their exact supported profiles. In both cases, “complete” means no
required fixture-only behavior, scaffold, permanent refusal, hidden Advanced
dependency, undocumented command or missing refusal/recovery/package/
accessibility/documentation evidence.

The release train and finite matrices are governed by:

- [`version_train.v1.toml`](../../release/index/version_train.v1.toml)
- [`autonomy_policy.v1.toml`](../../release/index/autonomy_policy.v1.toml)
- [`milestones.v1.toml`](../../release/index/milestones.v1.toml)
- [`capability_frontend_matrix.v1.toml`](../../release/index/capability_frontend_matrix.v1.toml)
- [`withdrawal_policy.v1.toml`](../../release/index/withdrawal_policy.v1.toml)

Those are ratified planning contracts with activation gates. This C1 record
does not allocate a public version, authorize a tag, promote a route, sign,
publish, support or withdraw a release. Autonomous construction and alpha
qualification may proceed between gates; human validation occurs at the end
of beta, release-candidate and stable trains after automated evidence closes.

## Visible product

The shell has four top-level pages and one persistent product surface:

1. Instances
2. Installations
3. Activity
4. Settings / About
5. Launch Deck

First Run, instance list, instance summary/readiness, last run, and Recovery
Center are focused states inside those pages. The generated command explorer
remains available under **Advanced** and is not the home screen.

The minimum semantic projection is experimental and FacMan-local:

```text
facman.presentation.v0

ShellSnapshot
InstanceListView
InstanceSummaryView
ReadinessView
LaunchDeckView
ActionDescriptor
ActivityView
OperationView
RecoveryView
```

It is encoded through the existing machine transport. It is not a stable
public ABI and is not promoted into Universal Launcher before C1. Promotion is
revisited only after C1 and a second real product consumer.

## Platform and package cut

| Platform lane | C1 GUI | August package | Initial claim |
| --- | --- | --- | --- |
| Windows 10/11 x64 | WinForms | Portable ZIP first | Supported reference after complete live journey and package evidence |
| macOS 10.13+ x86_64 | AppKit | `.app`; DMG only when ready | Preview until runtime, package, accessibility, and real Play evidence pass |
| Frozen Linux x64/X11 baseline | GTK 3 C API with C++17 adapter | Self-contained tarball first | Preview until runtime, package, accessibility, and real Play evidence pass |

All three artifacts may be retained as internal or explicitly admitted preview
outputs from one candidate. Availability never
implies an unsupported stable claim. Signing and notarization are required for
claims that depend on publisher authenticity, but missing credentials do not
justify a false claim or block unsigned preview construction and testing.

Windows x86, macOS i386/10.9, Linux i686, Wayland-native qualification, WinUI,
SwiftUI, and Qt 6 are outside the August critical path.

## Frozen runtime and transport

The original C1 definition treated this qualified composition as frozen:

```text
FacMan source       8f495d63b412a3af5a22305d9d8b424efd4303d2
Universal Launcher  7fc25340623131ba86c08dca4fb8a43b18a4520d
Universal Setup     3048128963dc718a7c38c1cfcdda9e813a23b0db
```

Those hashes are retained as definition-time history. Current builds use the
canonical workspace/provider locks and active route selected by release-index
truth; this document neither repins a provider nor rewrites an immutable route.

C1 retains the bounded stdio process transport:

```text
WinForms --+
AppKit   ---+-- facman RPC process transport -- frozen core
GTK 3    --+
```

No C1 task replaces it with P/Invoke, a Swift/Objective-C bridge, a daemon, a
new service protocol, or dynamic providers. The backend operation owns the
process session and journal. Closing a frontend cannot convert an active or
interrupted backend operation into ordinary cancellation.

The process-transport exception exits after C1 only when direct bindings or a
durable host demonstrate measured value.

## Pre-packaged live acceptance prerequisites

Three bounded work units now sit on the canonical C1 path before packaged live
acceptance:

```text
FACMAN-WINFORMS-C1-TRANSPORT-HARDENING-01
FACMAN-C1-BACKEND-IDENTITY-01
FACMAN-WORKSPACE-ROOT-AUTHORITY-01
```

They must prove truthful bounded transport failure semantics, an exact
package-relative backend/contract identity, and no-follow workspace-root
ownership respectively. They retain the existing C1 process protocol and may
not repin a provider, change the active Play candidate, widen Setup authority,
or grant observer, permit, execution, route, signing, publication, or release
authority.

The Windows release-candidate work unit remains active and fail-closed.
Revalidation-04 is superseded and archived before observer self-test; it is
historical evidence, not a resumable gate. The release sequence is:

```text
transport hardening + backend identity
-> workspace-root authority
-> fresh successor route definition
-> fresh remote-only source closure
-> fresh successor qualification
-> new stage -> observer -> prepare -> permit -> two launches -> verdict
-> exact route capability and promotion after Pass
-> exact Windows package and packaged live acceptance
-> clean Windows 10/11 x64 qualification
-> keyboard, DPI, high-contrast, and accessibility acceptance
-> signing or explicit unsigned-preview classification
-> internal C1 alpha evidence checkpoint
```

Planning this sequence changes no candidate identity or authority state. The
three hardening WorkUnits precede successor construction; every later stage is
formed from fresh evidence and separate authority.

## Authority-only Play gate

The retained revalidation-04 record remains blocked and historical. It cannot
be restarted, resumed, prepared, or executed. Its former authority boundary
continues to prevent accidental promotion of:

```text
FACMAN-EXACT-PLAY-ROUTE-CAPABILITY-01
FACMAN-WINDOWS-INSTANCE-ISOLATED-PLAY-ROUTE-PROMOTION-01
C1-LIVE-PLAY-ACCEPTANCE-01
```

It does not block the C1 cut-line, journeys, presentation fixtures, native
shells, refusal UI, Activity, recovery, provisional candidate construction,
preview packaging, accessibility work, support documentation, or the three
pre-successor hardening WorkUnits. Until a fresh successor passes and its route
is promoted, Play presents the exact structured unavailable state and does not
execute.

Jules's retained revalidation-04 operator designation is historical only. It
grants no observer capture, `prepare`, permit, Factorio execution, human
verdict, route, signing, or publication authority. A successor requires a new
WorkUnit, qualification, stage, and separately recorded authority chain.

GUI-only changes do not invalidate route evidence unless they change the
execution binary, launch plan, route policy, provider pin, instance binding,
operation semantics, or package closure containing the qualified runtime.

## Native OEM+ shell

C1 uses native title bars, menus, controls, fonts, focus behavior, system
light/high-contrast behavior, a FacMan icon, restrained accent, product status
icons, and one branded Launch Deck.

Only two appearance modes ship:

```text
System Native
FacMan OEM+
```

System Native is the recovery appearance. Custom chrome, custom fonts,
arbitrary CSS/QML/XAML packages, user-replaceable layouts, animated materials,
and theme marketplaces are deferred.

## Included journey

```text
start FacMan
-> find/select an existing standalone Factorio installation
-> create or select one isolated vanilla instance
-> show readiness or one actionable blocker
-> Play to the normal Factorio menu when the route is authorized
-> supervise exit and show last run
-> relaunch
-> provide truthful recovery after interruption
```

The paired refusal journey changes or invalidates readiness after it was
computed. FacMan refuses stale authority, explains why, and offers a rescan or
recovery action. Fixture-backed positive, refusal, running, exited, and
interrupted states proceed before live Play authority exists.

## Explicit exclusions

C1 excludes managed Factorio installation/repair/update/removal, Steam-specific
execution, Mod Portal access, mod downloading, managed modsets, accounts,
credential storage, save synchronization, self-update, cloud features, remote
News, arbitrary themes, daemons, plugins, marketplaces, servers, development
tooling, public SDK stabilization, and repository reorganization.

News and remote feeds are post-C1. Mods and managed content begin at C2.
Managed installation mutation begins at C3. Accounts, authentication, and
network extension begin at C4. Stable cross-platform and release-service
claims remain evidence-driven rather than calendar-driven.

## Foundation evidence

The supported Windows claim requires the positive and refusal journeys,
operation-death and stale-readiness journeys, clean-profile runtime, support
bundle redaction, reproducible package construction, keyboard operation,
access keys, focus order, accessible names, contrast, and 100%, 150%, and 200%
scaling.

AppKit and GTK artifacts require real bundle/package runtime smoke and the same
fixture semantics before preview publication. Their stable promotion requires
their own real Play, accessibility, package, install/removal, and support
evidence.

Artifacts carry version metadata, licenses, checksums, SBOM, provenance,
candidate notes, known limitations, and removal instructions. P0 security or
data-loss defects, P1 journey blockers, packaging defects, and accessibility
failures block the C1 checkpoint. Deferred features do not re-enter C1 without
removing scope of comparable cost. Passing C1 remains necessary evidence for a
later public train; it is not sufficient evidence for `0.1.0` or `1.0.0`.
