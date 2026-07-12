# Operational UX

FacMan's TUI, WinForms, and AppKit clients consume the generated command
grammar. They do not decide instance, snapshot, modset, save, retention, server,
transaction, or recovery behavior.

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

WinForms and AppKit expose generated command forms and generic views for
instance diffs, snapshots, modset plans, save and retention results, server
plans, and transaction/recovery state. These views format structured results;
they do not reproduce backend policy.
