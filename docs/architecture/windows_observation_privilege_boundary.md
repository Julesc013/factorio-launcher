# Windows observation privilege boundary

## Decision

FacMan's player process and Factorio must run with the interactive user's
normal medium-integrity token. Windows kernel ETW control is isolated in a
separate one-shot high-integrity observer.

```text
FacMan coordinator   medium integrity
Factorio             medium integrity
observer broker      high integrity
```

PowerShell is not part of this architecture. It is only historical Gate 4C
operator scaffolding.

## Why elevation exists

The frozen hermetic Play claim depends on process, filesystem, and Registry
events from a WPR kernel trace. Windows restricts control of that trace. The
game itself needs no administrative capability.

Running the complete launcher as Administrator is prohibited because ordinary
`CreateProcessW` creation uses the caller's security context. A monolithic
elevated launcher would therefore risk elevating Factorio.

## Gate 4C implementation

The evidence-only Gate 4C harness implements the narrow boundary needed to
repeat the frozen verdict:

1. The coordinator refuses to run unless its token is medium integrity.
2. It resolves and reviews the exact frozen menu plan.
3. It creates a one-user, first-instance, remote-client-rejecting named pipe.
4. It starts the same reviewed harness in hidden observer-broker mode through
   the Windows `runas` verb.
5. Both peers independently verify the other process's PID, executable path,
   user SID, Windows session, and integrity level.
6. The broker revalidates the frozen policy, session, plan, resources, provider
   revision, nonce, and expiry.
7. The broker starts WPR and returns `observer_ready`.
8. The normal coordinator retains plan admission and one-use permit
   consumption.
9. The Windows supervisor creates Factorio suspended, verifies its token is
   the exact medium-integrity interactive principal/session, and only then
   resumes its primary thread.
10. After Factorio exits, the broker stops WPR, closes the evidence, and exits.

The high-integrity process cannot launch Factorio, Setup, a network client, a
credential provider, or a caller-selected executable.

## IPC authentication

The local pipe is protected by a DACL for the exact interactive user SID. The
pipe rejects remote clients and allows one connection.

The coordinator binds the client PID to the process handle returned by
`ShellExecuteExW`. The broker binds the server PID to the claimed coordinator.
Both sides check:

- same reviewed harness image;
- same interactive user SID;
- same Windows session;
- coordinator is medium integrity;
- broker is high integrity.

Every bounded JSON request is closed, canonically digested, nonce-bound,
ordered, and single-use. The start request additionally binds:

- exact policy digest;
- exact session and preflight digests;
- exact launch-plan digest;
- exact observer-provider revision;
- exact resource-binding digest;
- not-before and expiry.

No secret or reusable permit is passed on the command line or persisted.

## Failure behavior

- UAC cancellation stops before WPR or Factorio.
- Broker refusal stops before WPR.
- WPR start failure stops before permit consumption or Factorio.
- A status failure triggers fail-closed WPR abort.
- Permit refusal or pre-resume token refusal triggers fail-closed WPR abort.
- Pipe loss or broker failure makes the result unavailable or Inconclusive.
- If automatic abort cannot be proven, an exact recovery-required artifact is
  written and the operator must check WPR from an elevated context.
- A protected-root or attributed external write remains Fail evidence.

## Product boundary

This Gate 4C implementation is not public Play authority. The later
`FACMAN-WINDOWS-OBSERVATION-BROKER-01` product WorkUnit may package and sign a
dedicated helper, improve the UAC experience, and remove terminal scaffolding
only after an exact Gate 4C Pass.

It must preserve the same least-privilege law and must not become:

- a persistent generic administrator service;
- an arbitrary command runner;
- a Setup broker;
- a credential or network broker;
- a way to bypass UAC.
