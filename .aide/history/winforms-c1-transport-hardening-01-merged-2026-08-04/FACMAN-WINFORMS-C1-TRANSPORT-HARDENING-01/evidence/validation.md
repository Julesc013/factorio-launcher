# Validation evidence

## Pre-implementation

- Exact FacMan base: `bfac7ce41f19856522b5f9603320f444b8f45094`.
- `main...dev`: `0/0` before task-branch creation.
- AIDE `git policy`: pass.
- AIDE `git detect`: trunk with `dev` integration; task branch required.
- AIDE clean `git plan`: `ready_dry_run`.
- AIDE `task inspect`, `task noop-check`, and `task recover`: missing task
  surfaces demonstrated before activation.

## Red characterization

`python tools/winforms_transport_legacy_red_probe.py` compiled the exact
pre-hardening WinForms sources against .NET Framework 4.8 and demonstrated:

- absent result fields synthesized `ok`, `completed`, and fresh identities;
- exit-zero non-JSON output projected as success;
- missing response identities were substituted from request identities;
- malformed post-dispatch JSON became `refused_before_effects`;
- wrong schema, protocol, request, command, operation, and attempt identities
  were accepted;
- invalid UTF-8 replacement-decoded into apparent success; and
- a one-character limit accepted a two-byte UTF-8 value.

Disposition: expected red; the permanent Windows behavior harness replaces
this legacy-only probe after the repair.

## Green validation

### Transport behavior

- `python tools/winforms_transport_hardening_check.py`: pass, 38 executable
  Windows cases.
- Exact request boundaries: 1 MiB accepted; 1 MiB plus one refused before
  process start.
- Exact stdout boundaries: 16 MiB accepted; 16 MiB plus one is
  `outcome_unknown`.
- Exact stderr boundaries: 64 KiB accepted; 64 KiB plus one is
  `outcome_unknown`.
- Strict malformed, duplicate-member, trailing-data, invalid-UTF-8, missing,
  mismatched, type-confused, and contradictory response cases all fail closed.
- Pre-dispatch cancellation/start failure prove no effects. Post-dispatch
  cancellation, timeout, early exit, and output exhaustion preserve unknown
  effects and require `workspace.recovery.inspect`.
- Spawned descendants and a child retaining inherited pipes are terminated by
  the assigned kill-on-close Job Object.
- A complete terminal response winning the cancellation race is retained as
  `cancellation_requested_but_completed`.

### Builds and repository gates

- WinForms .NET Framework 4.8 Debug x64 warnings-as-errors: pass.
- WinForms .NET Framework 4.8 Release x64 warnings-as-errors: pass.
- Canonical MSVC 19.51 native Debug build and CTest: pass, 58/58.
- Canonical MSVC 19.51 native Release build and CTest: pass, 58/58.
- `python tools/test_obligations.py --profile promotion`: pass, 668 tests,
  three classified skips, zero required/unknown skips, zero failures/errors.
- Classified skips: two unsupported symlink-creation cases and one optional
  bounded full-scale performance corpus.
- The machine-readable classified result is retained in
  `python-test-obligations.v1.json`.
- `python tools/strict_check.py`: pass with both exact sibling provider pins
  readable.
- AIDE queue, compaction, target-truth, plan-view, source-format, security,
  code-security, frontend-truth, GUI-surface, and diff checks: pass.

### Package and presentation

- Deterministic C1 presentation and runtime smoke: pass for all five states,
  pages, refusal, Last Run, recovery, accessibility anchors, and x64 DPI shell.
- Unsigned `windows_legacy_winforms_x64` reconstruction: pass.
- Package runtime smoke: pass from arbitrary working directory and without
  `PATH`; 398 files verified with SHA-256-consistent integrity.
- The package remains `not_proven_unsigned` and unpublished.

### Machine qualification note

This host has a persistent compatibility flag requiring elevation for
`C:\Windows\System32\cmd.exe`. Canonical MSVC qualification used only the
process-local `__COMPAT_LAYER=RunAsInvoker` override. No registry, machine
policy, provider checkout, or product authority state was changed.

The first fallback GCC warnings-as-errors build also exposed an unused
Linux/macOS-only discovery-smoke helper on Windows. Its compilation was scoped
to the platforms that call it before canonical MSVC qualification.

### Provider and authority reconciliation

- ULK pin before/after:
  `7fc25340623131ba86c08dca4fb8a43b18a4520d`.
- USK pin before/after:
  `3048128963dc718a7c38c1cfcdda9e813a23b0db`.
- Revalidation-04 remains superseded immutable history.
- No successor stage, observer, prepare, permit, execution, verdict, route,
  Setup mutation, credentials, network, signing, or publication was enabled.

## Merged-dev closeout

- Pull request: `#119`.
- Merge revision: `7ebbfa37b23ee173cbb15f399935d0e035e79375`.
- First parent: `bfac7ce41f19856522b5f9603320f444b8f45094`.
- Second parent and exact task head:
  `a90720ca994352f8a327399be718ab2feca91256`.
- `git merge-base --is-ancestor a90720c 7ebbfa3`: pass; the complete task
  head is contained by the merge.
- Local `dev` and `origin/dev` both resolved to the exact merge revision at
  closeout inspection.
- The only local worktree was the clean `dev` worktree at the merge revision;
  no contained task worktree or local transport-hardening branch remained to
  remove. The published remote task ref is not deleted by this local closeout.
- ULK and USK consumer pins remain, respectively,
  `7fc25340623131ba86c08dca4fb8a43b18a4520d` and
  `3048128963dc718a7c38c1cfcdda9e813a23b0db`.
- Closeout grants no provider repin, product execution, Setup mutation,
  successor route, signing, publication, credential, or network authority.
