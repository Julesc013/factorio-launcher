# Execution foundation

The execution foundation supplies the smallest architecture needed by Play
without granting real Factorio execution authority.

## Startup configuration

`ApplicationConfiguration` is an immutable process-lifetime snapshot. The
application reads setup environment values and user preferences once when the
FLB application context is created. Setup calls receive that snapshot; a
command cannot change provider policy by mutating the environment mid-flight.
The default/global Factorio roots derived from `APPDATA`, `LOCALAPPDATA`,
`HOME`, and `USERPROFILE` are captured in the same snapshot. Authority-bearing
launch preflight consumes only those immutable roots and never re-reads the
process environment.
Process, network, credential, signing, and publication authority cannot be
enabled through environment variables.

## Admission and routing

Every typed application request is classified by effects and durable
capabilities before a handler can produce an external effect. The extracted
`LaunchApplicationModule` owns preview, preflight, Play, and the compatibility
run route. The existing central switch remains the fallback for untouched
domains. This is the first bounded command-module seam, not a general plugin
framework.

`facman play <instance>` and `facman run <instance> --execute` both route to
`run.execute`. The command truthfully declares workspace read/write and process
execution because a successful future run will write its lock, journal, and
post-run state. Its real-product availability remains fail-closed.

Launch references are also fail-closed. Only the exact `active` lifecycle with
a current `pass` verification status, nonempty verification identity, nonempty
state revision, and a fresh Universal Launcher graph can remain eligible.
Missing, unknown, unsupported, failed, recovery-required, retired, uninstalled,
stale, or malformed evidence produces a typed refusal; no handler manufactures
`active`, `unknown`, or `unobserved` evidence. Effective configuration is read
through a stable no-follow handle and revalidated before its paths influence
preflight.

## Process supervision

The product-neutral platform supervisor accepts an explicit executable and
argument vector and never invokes a shell. It controls the working directory,
environment, inherited standard handles, timeout, cancellation, output budgets,
process identity, and process-tree lifetime. Windows uses a kill-on-close Job
Object and an explicit inherited-handle list. POSIX uses a dedicated process
group, close-on-exec launch-status pipe, and bounded descriptor inheritance.

The existing CLI process transport now uses this same supervisor. Factorio's
launch layer consumes it through the narrow `ProcessSupervisor` port.

## Session journal

`LaunchExecutionService` revalidates the authorised instance and executable,
takes exclusive instance run ownership, and durably writes
`factorio.launch_session.v1` transitions:

```text
requested -> preflighted -> authorised -> starting -> running
running -> exited | cancelled | timed_out | crashed | killed
terminal -> complete | recovery_required
```

Interrupted journals are reconciled only after their recorded native process
identity is no longer live. Recovery never converts an interrupted session into
a successful run.

The Factorio-local journal is an execution diagnostic, not Last Run authority.
For an admitted fake journey, the caller may additionally provide an absolute
ULK session-journal root plus opaque session, operation, attempt, runnable, and
relaunch identities. `LaunchExecutionService` validates those values against
the installed experimental ULK ABI before dispatch, records `running` from the
supervisor's started callback, and commits one immutable terminal record only
after local journal and run-lock finalization.

The terminal mapping preserves the ULK operation law:

```text
no dispatch + cancellation       -> cancelled_before_dispatch
no dispatch + start refusal      -> refused_before_effects
observed terminal process        -> completed
cancel after dispatch            -> cancellation_requested_but_completed
uncertain post-dispatch result   -> outcome_unknown
journal/finalization uncertainty -> recovery_required
```

An exited process records its observed exit code, including a nonzero code.
Unknown or recovery-required outcomes carry the mandatory recovery inspection
reference. A running or terminal ULK write failure cancels further supervised
work where possible and leaves explicit recovery state; FacMan never creates a
frontend Last Run record as a substitute. The default Last Run provider reads
the ULK journal after process restart, so successful, nonzero, cancellation,
unknown, and recovery projections all come from the same durable authority.

Supplying no ULK root preserves the earlier local-only foundation behavior.
The optional seam is not a provider selector and cannot grant process
authority; only the already bounded `foundation_test_process` authority reaches
it in this programme.

## Presentation action binding

The callable presentation service owns a narrow optional launch-executor seam.
Executor presence is not authority: `launch.play` is available only when the
executor admits the current selected scope, and dispatch additionally requires
an explicit non-dry-run request plus idempotency and durable operation
identities. The production application module supplies no executor, so this
binding cannot make real Play reachable.

The fake-session conformance fixture uses the seam to call
`LaunchExecutionService`, then asks the presentation service for a replacement
snapshot. The resulting Last Run is therefore read back through the ULK
provider rather than copied from the executor result or manufactured by a
frontend. Semantic action results preserve ULK's six operation outcomes.

## Authority boundary

The only executable authority in this phase is
`foundation_test_process`, accepted by the internal execution service for the
portable fake process. Public application configuration cannot construct it,
and the global admission seam continues to refuse real Play. Steam-aware
instance isolation and hermetic standalone execution remain separate,
human-reviewed gates.
