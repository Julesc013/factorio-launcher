# Same-binary TUI parity checkpoint

Status: active implementation slice; the original stacked head passed local and
hosted qualification, and the branch is now forward-integrated onto the exact
qualified canonical `dev`. Post-restack exact-head proof and human review remain
required and are recorded on PR #144 rather than predicted by this tracked file.

## Identity and boundaries

- WorkUnit: `FACMAN-SAME-BINARY-TUI-PARITY-01`
- branch: `task/facman-same-binary-tui-parity-01`
- original stacked base: terminal foundation `de3ca04b774027df85dddec663ecaf7966f49fb5`
- current base: canonical FacMan `dev@d4171a9beca18a63692819c7b7eedbaaae48d04a`
- normal forward-integration merge: `ca1b6a2027bc6f66a4354932ca89af0a525b1aeb`
- implementation commits: `82f0406936968ff1c29e11e43a7f7eb67ddf63cf`
  and `f5f65ce74a64000611c5733aeb51ed3184d4a811`
- terminal-foundation PR #141 merged as `318a1151209897e13652d07a5d9145f9b9f13c00`
- provider-main reachability repair PR #145 merged as canonical FacMan
  `dev@d4171a9beca18a63692819c7b7eedbaaae48d04a`
- canonical ULK pin remains `1cafe4054297cc11e02458b83d230db0cd064471`
- ULK session subset is promoted on canonical
  `main@09f0639ab6529fba2f2aa22e9bf68e5eebed0553` and synchronized into
  `dev@2e77e15c8bcdeb833a0a45aab3421886b72cc70c`
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
- POSIX PTY full-screen/help/resize/clean-exit test is intentionally skipped on
  the local Windows host and passed at exact original head `805da69f...` in
  hosted Linux and macOS native CI.
- deterministic ConPTY capability selection is covered by the native terminal
  smoke; a live hosted ConPTY receipt remains pending.
- legacy generated guided forms and direct/process/daemon refusal behavior:
  unchanged and passing.
- warnings-as-errors shared-provider build and CTest: 43/43 pass.
- post-restack promotion obligation profile: 1,013 tests pass with zero failures, errors,
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

- pass the new post-restack exact-head Windows, Linux, and macOS matrix (the
  original stacked `805da69f...` head passed all 33 returned checks; that
  receipt is not reused for the new head);
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
