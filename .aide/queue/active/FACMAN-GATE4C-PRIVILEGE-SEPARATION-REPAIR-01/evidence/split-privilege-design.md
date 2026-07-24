# Gate 4C verdict-only split-privilege design

Recorded: 2026-07-24

## Scope

This design repairs the evidence-only Gate 4C harness. It does not create a
public Play route or the later player-facing Windows observation broker.

## Process boundary

```text
normal operator terminal
  -> Gate 4C coordinator at medium integrity
       -> Factorio at medium integrity through the existing launch provider
       -> one UAC request
            -> same reviewed harness in observer-broker mode at high integrity
                 -> exact reviewed Python observer backend
                 -> WPR start, status, finish, or fail-closed abort only
```

The broker cannot construct a process request for Factorio, Setup, a credential
provider, a network client, or a caller-selected executable.

## Local channel

The coordinator owns one first-instance, remote-client-rejecting Windows named
pipe with a protected DACL granting access only to the exact interactive user
SID. The pipe name contains a platform-CSPRNG nonce and is valid for one broker
process.

After connection the coordinator verifies:

- named-pipe client PID equals the process returned by `ShellExecuteExW`;
- broker image equals the running reviewed harness;
- broker token user SID equals the coordinator token user SID;
- broker Windows session equals the coordinator session;
- broker integrity is high;
- broker process remains alive.

The broker independently verifies:

- named-pipe server PID equals the claimed coordinator PID;
- coordinator image equals the running reviewed harness;
- coordinator token user SID equals the broker token user SID;
- coordinator Windows session equals the broker session;
- coordinator integrity is medium;
- the session descriptor and all bound artifacts still validate.

This is an OS-authenticated local channel. No reusable bearer secret is placed
on a command line, in a workspace file, or in evidence.

## Closed request

The initial observer request binds exactly:

```text
protocol version
command = observer_start
coordinator PID
operation ID
session digest
preflight digest
frozen policy digest
launch-plan digest
observer provider revision
resource-binding digest
one CSPRNG nonce
not-before and expiry
```

The broker recomputes or reloads every bound value from stable no-follow
artifacts. It refuses unknown or duplicate fields, wildcards, another command,
another provider, another policy, another session, another plan, another
principal, expiry, and replay.

The finish request additionally binds the exact Factorio process ID, stable
process-start identity, executable, and capture-session digest. The abort
request may only close the already-started exact capture.

Responses echo the request digest and nonce and contain only structured
observer state and evidence identities. The coordinator accepts responses only
from the already authenticated pipe peer.

## Lifetime and failure law

- The broker is launched only after exact plan review.
- WPR becomes active before permit issuance or process creation.
- Permit issuance remains in the medium coordinator.
- Permit consumption remains immediately before Factorio process creation.
- The broker survives only for the exact observation session.
- Normal completion stops WPR, hash-closes observation output, and exits.
- Coordinator cancellation or launch refusal requests fail-closed abort.
- Pipe loss, broker death, timeout, WPR loss, identity drift, or an incomplete
  response makes the candidate result unavailable or Inconclusive.
- No failed attempt may silently leave WPR active.

## Integrity evidence

The repair proves without launching Factorio:

```text
coordinator integrity = medium
broker integrity      = high
interactive user SID  = exact and equal
Windows session       = exact and equal
binary identity       = exact and equal
```

The fresh Gate 4C verdict must additionally bind the observed Factorio token
integrity as medium. The verdict cannot reuse attempt-02 evidence.

## Deferred product work

Signing, installed-helper lifecycle, polished UAC UX, durable broker version
negotiation, and a generally available player workflow belong to the later
`FACMAN-WINDOWS-OBSERVATION-BROKER-01` WorkUnit after a Gate 4C Pass.
