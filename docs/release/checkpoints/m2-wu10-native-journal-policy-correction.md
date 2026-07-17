# M2-WU10 Native-Journal Verifier Policy Correction

Status: policy-only correction in progress; no technical acceptance result.

## Trigger

PR #26 independently merged the frozen synthetic acceptance policy into
`dev` at `7a3f812ab0f81fb35e2e6104bd573d8832a44e59`. The first result attempt then
created two fresh retained children under the authorized root:

```text
m2wu10-20260717-01
m2wu10-20260717-01-interruptions
```

The pinned Universal Setup runner revision
`3f8489275077347c2918f3bb03614ec6431362ff` completed both the lifecycle and
eleven-case interruption corpus. The verifier frozen at the accepted policy
revision refused to emit `EvidencePass`.

## Failure

All eighteen retained transaction journals are valid JSON in Universal
Setup's deterministic native field order. PR #26's generated verifier fixture
wrote the same objects with sorted keys. The verifier therefore added an
unsupported file-encoding requirement and rejected every native journal as
"not canonical JSON" before it could accept the run.

This is a verifier-contract failure, not a lifecycle `MachinePass`, and not
evidence of product mutation outside the authorized root. No observation file
was written and no acceptance result or authority was recorded.

## Bounded Correction

The correction permits native JSON field order for transaction journals only.
It does not trust journal status text. The verifier still independently
requires and recomputes:

- the journal schema and non-empty transition list;
- every transition sequence, predecessor, ID, and durability marker;
- the exact completed lifecycle for retained install, repair, move, and
  uninstall journals;
- current-state consistency for interruption journals;
- the journal digest from transition bytes;
- exactly four unique target, staging, setup-state, and audit roots; and
- containment of every declared root inside the selected fresh run.

Acceptance summaries, evidence packets, audit events, ownership manifests,
installed states, and interruption summaries retain their existing canonical
JSON requirements. All twelve negative controls remain unchanged.

The generated fixture now writes all eighteen journals in non-sorted native
field order and asserts that they differ from sorted-key canonical bytes before
deriving `EvidencePass`. The target-escape negative control continues to prove
that relaxing field order does not relax root containment.

## Separation and Next Run

This correction must merge independently and pass the complete local and
hosted matrix. Its merge revision becomes the new accepted verifier revision.
Only then may a different lifecycle run ID and interruption run ID be created.
The failed `20260717-01` pair remains diagnostic evidence and cannot be reused
as the sole passing result.

No `MachinePass`, human `Pass`, WU10 closeout, ordinary setup candidacy, real
Factorio authority, existing-installation authority, Steam authority,
execution, H1, network, credential, registry, elevation, signing, or
publication authority is recorded here.
