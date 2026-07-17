# M2-WU10 Automated Synthetic Acceptance Policy

Status: policy frozen; no technical acceptance result recorded.

## Decision

The deterministic M2 synthetic portable lifecycle is governed by machine
acceptance rather than a fabricated human verdict. A conforming result is
named `MachinePass`. Human review is not required for this non-executable lane,
but the policy revision itself remains an externally authorized governance
decision.

The versioned policy is
`contracts/policy/m2_synthetic_portable_acceptance_policy.v1.json`. This
checkpoint freezes its criteria and verifier before any new run is accepted.
The historical `m2wu10-20260715-01` run remains corroborating evidence only;
this policy revision does not record it, reuse it as the sole passing result,
close WU10, or promote setup authority.

## Separation of Duties

The Universal Setup `usk_live_acceptance` executable performs the synthetic
lifecycle. The FacMan Python verifier is a separate standard-library program
that reads retained bytes and derives its own facts. It does not import or call
the runner or Universal Setup implementation.

The result lane binds four identities:

```text
accepted policy revision P
Universal Setup runner revision I
fresh evidence run R
separate result commit V
```

The verifier and policy bytes used by V must match revision P. The runner
summary must bind P as its consumer revision and the exact Universal Setup
revision frozen by the policy. V is necessarily later than P and may not alter
the verifier or policy while recording the result.

The verifier first emits an `EvidencePass` in a
`factorio.m2_machine_acceptance_observation.v1` document. `EvidencePass` is not
the technical acceptance verdict. The later recorded
`factorio.m2_machine_acceptance_result.v1` may say `MachinePass` only after it
adds the observation hash and binds every frozen local and hosted exact-head
validation gate; no result document is part of this policy-only change.

## Independently Derived Evidence

The verifier derives the following directly:

- exact file and directory closure, byte count, and absence of links or
  reparse points;
- exact ZIP digest, three expected entries, per-entry bytes, and absence of
  executable extensions or executable-file signatures;
- exact retained product files and clean absence of the moved/current root and
  temporary foreign-content file;
- canonical packet JSON and packet digests;
- canonical audit events, recomputed event digests, and continuous links;
- canonical ownership manifests and recomputed manifest digests;
- installed-state identities and their ownership, provider, archive, and
  target-root bindings;
- transaction transition chains, recomputed journal digests, and contained
  target/staging/state/audit roots;
- install, repair, move, and uninstall snapshots derived from the retained
  closure and absent target;
- a fresh eleven-case interruption summary and fourteen retained journals;
- exact policy, runner, verifier, and consumer revision bindings; and
- the unchanged excluded-authority boundary.

Runner status text and automated finding labels are not acceptance authority.
The verifier checks their structural consistency, but `EvidencePass` is
derived from the retained filesystem, hashes, state, journals, ownership,
audit chain, and revision bindings. The final `MachinePass` additionally
requires strict, native, Python, package, reproducibility, Windows, Linux,
macOS, sanitizer, bounded-fuzzer, coverage, CodeQL, schema, security-policy,
and release-policy proof at the exact result head.

## Negative Controls

Required tests prove failure after summary, archive, packet, or audit mutation;
after adding a link/reparse point or unexpected file; after changing tree
counts; after recreating `moved-product` or removing `installed-product`; after
placing a target outside the acceptance root; after changing the provider
revision; and after attempting any excluded authority promotion.

These controls run from a generated independent fixture on Windows, Linux, and
macOS. They do not use the retained live root and do not create a repository
acceptance result.

## Authority Boundary

A later `MachinePass` may make local managed portable setup a candidate only
for newly created, explicitly selected, policy-approved targets. This policy
does not authorize or infer:

- licensed Factorio archive acceptance;
- mutation or adoption of an existing installation;
- Steam or Steam Cloud mutation;
- Factorio execution, `run.execute`, or H1;
- network, credential, registry, shortcut, elevation, or system-wide behavior;
- signing or publication.

Human authorization remains mandatory for those higher-risk or judgment-based
lanes. This checkpoint records no current `MachinePass` and no human `Pass`.
