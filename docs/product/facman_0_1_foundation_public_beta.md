# FacMan 0.1 foundation public beta contract

FacMan 0.1 is shaped like the eventual 1.0 product while deliberately carrying
a smaller, evidence-backed feature set. It is one product named **FacMan**, one
terminal executable named `facman`, one same-binary TUI route (`facman tui`),
and an existing Alpha.5 portable/setup distribution. Prospective corrected
delivery requirements are recorded in `release/index/plan.v1.toml` under
`delivery_train`; their in-progress admission does not qualify new packages or
activate support, execution, signing or publication.

The architectural boundary is already the long-term one. FacMan owns
Factorio-specific intent and policy; Universal Launcher owns generic
process/session lifecycle; Universal Setup owns installed-software mutation.
Native GUIs and the TUI are projections of the same semantic backend and do
not acquire independent product policy.

## Included 0.1 spine

- Workspace startup, diagnostics, recovery, preferences, and redacted support export.
- Supported-install discovery and read-only registration of foreign installations.
- Isolated instance and profile lifecycle, configuration explanation, local mods and modsets, saves, snapshots, readiness, launch preview, and session/Last Run inspection.
- Explicit Play only through a separately qualified route; unavailable authority is rendered as a structured refusal.
- Managed installation only into a new, explicitly selected, FacMan-owned target after plan review and confirmation, with verification and recovery. No adoption or mutation of a foreign installation is inferred.
- Complete human CLI, JSON/RPC, ordinary full-screen TUI and linear TUI for every declared local J01-J12 journey on Windows x64, Linux x64 and macOS Intel x64, without GUI/display dependencies or Advanced fallback.
- Complete WinForms and GTK3 reference desktops and field hardening before plain 0.1.0. Maintain AppKit preview and contract tests; full AppKit/native macOS desktop graduation belongs to 0.4. Current GTK3/AppKit qualification remains experimental until new exact evidence exists.

## Distribution and resource law

The product stage contains the public entrypoints, required runtime libraries,
`facman.resources`, selected user documentation, licenses, and product
manifests. `facman.resources` is deterministic, self-describing, hash-verified,
bounded on read, and safely exportable for diagnostics. Product stages exclude
SDK headers and metadata, repository tools/tests, raw evidence, and loose
contract/content trees.

Portable and setup packages are adapters over the same verified stage. Toolkit
implementation names and legacy compatibility executable names are not public
artifacts. Exact provider revisions are materialized outside the source
checkout in detached, marker-owned caches; live sibling worktrees are never
repurposed as build inputs.

The prospective Terminal profile excludes GUI payload. Desktop adds a native
GUI overlay to the same terminal component; both need portable and installed
use. The current three-profile/eight-asset selector remains unchanged until
new producers, profiles, manifests and qualification agree. Asset counts are
derived from admitted profiles, not inferred from this scope amendment.

## Deliberate deferrals

0.1 does not promise Mod Portal networking, credential storage, automatic
update, daemon/remote administration, plugins, a public provider SDK, server
execution, store mutation, Apple Silicon/universal macOS or general Linux
distribution compatibility. Selected GTK X11/Wayland qualification is required
before claiming either backend; terminal operation does not require either.
Acquisition/credentials/Mod Portal become functional in 0.2, bounded local
hosting in 0.3, and full AppKit desktop in 0.4. Prepare only justified consumed
mechanisms now; scaffolds and speculative stable APIs cannot count as features.

## Completion law

Machine validation can prove implementation, determinism, packaging, security
boundaries, migrations, and cross-frontend semantic contracts. It cannot
fabricate real Play, live managed-install, accessibility, signing,
notarization, or publication evidence. Those gates remain visibly pending
until the named operator performs and accepts them. A stable `0.1.0` release
also requires a clean exact source revision, immutable forward-only release
identity, and protected-branch promotion.

The internal order is integrated local application, Terminal v1 machine
completion, WinForms/GTK3 reference-desktop machine completion, then accepted
0.1 release. Mechanical testing and remediation are autonomous within the
actual authority envelope. Real effects need observed evidence and permitted
disposable hosts; automated findings do not become invented human testimony.
