# Gate 4C attempt 02 privilege-boundary blocker

Recorded: 2026-07-24T10:24:58Z

## Disposition

```text
BLOCKED_BEFORE_BASELINE
```

No attempt-02 observer self-test, attestation, preflight, baseline, plan,
permit, capture token, Factorio process, or human verdict was created.

## Finding

The accepted Gate 4C harness currently performs both privileged observation
control and game-process creation inside one process:

1. `tools/gate4c_verdict_session.py` requires elevation to start and stop the
   frozen WPR kernel trace.
2. `tests/native/gate4c_verdict_harness.cpp` starts that helper as a child and
   then calls `HermeticCandidateLaunchProvider::consume_and_execute`.
3. `PlatformProcessSupervisor` reaches
   `runtime/platform/fl_process_supervisor_windows.cpp`.
4. The Windows supervisor calls `CreateProcessW` directly.
5. No filtered interactive-user token, `CreateProcessAsUserW`, privilege
   broker, or separate medium-integrity launch process exists on this route.

Microsoft documents that a process created with `CreateProcessW` runs in the
security context of the calling process. The current evidence procedure starts
the verdict harness from an elevated operator terminal so it can control WPR.
The candidate therefore cannot prove that Factorio remains at medium integrity.

## Required repair

The fresh verdict cannot resume until the implementation proves:

```text
FacMan coordinator    medium integrity
Factorio              medium integrity
observer helper       high integrity
interactive user      exact bound user/session
```

The elevated component must be one-shot and observer-only. It must not own
generic process execution, Factorio launch, Setup, credentials, networking, or
arbitrary command lines.

## Preserved boundaries

- Frozen policy digest remains
  `6fde31f26d57e23d67c01dd598cb869a4914d11711868b46d4f817709455e7a2`.
- Gate 4B candidate remains non-public.
- No human verdict is inferred.
- No authority is promoted.
- WPR is idle.
