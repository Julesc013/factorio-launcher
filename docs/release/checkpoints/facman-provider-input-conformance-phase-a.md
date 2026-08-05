# FacMan provider-input conformance phase A

Date: 2026-08-06

Status: implementation complete; hosted exact-head evidence pending

Parent WorkUnit: `THREE-REPO-SOURCE-VS-SDK-CONFORMANCE-01`

Parent result: `PENDING` / `partial`

## Disposition

Phase A establishes provider-input and runtime-closure conformance. It does not
close the parent WorkUnit and does not advance provider SDK consumption or pin
reconciliation.

```text
completed phase       provider_input_conformance
next required phase   semantic_equivalence
parent status         active
parent result         PENDING / partial
```

Operation-outcome equality, structured refusals, interrupted recovery,
release-resolution-root equality, and macOS provider conformance remain
pending and must be delivered from a fresh exact-`dev` branch after this
tranche is accepted and integrated.

## CI source-truth correction

General integration CI now distinguishes:

```text
checkout facts
  -> workspace-lock-bound integration coherence
  -> unpublished integration package and runtime proof

unchanged release source projection
  -> exact two-provider refusal negative control
```

The integration record binds the clean checkout, exact consumed provider pins,
compiled build identity, selected provider mode, target, linkage, toolchain,
and workspace-lock digest. It explicitly records:

```text
integration_coherent = true
release_eligible = false
provider_adoption = false
signing = false
publication = false
```

Integration packages embed this record and omit release-resolution metadata.
They are not release packages.

The release projector and `facman.source_observation.v1` validator are
unchanged. The negative control passes only for the exact ULK and USK commit
mismatch, no release observation, no package, byte-identical tracked locks,
and no authority promotion. It fails as stale after reconciliation.

## Local validation

```text
strict repository validation                         PASS
focused source-truth/package/CI/programme suite      PASS (59 tests)
generated project-state validation                   PASS
AIDE Lite portable validation                        PASS
workspace/provider/route lock diff                   empty
```

The pre-amendment full portable suite ran 833 tests and reported two errors
from a locally retained native build identity that predates the current source
commits. That known host/build-state limitation is not presented as a pass and
must be superseded by the required hosted exact-head runs.

## Authority ceiling

This phase grants no provider adoption, provider repin, Setup mutation,
Factorio execution, observer capture, permit, route, signing, publication,
support, or protected-ref authority. PR #124 remains a draft review candidate
until all required exact-head checks pass and the owner makes a separate merge
decision.
