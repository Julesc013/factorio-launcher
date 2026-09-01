# FacMan 0.1 foundation public beta contract

FacMan 0.1 is shaped like the eventual 1.0 product while deliberately carrying
a smaller, evidence-backed feature set. It is one product named **FacMan**, one
terminal executable named `facman`, one same-binary TUI route (`facman tui`),
and two user downloads per platform: portable and setup.

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
- WinForms as the Windows reference GUI, with AppKit Intel and GTK 3/X11 as experimental previews. CLI JSON is the automation contract; human CLI and same-binary TUI cover operator workflows.

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

## Deliberate deferrals

0.1 does not promise Mod Portal networking, credential storage, automatic
update, daemon/remote administration, plugins, a public provider SDK, server
execution, store mutation, Apple Silicon/universal macOS, Wayland-native
behavior, or general Linux distribution compatibility. Those systems remain
extension seams, not hidden half-features.

## Completion law

Machine validation can prove implementation, determinism, packaging, security
boundaries, migrations, and cross-frontend semantic contracts. It cannot
fabricate real Play, live managed-install, accessibility, signing,
notarization, or publication evidence. Those gates remain visibly pending
until the named operator performs and accepts them. A stable `0.1.0` release
also requires a clean exact source revision, immutable forward-only release
identity, and protected-branch promotion.
