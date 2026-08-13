# Same-binary TUI parity checkpoint

Status: active implementation slice; local Windows qualification passed;
hosted exact-head proof and human review remain required.

## Identity and boundaries

- WorkUnit: `FACMAN-SAME-BINARY-TUI-PARITY-01`
- branch: `task/facman-same-binary-tui-parity-01`
- stacked base: terminal foundation `de3ca04b774027df85dddec663ecaf7966f49fb5`
- implementation commits: `82f0406936968ff1c29e11e43a7f7eb67ddf63cf`
  and `f5f65ce74a64000611c5733aeb51ed3184d4a811`
- canonical FacMan dev remains `54b188c0b2d4ab62c1d948cd1c548489fbe8c8b7`
- canonical ULK pin remains `1cafe4054297cc11e02458b83d230db0cd064471`
- observed ULK dev candidate remains `e6de83ad1e1a2c646d31eb2ca68aa5cddb323b4a`
- Universal Setup pin remains `32488fc13bd2439f9f6e52e83a97f6da345a7650`

No provider pin, protected branch, execution authority, Setup mutation,
credential path, signing, publication, tag, or release changed.

## Implemented cut

The required `facman` binary now contains two TUI planes:

```text
facman tui             ordinary task shell when interactive
facman tui --ordinary  explicitly testable linear ordinary shell
facman tui --advanced  exhaustive generated command browser
```

`--interactive` remains a backward-compatible Advanced alias. Home,
Instances, Installations, Content, Saves, Activity, Settings, and Advanced are
always addressable. A persistent Launch Deck projects selected instance,
version, profile/content/save summary, readiness, contextual action, active
operation, and authoritative Last Run availability.

The product state path is:

```text
facman.presentation_snapshot.v1
  -> TuiSnapshot
  -> TuiState + pure event reducer
  -> TuiRenderModel
  -> full-screen or linear renderer
```

Only `tui_product_shell.cpp` calls `CommandClient`/`FrontendSession`.
Renderers contain no backend, revision, readiness, action, refusal, recovery,
or Last Run policy. Installation scan uses the typed `presentation.action`
contract and an expected revision plus idempotency key. Unavailable Play is
shown as a backend refusal and is never promoted by a terminal flag.

The dependency-free full-screen adapter uses the alternate screen only after
capability admission. Redirected streams, `TERM=dumb`, `NO_COLOR`, safe mode,
and explicit plain mode use the escape-free linear transcript. FTXUI and every
other third-party renderer remain unpinned and unrequired.

## Local evidence

- MSVC 19.51 / Windows SDK 10.0.26100 warnings-as-errors build: pass.
- existing native TUI smoke: pass.
- terminal capability smoke: pass.
- new reducer/snapshot/form/render-model smoke: pass.
- Python TUI product suite: 4/4 pass, including ordinary eight-page routing,
  Launch Deck, NO_COLOR, redirected EOF, direct/process presentation parity,
  and Advanced handoff.
- POSIX PTY full-screen/help/resize/clean-exit test is present and intentionally
  skipped on the local Windows host; hosted POSIX observation remains pending.
- deterministic ConPTY capability selection is covered by the native terminal
  smoke; a live hosted ConPTY receipt remains pending.
- legacy generated guided forms and direct/process/daemon refusal behavior:
  unchanged and passing.
- warnings-as-errors shared-provider build and CTest: 43/43 pass.
- promotion obligation profile: 1,010 tests pass with zero failures, errors,
  expected failures, unexpected successes, required-blocked skips, or unknown
  skips; the gate reports `gate_passed = true`.
- WinForms shared-provider build and Windows package/runtime proof: pass.
- the eight classified skips are five unsupported Windows symlink-privilege
  cases, two optional cases, and the POSIX-only PTY case; none is required.
- no test created a workspace or ran Factorio.

Portable AIDE task inspection was report-only and returned
`blocked_missing_task_surfaces`, as expected because the managed Lite Pack does
not copy source `.aide/queue/` state into the target repository.

## Remaining acceptance

This is not yet a complete parity or release claim. Before WorkUnit closeout:

- pass exact-head hosted Windows, Linux, and macOS builds and tests;
- add/retain PTY and ConPTY interaction evidence for resize, F1, arrows,
  Ctrl+P, Ctrl+R, cancellation, search, suspend/resume, EOF, and terminal close;
- close complete required ordinary journey cells so none depend on Advanced;
- adopt promoted ULK and prove Last Run/unknown/recovery behavior;
- pass direct/process/CLI/TUI semantic equality and transport-fault suites;
- prove packaged `facman` alone supplies CLI JSON, human CLI, and TUI;
- complete keyboard, focus, screen-reader transcript, Unicode-width,
  long-label, and performance receipts.

Real Factorio, private archives, managed installation, service/daemon work,
plugins, Qt, online services, signing, and publication remain outside scope.
