# Functional Terminal Frontend

`FACMAN-TUI-MINIMUM-PRODUCT-01` replaces the old message-only executable with
a portable C++17 frontend over `facman::client::FacManClient` and
`DirectFlbTransport`. It consumes `apps/tui/generated_command_catalog.hpp`, so
it neither owns command metadata nor implements Factorio behavior.

## Product Surface

The interactive menu provides entry points for status, doctor, installs,
instances, launch planning, modsets, saves, diagnostics, recovery, and
capabilities. `--command` accepts any generated contract ID or runtime ID. The
structured mode passes the typed backend payload through unchanged; the human
mode adds only command/outcome context.

Writes require the explicit `--apply` flag. Without it, generated
`persistent_local_write` commands are dispatched as dry-run requests. Process
execution is not enabled: `run.execute` remains unavailable even with
`--apply`, and the backend refusal code remains `isolation_not_proven`.

## Terminal Boundaries

- interactive mode is selected only when both standard input and output are
  terminals, unless `--interactive` is explicit;
- redirected execution defaults to `workspace.status` and emits no cursor
  control;
- `NO_COLOR` and narrow/plain terminals require no color or wide-layout
  semantics;
- response display is capped at 1 MiB;
- cancellation and positive timeout validation use the reusable client;
- the Windows executable carries the UTF-8 and long-path manifest;
- read-only commands do not initialize an empty workspace.

## Proof and Packaging

Native and Python smokes cover generated-catalog parity, empty and Unicode
workspaces, redirected streams, structured passthrough, cancellation,
authority refusal, and bounded read-only status. Package runtime smoke invokes
the TUI after CLI integrity verification and checks the same authority state.

Three target-specific x64 package-preview profiles exist. They remain unsigned
and unpublished release artifacts until their exact-head native/package CI
lanes pass. The old OS-neutral `portable_tui_x64` profile remains disabled and
does not support a product claim.
