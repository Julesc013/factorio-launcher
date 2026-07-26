# Instance-isolated verdict harness

Status: implemented operator-only evidence path pending exact remote-only
post-harness qualification; no Factorio execution, verdict, or product
authority.

The harness extends the historical Gate 4C evidence machinery without
rewriting its frozen Verdict 03 meaning. Route choice is closed over two
immutable bindings:

```text
gate4c-hermetic-verdict03
windows-instance-isolated-revalidation
```

An unknown route or WorkUnit refuses before baseline capture, permit issuance,
or process creation.

## Identity chain

The instance-isolated route never hard-codes the current candidate artifact
hashes into source. It consumes one immutable
`facman.play_candidate_qualification_binding.v1` record produced by a separate
remote-only reconstruction:

```text
three published source revisions and required remote refs
                        ↓
four exact candidate artifacts, sizes, and SHA-256 digests
                        ↓
authenticated Factorio 2.0.77 executable identity
                        ↓
InstanceSpec, InstanceBinding, and readiness digests
                        ↓
qualification_digest
```

The four candidate artifacts are the CLI, candidate smoke, verdict harness,
and CMake cache. Every key is closed, revisions and digests use exact lowercase
forms, artifact paths must be relative and traversal-free, and the entire
record is hash-bound with `facman.sorted-json.v1`.

Preflight independently requires each checkout to:

- equal its exact qualified revision;
- be clean;
- contain the required ancestors;
- be reachable from the qualified canonical remote ref.

Staged files must match the qualified size and digest after a no-follow copy.
The configured harness must itself be the qualified harness artifact.

## Execution boundary

Python tooling stages and prepares evidence but cannot issue a permit or start
Factorio. Native `facman_gate4c_verdict_harness --run-session` remains the only
candidate execution boundary. It:

1. accepts only a route-bound, hash-closed session;
2. independently verifies the route's frozen policy;
3. projects the route-specific candidate plan;
4. displays the exact menu plan and requires an explicit digest-bearing
   confirmation;
5. issues one 30-second, one-use permit;
6. reobserves the candidate immediately before execution;
7. starts the high-integrity observer before the medium-integrity process;
8. derives a technical packet with human verdict unset and authority false.

The normal product does not install this harness or any Python operator tool.

## Instance-isolated evidence law

The route binds exactly seven writable resources and twelve protected
resources from the frozen policy. File and Registry effects are eligible only
when target, completion, object lifetime, process attribution, principal, and
owner are resolved.

The observer records separate principal facts:

- the SHA-256 digest of the Windows SID proves the exact BAM selector;
- the plan principal-identity digest binds the observation to the reviewed
  candidate plan.

The primary process is owned by `operation.temporary`; Instance writes are
owned by `instance.closure`; the remaining operation writes require an exact
operation resource and artifact owner. One exact BAM `RegSetValue` family may
be classified as `expected_external_disclosed`. It is never a permit resource
or portable Instance state.

Missing completion, unresolved target, object/KCB reuse ambiguity, event loss,
packet collision, provider failure, or incomplete baseline/postrun comparison
is Inconclusive. Protected or unexpected external mutation is Fail.

## Human and promotion boundary

Two fresh launches are required. A person must establish every frozen journey
check; technical `eligible_for_human_verdict` is not Pass. Finalization derives
exactly Pass, Fail, or Inconclusive and cannot promote a route.

The required sequence remains:

```text
merge reviewed harness
→ rebuild from empty remote clones
→ publish exact qualification binding
→ fresh observer self-test and host attestation
→ human-controlled two-launch revalidation
→ separate exact-route promotion only after Pass
```

Historical Verdict 01, 02, or 03 baselines, packets, permits, traces, or human
observations cannot satisfy the new route.
