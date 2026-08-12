# FacMan 0.1 Windows Technical Preview contract

Status: candidate scope contract; no execution, qualification, release, signing,
publication, or support authority is granted.

Canonical milestone: `FACMAN-0.1-WINDOWS-TECHNICAL-PREVIEW` in
`release/index/plan.v1.toml`. Canonical required and deferred capability IDs
live in `release/index/technical_preview_scope.v1.toml`; the factual census is
`release/index/capability_frontend_matrix.v1.toml`.

## Product cut

FacMan `0.1.0` is a Windows x64 Technical Preview for one existing-install,
isolated-instance journey. WinForms is the primary ordinary-user surface. CLI
JSON is the normative automation and test contract. Human CLI is required for
Doctor, diagnostics, status, support, and recovery. The TUI remains a tested,
grammar-generated command explorer and is not an ordinary-workflow parity
blocker.

The preview discovers and registers an existing standalone installation
read-only, creates or selects an isolated FacMan instance, computes Factorio
readiness, renders the Launch Deck, requests the qualified launch-to-menu route
or explains its structured unavailability, and exposes session, Last Run,
relaunch, and recovery state.

## Explicit deferrals

Managed installation, selected-save launch, accounts, acquisition, network and
storefront mutation, self-update, system-wide installation, elevation, native
installers, servers, other platforms, public provider APIs, a daemon, remote
administration, and plugins are outside this milestone. Their registered
commands and schemas do not make them implemented or release-blocking.

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

The milestone produces an unsigned internal candidate. Public publication
requires a separately frozen exact RC, immutable reconstruction, a qualified
real route, a current human experiential/accessibility receipt, production
signing, and explicit D4 promotion. The current exact route target is Factorio
2.0.77 while the retained real archive corpus is 2.1.14; a reviewed decision is
required and silent substitution is forbidden.

No frontend may become a second readiness or Last Run authority. If one
complete bounded semantic migration cannot be finished, work stops at
characterization tests and non-authorizing contracts.
