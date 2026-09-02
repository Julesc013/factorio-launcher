# FacMan 0.1 Windows reference and preview contract

Status: the original Windows-only Technical Preview is retained as the
reference-platform contract, but its sequencing is superseded by the active
alpha.5 beta-readiness programme. No human verdict, execution, release,
signing, publication, or support authority is granted.

Canonical milestone: `FACMAN-0.1-WINDOWS-TECHNICAL-PREVIEW` in
`release/index/plan.v1.toml`. Canonical required and deferred capability IDs
live in `release/index/technical_preview_scope.v1.toml`; the factual census is
`release/index/capability_frontend_matrix.v1.toml`.

## Active product cut

Windows 10/11 x64 remains the reference `0.1` lane. WinForms on .NET Framework
4.8 is its ordinary-user surface. CLI JSON is the normative automation and test
contract. Human CLI is required for Doctor, diagnostics, status, support, and
recovery. The TUI is the required task-oriented projection invoked as
`facman tui`; its Advanced surface is generated from the same command
specification as the CLI. No package requires a separate TUI executable.

The active alpha.5 programme also produces explicitly unsupported semantic
previews for GTK3 on Ubuntu 24.04 x64/X11 and AppKit on macOS 13+ Intel. Each
platform has one portable and one setup candidate. These previews do not turn
the Windows reference contract into a three-platform support promise.

The preview discovers and registers an existing standalone installation
read-only, creates or selects an isolated FacMan instance, computes Factorio
readiness, renders the Launch Deck, requests the qualified launch-to-menu route
or explains its structured unavailability, and exposes session, Last Run,
relaunch, and recovery state.

## Reconciled deferrals

Managed local-source installation is no longer deferred beyond 0.1 beta. It is
an open release-blocking journey limited to a fresh, explicitly selected
FacMan-owned target with plan, confirmation, apply, verify, recovery, repair,
and uninstall. No live-target human acceptance is claimed.

GTK3 and AppKit preview packaging is also inside the active 0.1 candidate
scope; semantic and human parity remains open. Selected-save launch, accounts,
acquisition, network/storefront mutation, self-update, system-wide install,
elevation, servers, public provider APIs, a daemon, remote administration, and
plugins remain outside beta. Qt6 is a scaffold only; Qt6, WinUI, and SwiftUI
are separate post-beta admission lanes. Registered commands and schemas do not
make a deferred capability implemented.

## Ownership and persistence

FacMan owns Factorio installation classification, instances, profiles,
configuration, mods/modsets, saves, readiness, launch intent, presentation,
release, and support. Universal Launcher owns only opaque runnable references
and generic operation/process/session/Last Run lifecycle. Universal Setup owns
installed-software mutation, installed state, setup transactions, recovery,
and audit.

The existing human-readable JSON/TOML workspace store remains authoritative.
SQLite is not introduced as canonical state. A later SQLite index may be
considered only as a rebuildable derivative after measured query/concurrency
pressure or a materially different second consumer.

## Candidate and publication law

Exact candidate run `33576140943`, attempt 1 passed five jobs from source
revision `a7a518dbfe2a6d54da7b9c84fbd318300265e31d` and tree
`1ebcd2b230ed188e021880ffa4c438de2ede655b`. Four workflow artifacts culminated
in a download-back-verified 14-file internal unsigned, unpublished evidence
bundle. It is not the final public eight-asset matrix. The non-authorizing
receipt is `release/index/alpha5_promotion_candidate_closeout.v1.toml`.

The run machine-qualified WinForms as the reference product and GTK3/AppKit as
semantic previews. It did not supply human install, accessibility, packaged
performance/security/fault, managed-install, or real Play verdicts. Public
publication requires a separately frozen exact candidate, immutable
reconstruction, a qualified real route, current human receipts, production
signing/notarization as applicable, and explicit promotion. The current exact
route target is Factorio 2.0.77 while the retained real archive corpus is
2.1.14; a reviewed decision is required and silent substitution is forbidden.

Candidate evidence is source-bound. The receipt does not qualify its closeout
revision or any future revision; each changed source needs a fresh run.

No frontend may become a second readiness or Last Run authority. If one
complete bounded semantic migration cannot be finished, work stops at
characterization tests and non-authorizing contracts.

The detailed interaction, accessibility, compatibility, customization,
machine/agent, and future local-service law is frozen in
[`unified_interaction_platform.v1.md`](../architecture/unified_interaction_platform.v1.md).
Its dependency-ordered implementation and qualification checklist is
[`interaction_platform_execution_programme.v1.md`](../architecture/interaction_platform_execution_programme.v1.md).
The required fake-process journey closes through CLI JSON, WinForms, and the
same-binary TUI. AppKit and GTK are inside the current package-preview cut but
outside the prospective Windows support cut; neither may retain an independent
readiness, session, or Last Run authority.
