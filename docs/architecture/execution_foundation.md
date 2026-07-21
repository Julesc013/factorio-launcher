# Execution foundation

The execution foundation supplies the smallest architecture needed by Play
without granting real Factorio execution authority.

## Startup configuration

`ApplicationConfiguration` is an immutable process-lifetime snapshot. The
application reads setup environment values and user preferences once when the
FLB application context is created. Setup calls receive that snapshot; a
command cannot change provider policy by mutating the environment mid-flight.
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

## Authority boundary

The only executable authority in this phase is
`foundation_test_process`, accepted by the internal execution service for the
portable fake process. Public application configuration cannot construct it,
and the global admission seam continues to refuse real Play. Steam-aware
instance isolation and hermetic standalone execution remain separate,
human-reviewed gates.
