# Presentation fake-session journey checkpoint

Status: active bounded implementation. This slice connects the callable
presentation service to the already qualified fake-process/ULK bridge without
enabling production Play or claiming the complete Windows journey.

## Boundary

- WorkUnit: `FACMAN-WINDOWS-EXISTING-INSTALL-JOURNEY-01`
- task branch: `task/facman-presentation-fake-session-journey-01`
- stacked base: exact PR #151 head
  `9396055f4d7b7184d263fe833b46941207abc5e9`
- canonical FacMan base contained by the stack:
  `dev@e1177df9df7e3d391bd35d0d810247dccb1ac37c`
- canonical ULK provider pin:
  `09f0639ab6529fba2f2aa22e9bf68e5eebed0553`

The production `PresentationApplicationModule` constructs the service without
a launch executor. Real Play therefore remains unavailable. The only executor
used by this slice is a native-test fixture which invokes the existing
`foundation_test_process` service and the repository's fake process probe.
No environment variable, CLI option, package setting, or frontend flag can
install that executor.

## Effect and confirmation law

`presentation.action` carries dynamic backend-described effects. A process
action is no longer allowed to inherit the read-only transport behavior of
refresh, Doctor, or installation scanning.

An effectful action now requires all of the following:

1. the backend snapshot advertises the action as available;
2. a narrow product launch executor is present and admits the selected scope;
3. the action has an idempotency key and durable operation identity;
4. the application receives an explicit non-dry-run dispatch;
5. the frontend satisfies the descriptor's explicit confirmation contract.

The same-binary TUI treats confirmation as a single-use capability. The first
activation displays the exact action to confirm. The second activation clears
the confirmation before transport dispatch and sends the durable operation
identity. Selection changes, refresh, navigation, cancellation, and a new
snapshot all invalidate a pending confirmation. A transport loss therefore
cannot turn a later activation into an unreviewed retry.

Read-only semantic actions remain dry-run requests and preserve their existing
one-step behavior.

## Outcome and replay law

The semantic action result schema now represents all six ULK terminal
classifications:

```text
cancelled_before_dispatch
refused_before_effects
completed
cancellation_requested_but_completed
recovery_required
outcome_unknown
```

The TUI reads that typed semantic outcome instead of overwriting it with the
outer command-transport completion. Replacement snapshots are queried only
after the executor returns, so Last Run is projected from the authoritative
ULK journal.

In-process duplicate lookup now occurs before current-revision comparison. An
exact retry of a completed request returns the original result even when the
effect changed the current snapshot revision; reuse of the same key for
different input remains a conflict. Durable cross-process action-receipt
replay is still an explicit remaining acceptance item and is not claimed by
this slice.

## Current proof

- Visual Studio Release source-provider configuration: pass;
- presentation service native smoke: pass;
- same-binary TUI product-model smoke: pass;
- schema validation across all repository schemas: pass;
- focused presentation/semantic-spine Python tests: pass;
- fake process sessions: repository probe only;
- real Factorio executions: zero.

Exact-head full native, Python, provider/package, and hosted matrices remain
required before review.

## Remaining WorkUnit acceptance

The complete journey still needs ordinary backend actions for read-only
installation registration and instance creation/selection, a production-path
fixture composition usable through process RPC without exposing real Play,
WinForms consumption of the common snapshot/action service, durable
cross-process duplicate receipts, relaunch/recovery faults, frontend-close
proof, and packaged CLI JSON/TUI/WinForms semantic equality.

