# Functional Terminal Frontend

## Current implementation

`FACMAN-TUI-MINIMUM-PRODUCT-01` replaced the old message-only executable with
a portable C++17 command explorer over `facman::client::FacManClient` and
`DirectFlbTransport`. It consumes the generated command catalog, supports
direct and bounded-process transports, keeps daemon transport refused, and has
useful line-oriented forms, cancellation, redirection, Unicode, no-color,
authority-refusal, and package smokes.

It currently builds as the unpublished `facman-tui` developer executable. That
is a migration baseline, not the release target and not ordinary-workflow
parity.

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

The complete target architecture and delivery sequence are in
[`unified_interaction_platform.v1.md`](../architecture/unified_interaction_platform.v1.md).
