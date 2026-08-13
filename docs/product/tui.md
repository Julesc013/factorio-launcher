# Functional Terminal Frontend

## Current implementation

`FACMAN-TERMINAL-FRONTEND-FOUNDATION-01` embeds the portable C++17 terminal host
in `facman`. The generated command browser is retained under Advanced, while a
dependency-free linear renderer supplies the deterministic redirected, dumb,
safe-mode, and no-color path. `FrontendSession` normalizes direct, bounded
process, and explicitly refused service transports, negotiates backend and
provider identity, and carries request/operation/attempt correlation without
owning product state.

`facman-tui` is now only an opt-in unpublished compatibility build. Product
profiles map CLI and TUI roles to the same `facman` artifact. This foundation
does not yet claim ordinary-workflow parity or a qualified full-screen adapter.

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

The full-screen renderer is replaceable behind a project-owned interface and
is paired with a dependency-free linear renderer. TTY detection never changes
script behavior; JSON and redirected output never receive cursor control.
Themes, keymaps, layout preferences, and shortcuts are validated data and
cannot bypass backend action or authority law.

Writes retain explicit review and `--apply` semantics. Execution cannot be
promoted by a frontend flag. Frontend close, timeout, transport loss,
cancellation, backend restart, unknown outcome, and recovery-required states
must preserve the backend/ULK terminal result.

## Proof and packaging

`FACMAN-SAME-BINARY-TUI-PARITY-01` will add generated command/action equality,
headless view-model goldens, PTY/ConPTY runs on Windows/macOS/Linux,
accessibility/linear-mode evidence, transport fault proof, and a mutation gate
against silent parity gaps. The Windows Technical Preview package must prove
that `facman` alone provides CLI JSON, human CLI, and TUI behavior.

The renderer admission decision for the foundation is
`linear_only_pending_full_screen_adapter_qualification`. FTXUI remains the
preferred candidate, but no third-party renderer is pinned or shipped until its
offline source closure, licence/SBOM, portability, accessibility, security,
performance, compatibility, and rollback gates pass.

The target architecture is in
[`unified_interaction_platform.v1.md`](../architecture/unified_interaction_platform.v1.md).
The module decomposition, renderer admission, portability, accessibility,
compatibility, parity TCK, de-scope rules, and implementation checklist are
in [`interaction_platform_execution_programme.v1.md`](../architecture/interaction_platform_execution_programme.v1.md).
