# Functional Terminal Frontend

## Current implementation

`FACMAN-TERMINAL-FRONTEND-FOUNDATION-01` embeds the portable C++17 terminal host
in `facman`. The generated command browser is retained under Advanced, while a
dependency-free linear renderer supplies the deterministic redirected, dumb,
safe-mode, and no-color path. `FrontendSession` normalizes direct, bounded
process, and explicitly refused service transports, negotiates backend and
provider identity, and carries request/operation/attempt correlation without
owning product state.

`facman-tui` is only an opt-in unpublished compatibility build. Product
profiles map CLI and TUI roles to the same `facman` artifact. This foundation
is the exact parent of the active ordinary-shell WorkUnit.

`FACMAN-SAME-BINARY-TUI-PARITY-01` now supplies the first task-oriented product
shell. Its pure `TuiState` reducer consumes immutable presentation snapshots
and produces a toolkit-neutral render model. A narrow controller is the only
terminal layer allowed to call `FrontendSession`; renderers never call the
backend. The shell provides Home, Instances, Installations, Content, Saves,
Activity, Settings, and Advanced, with a persistent Launch Deck. The existing
generated browser remains intact under Advanced and `--interactive` remains a
compatibility alias for it.

## Ratified product target

The Technical Preview requires:

```text
facman <command>          bounded human CLI
facman <command> --json   normative machine contract
facman tui                task-oriented terminal UI
```

`facman tui` shares the executable, generated command specification,
presentation query/action service, frontend session, operation identity,
Last Run authority, and package identity with the CLI. Instances,
Installations, Activity/Last Run, Settings/Support/About, and the Launch Deck
are designed ordinary views. The generated command explorer remains available
under Advanced for complete command coverage.

The project-owned, dependency-free full-screen renderer is replaceable behind
`ProductRenderer` and is paired with the mandatory linear renderer. Capability
selection admits full-screen mode only for an interactive VT/ConPTY terminal;
redirected, dumb, no-color, safe, and explicit plain paths remain linear. TTY detection never changes
script behavior; JSON and redirected output never receive cursor control.
Themes, keymaps, layout preferences, and shortcuts are validated data and
cannot bypass backend action or authority law.

Writes retain explicit review and `--apply` semantics. Execution cannot be
promoted by a frontend flag. Frontend close, timeout, transport loss,
cancellation, backend restart, unknown outcome, and recovery-required states
must preserve the backend/ULK terminal result.

The interaction model defines the complete extensible form vocabulary—string,
multiline, integer, boolean, enum, multi-select, path, size, duration, version,
digest, and secret reference—plus defaults, choices, conditional visibility,
validation, plan preview, and digest confirmation. Only forms needed by an
admitted product journey should become ordinary UI; exhaustive generated forms
remain Advanced and secrets are never rendered as values.

## Current proof and remaining closure

The current slice proves reducer/snapshot/action parsing, bounded 80x24 and
narrow render models, ASCII linear output, NO_COLOR fallback, redirected EOF,
ordinary-page navigation, read-only semantic action dispatch, and the
ordinary-to-Advanced same-process handoff. Existing CLI JSON, direct/process
transport, cancellation, and generated-form tests remain unchanged.

The WorkUnit remains active until hosted Windows/macOS/Linux PTY or ConPTY
interaction, suspend/resume and resize, package one-binary proof, complete
fake-process journey semantics, transport faults, authoritative ULK Last Run,
and accessibility receipts close. Content, Saves, and Settings are visible
ordinary routes but currently direct exhaustive operations to Advanced; no
Technical Preview-required journey may remain there at closeout.

The closeout implementation owns terminal lifetime explicitly. Full-screen,
cursor, raw-console/termios, and signal state are scoped resources; POSIX Ctrl+C
is a typed cancel event, job-control suspension restores and resumes the
terminal, and termination leaves a bounded exit result after restoration.
Terminals below 40x12 switch to the linear transcript rather than rendering
against invented dimensions.

Terminal text is decoded and clipped by display cells rather than UTF-8 bytes.
Wide characters, combining marks, joined emoji, variation selectors, invalid
input, and control-character sanitization are handled inside the replaceable
renderer boundary. Backend-projected text can therefore never inject terminal
control sequences through the ordinary renderer.

Frontend interaction state may retain a selected record identity. Descriptive
attributes such as version, profile and readiness are never retained as a
fallback cache: they must be present in a fresh backend projection. Each new
semantic action intent receives a new request/idempotency identity even when
the snapshot revision has not changed; a retry of that same dispatch retains
its identity.

The renderer decision is `project_owned_dependency_free_full_screen_plus_linear`.
FTXUI remains optional and unadmitted; it is unnecessary for this shell and may
be considered only after offline source closure, licence/SBOM, portability,
accessibility, security, performance, compatibility, and rollback gates pass.

The target architecture is in
[`unified_interaction_platform.v1.md`](../architecture/unified_interaction_platform.v1.md).
The module decomposition, renderer admission, portability, accessibility,
compatibility, parity TCK, de-scope rules, and implementation checklist are
in [`interaction_platform_execution_programme.v1.md`](../architecture/interaction_platform_execution_programme.v1.md).
The active closeout evidence is recorded in
[`facman-same-binary-tui-parity-closeout-01.md`](../release/checkpoints/facman-same-binary-tui-parity-closeout-01.md).
