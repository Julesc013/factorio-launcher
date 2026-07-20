# PR #34 Gate 0 dev integration

## Disposition

Gate 0 is accepted as a reviewed, reproducible `dev` integration. PR #34 merged
the exact reviewed head
`61a7afe6718d3ca36b2c530b83890fcd37cc5c03` into `dev` at
`62c2503110cdb89b9cc89f19a69903f214d33e3c`.

This checkpoint promotes the task-branch contract and schema counts to current
integrated development-state truth. It does not promote a release, Safe beta,
playability, process authority, installation mutation, networking, credentials,
host mutation, canonical `main`, signing, or publication.

## Review evidence

The five named review slices are recorded in
[`PR #34 Gate 0 slice review`](../../quality/pr-34-gate-0-slice-review.md):

| Slice | Result |
| --- | --- |
| Execution and authority | Pass with documented notes |
| Installation model | Pass with documented notes |
| Contracts and generated surfaces | Pass |
| Product architecture | Pass with documented notes |
| Governance and evidence | Pass with documented notes |

No P0 finding remained at the reviewed head. Setup dispatch passes through the
global admission seam while retaining provider-side policy enforcement.

## Exact-head validation

| Evidence | Result |
| --- | --- |
| PR CI run `29758642385` | Pass |
| PR code-security run `29758642411` | Pass |
| PR schema-check run `29758642428` | Pass |
| PR security-policy run `29758642557` | Pass |
| Clean three-repository reproduction | Pass |

The clean reproduction pinned Universal Launcher at
`7bd4425f0c35414f738159b45d8bec42edf70235` and Universal Setup at
`3f8489275077347c2918f3bb03614ec6431362ff`. It configured, built, and tested
both providers, then configured, built, ran CTest, AIDE Lite, strict policy, and
the Python suite for FacMan. Its isolated temporary root was removed.

## Exact merged-dev validation

| Evidence | Result |
| --- | --- |
| `dev` CI run `29760235796` | Pass |
| `dev` code-security run `29760235888` | Pass |
| `dev` schema-check run `29760236038` | Pass |
| `dev` security-policy run `29760236168` | Pass |
| Clean three-repository reproduction at `62c2503` | Pass |

The merged-dev reproduction used the same locked provider revisions and the
same full validation matrix. Its isolated temporary root was removed.

## Continuing boundary

The active installation WorkUnit remains open only for a bounded read-only
model-v2 and deterministic plan-only closeout. General installation apply and
the broader repair/move/update/uninstall lifecycle remain deferred to later
permit-backed work. The next player-facing sequence remains WorldSpec and
readiness, OperationPermit, one hermetic standalone Play proof, and the
world-centric alpha.
