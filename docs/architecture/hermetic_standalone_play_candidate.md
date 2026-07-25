# Hermetic standalone Play candidate

Status: implemented technical candidate; synthetic execution proven locally;
real Factorio run, human verdict, product route, and authority promotion absent.

The Gate 4B candidate implements only the frozen
`facman.hermetic-standalone-play.2.0.77.windows-x64.v1` policy. The runtime
recomputes the canonical Gate 4A document and accepts only policy digest
`6fde31f26d57e23d67c01dd598cb869a4914d11711868b46d4f817709455e7a2`.
Changing a selector, scope, evidence requirement, observation rule, or verdict
rule makes the candidate unavailable.

## Candidate boundary

The candidate accepts exactly:

- Windows x64;
- Factorio 2.0.77;
- standalone, non-Steam application data;
- an executable SHA-256 bound to operator-reviewed Wube source evidence;
- a FacMan-owned instance on fixed local NTFS;
- base content and an explicit empty mod lock;
- `instance.play`, `menu`, and `hermetic`;
- no account, credential, network, Setup, or alternative launch intent.

`CandidatePermitIssuer::public_issuance_available()` and
`HermeticCandidateLaunchProvider::public_execution_available()` both remain
false. There is no command contract or registered route for Play or permit
issuance. Gate 4B can therefore exercise only injected synthetic process and
observation providers; it cannot launch Factorio through the product.

## Evidence and planning

`project_hermetic_candidate_plan` converts the accepted Gate 2 Instance model
into one exact candidate plan. It independently reopens and binds:

- the InstanceSpec, InstanceBinding, and InstanceReadiness digests;
- installation evidence and the installation-root stable identity;
- executable stable identity and SHA-256;
- effective configuration and explicit empty-lock identities;
- read-data, write-data, and mod-root identities;
- policy, machine, principal, provider, source, baseline, and build evidence;
- one menu launch command and a non-inherited five-variable environment.

The process environment routes `TEMP` and `TMP` beneath
`temporary/<operation-id>/process` and `USERPROFILE` beneath the selected
instance's `state/userprofile`. The serialized plan contains digests rather
than reusable machine paths.

The runtime permit scope is a strict subset of the 13 policy writable roots:

```text
instance.config
instance.locks
instance.logs
instance.mods
instance.saves
instance.state
operation.record
operation.temporary
```

Each selected writable root is a separate typed resource. Present directories
bind stable object, volume, filesystem, and no-follow identities. An absent
directory binds absence, the stable workspace identity, and its relative-name
digest. No workspace prefix or wildcard becomes authority.

`reobserve_hermetic_candidate_context` rebuilds the same projection for the
owning provider immediately before consumption. Executable, configuration,
installation, policy, baseline, provider, or writable-root drift changes the
validation context and refuses the permit before process creation.

## Process and permit boundary

The bounded issuer uses the Gate 3 process-session authenticator with platform
CSPRNG entropy. It can issue only one short-lived permit for:

```text
operation       instance.play
intent          menu
isolation       hermetic
audience        factorio.launch.local
effects         workspace_read, workspace_write, process_execute
capabilities    launch.execute.hermetic, process.execute
```

The owning provider performs fresh observation, validates the exact permit,
and atomically consumes its nonce immediately before calling the injected
process supervisor. Replay, stale evidence, wrong audience, wrong intent,
wrong isolation, expiry, and session restart fail before process creation.

Windows process identity combines the PID with the kernel creation time. Linux
uses the PID and `/proc/<pid>/stat` start identity. The frozen candidate remains
Windows-only; the cross-platform representation exists so shared lifecycle and
recovery code compiles and fails conservatively elsewhere.

## Independent observation

`BoundArtifactCandidateEffectObserver` is the Gate 4B integration boundary for
an independent process-tree capture provider. Its start callback must return a
stable capture-session digest before the effect boundary. Its finish callback
must return a no-follow artifact only after the supervised process has ended.
The runtime then checks:

- exact plan and capture-session digests;
- observer provider identity and revision;
- raw artifact and canonical output digests;
- primary-process start identity rather than PID alone;
- the closed filesystem, registry, process, and provider event vocabulary;
- the closed writable, protected, forbidden, external, and unresolved classes;
- every frozen gap signal.

Lost events, overflow, unknown process identity, unresolved targets, delayed
events, attribution gaps, provider failure, unstable reads, or malformed
artifacts produce incomplete evidence. A Gate 4C capture backend may use
Procmon, ETW, or another reviewed Windows provider, but its evidence is not
accepted merely because a path or JSON document exists.

Protected filesystem state uses bounded deterministic no-follow manifests.
Files are opened, hashed, and revalidated; directories are re-inspected before
and after traversal; links and reparses are recorded as gaps; limits and time
budgets fail closed. Registry snapshots and attributed-event capture remain
inputs from the independent Gate 4C observation provider and must cover the
frozen logical resource set.

## Evidence packet and persistence

The technical packet records the exact policy, plan, evidence, permit
consumption, restart-safe process identity, observation, protected comparison,
all 25 automated controls, and separated output digests. It can record only:

```text
refused_before_process
fail_evidence
inconclusive
eligible_for_human_verdict
```

`human_verdict` is fixed to `unset`; `grants_authority` and
`product_route_available` are fixed to false. The full permit envelope,
authenticator value, secret key, raw credentials, and process output are not in
the lifecycle packet.

Lifecycle data is staged under `temporary/<operation-id>/candidate-artifacts`
and committed without clobber to `operations/<operation-id>/lifecycle`.
Standard output and standard error are separate files under the operation's
`output` directory. Stable lifecycle reads reject links, size overflow,
authority-field changes, open object shapes, and any packet self-hash mismatch.

## Gate boundary

Gate 4B can close only as `eligible_for_human_verdict` after the complete local,
hosted, and clean-reproduction matrix. It does not produce `Pass`, `Fail`, or
`Inconclusive` as the human verdict.

Gate 4C must pin the reviewed candidate revision, provide the independent
Windows capture backend and exact source evidence, run Factorio interactively,
complete the frozen two-launch player journey, and obtain a human signature on
the hash-closed evidence packet. Even a Gate 4C Pass requires a later separate
route-promotion decision.
