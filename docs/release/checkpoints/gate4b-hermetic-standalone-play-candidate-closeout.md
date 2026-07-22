# Gate 4B hermetic standalone Play candidate closeout

## Disposition

Gate 4B is accepted on reviewed `dev` as the exact technical candidate for the
frozen Gate 4A policy. PR #52 merged reviewed head
`da3e2274a3dc8a5757078b20276a1a6a93084860` at `dev` revision
`e9c1e69fee1ae815f62638db8b7263cb01b70389`.

Its sole disposition is:

```text
eligible_for_human_verdict
```

No human verdict, public Play route, product issuance, or real Factorio
execution is claimed.

## Accepted technical boundary

The implementation binds and revalidates:

- the exact frozen policy digest;
- Windows x64, Factorio 2.0.77, standalone non-Steam, `menu`, and `hermetic`;
- authenticated candidate-scoped source and executable evidence;
- InstanceSpec, InstanceBinding, InstanceReadiness, installation, executable,
  effective configuration, empty mod-lock, environment, and launch-plan
  identities;
- 31 evidence bindings and a strict eight-root runtime writable subset;
- one exact candidate-only, short-lived process-session permit;
- independent provider re-observation and atomic consumption immediately
  before the injected process boundary;
- observer-before-process ordering, explicit gap/incompleteness semantics, and
  stable no-follow protected-root comparisons; and
- a canonical hash-closed technical packet whose human fields are unset.

Process output remains separate from lifecycle state. Stable lifecycle reads
verify self-hash and no-follow identities. Full permit secrets and reusable
envelopes are absent from evidence packets.

## Exact proof

The final head passed push and pull-request CI, CodeQL for every configured
language, schema, and security-policy workflows. Linux GCC, macOS AppleClang,
Windows MSVC, sanitizers, fuzzing, coverage, native packages, reproducibility,
WinForms, AppKit, TUI, strict, and Python proof all passed.

The exact merge revision passed CI run `29910544402`, code-security run
`29910544923`, schema run `29910545091`, and security-policy run
`29910544435`.

A clean detached, no-hardlink reconstruction pinned FacMan at the reviewed
head, Universal Launcher at `7bd4425f0c35414f738159b45d8bec42edf70235`,
and Universal Setup at `3f8489275077347c2918f3bb03614ec6431362ff`.
All three repositories configured, built, tested, and passed strict checks;
FacMan additionally passed AIDE Lite and the full Python suite. The matrix
completed in 548.3 seconds.

## Authority boundary

This checkpoint does not promote:

- `facman play`, `instance.play`, or a general process route;
- product permit issuance or a reusable permit;
- a real Factorio run or human `Pass`, `Fail`, or `Inconclusive` result;
- installation preparation, Universal Setup mutation, credentials, networking,
  Steam, alternate launch intents, host repair, signing, or publication;
- playability, Safe beta, or canonical `main`.

## Next transition

`FACMAN-HERMETIC-STANDALONE-PLAY-VERDICT-01` is now the active, deliberately
human-reviewed WorkUnit. It must pin the exact policy, candidate, provider,
instance, executable, plan, and observer revisions and run the frozen menu
journey. A candidate defect opens a separate repair task; the verdict task may
not edit runtime code or weaken policy.

Even a human-reviewed Pass is evidence only. Enabling the exact proven route
requires a later, separately reviewed
`FACMAN-HERMETIC-STANDALONE-PLAY-ROUTE-PROMOTION-01` decision.
