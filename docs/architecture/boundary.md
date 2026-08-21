# Architecture Boundary

## Universal Setup owns

- install
- verify
- repair
- uninstall
- stage, commit, rollback
- installed-state manifests
- audit logs
- ownership boundaries

## Universal Launcher owns

- product-neutral runnable references;
- generic session, operation, attempt, process, cancellation, and terminal
  outcome semantics;
- authoritative durable session/Last Run journal after exact provider adoption;
- provider-neutral recovery classification and lifecycle TCKs.

Universal Launcher does not own Factorio installations, instances, profiles,
modsets, saves, readiness, launch intent, product navigation, or support policy.

## FacMan and its Factorio binding own

- Factorio install discovery
- Factorio version detection
- Factorio application and user-data layout rules
- Mod Portal adapter
- dependency and modset resolver
- command-line templates
- account token handling
- server workflows
- modder workflows
- Factorio installations and ownership classification
- instances, profiles, configuration, mods/modsets, and saves
- readiness, launch intent, product presentation, release, and support

Frontends must not stack on top of each other as real architecture. CLI, TUI,
WinForms, WinUI, AppKit, SwiftUI, GTK, and Qt all call the same command
graph and application/presentation service through a direct client, bounded
process transport, or a separately admitted local service. CLI JSON, human
CLI, and `facman tui` share one terminal executable, but no renderer is the
backend for another.

Machines and automation agents use the normative structured contract. They do
not scrape human output and receive no authority beyond the same typed action,
revision, idempotency, effect, confirmation, and recovery laws.

`factorio-launcher` must not directly implement repair, uninstall, or managed
install mutation.

See [`unified_interaction_platform.v1.md`](unified_interaction_platform.v1.md)
for the ratified interface and future service/extension boundaries.
