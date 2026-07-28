# Operational UX

FacMan's CLI, TUI, classic native shells, and modern native shells consume the
same command, operation, result, refusal, recovery, page, and semantic-action
contracts. They do not decide instance, snapshot, modset, save, retention,
server, transaction, setup, credential, process, or recovery behavior.

The governing rule is:

> Portable semantics, native presentation, constrained branding, and explicit
> capability adaptation.

Framework choice, platform design language, and deployment-version capability
are separate decisions. The complete shell, appearance, HIG, accessibility,
theming, performance, and frontend-authority contract is defined in
`docs/product/interface_design_system.md`.

The guided TUI supports category navigation, command search, typed required and
optional fields, enum choices, repeatable fields, review, explicit `APPLY`
confirmation for local writes, progress, cancellation, paging, and structured
refusals. `--command`, `--payload`, and `--json` remain stable for automation.
`--color auto|always|never`, `--plain`, `--page-size`, and
`--transport direct|process|daemon` control presentation and transport.
Daemon selection remains an explicit unavailable result.

`NO_COLOR` and `--plain` remove color assumptions, redirected output never
forces terminal controls, and every risk state has a text label. Preferences
supply workspace, transport, color, timeout, and page-size defaults when CLI
options do not override them. No guided-form payload or path history is stored.

Primary product journeys use deliberately designed native task views backed by
immutable shared presentation snapshots. The Instances page, Launch Deck, plan
review, Activity center, and recovery experience must not be generated from
generic command metadata.

Generated command forms remain useful under Advanced for command exploration,
diagnostics, compatibility fallback, experimental commands, and administrative
operations. They format registered schemas and structured results; they neither
reproduce backend policy nor define the player's main workflow.

Classic profiles are WinForms on Windows, AppKit on macOS, and GTK 3 on Linux.
Modern profiles are WinUI 3, SwiftUI for macOS, and Qt Quick Controls with
Kirigami on Linux. Page and action identities are shared; command placement,
menus, settings, button order, shortcuts, control metrics, and visual
capabilities adapt to each platform.
