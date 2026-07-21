# Gate 2 instance specification and readiness closeout

## Disposition

Gate 2 is accepted as a reviewed, deterministic, zero-write `dev` integration.
PR #39 merged the exact implementation head
`fa11b056c03784964e66ef391a81a6dfa8fcedc1` into `dev` at
`7113011a6c4fe1d76d4c09cc36bc8a3aafa34b36`. PR #40 then merged the bounded
clean-reproduction path correction
`f5915475eff78c255fe1f618a8be12c9c0f2d0f9` at final Gate 2 `dev` revision
`bbb46c5bfd10cd35fb965b23edc4951784f93ef4`.

This checkpoint closes `FACMAN-INSTANCE-SPEC-AND-READINESS-01` only. It opens
`FACMAN-OPERATION-PERMIT-01` as contract and validation infrastructure without
granting permit-issuance, preparation, process-execution, or real-Play
authority.

## Accepted product behavior

The additive `instances.describe` and `instances.readiness` routes project the
compatible `factorio.instance.v1` record into:

- a portable logical `InstanceSpec`;
- a machine-local, evidence-bound `InstanceBinding`;
- an evidence-derived `InstanceReadiness`; and
- a player-facing `InstanceView`.

The projections are deterministic under `facman.sorted-json.v1`. Their
component digests separate portable intent from machine-local evidence. The
default and only currently supported launch intent is `menu`; no save, server,
scenario, benchmark, or editor action is inferred. Other registered intents
receive a typed `unsupported_launch_intent` refusal.

Readiness explains installation, configuration, modset, instance-root,
environment, recovery, and launch-preflight dimensions. It never grants
authority. The existing `instances.inspect` route and persisted v1 record
remain compatible and unchanged.

## Zero-write and authority boundary

Repeated describe/readiness calls are proven not to create a missing workspace
or change workspace, installation, fixture, registry, journal, source, or
temporary operation state. The implementation contains no preparation,
transaction, process-launch, network, credential, Setup-apply, signing, or
publication primitive.

Every projection retains:

```text
mutation_executed = false
preparation_executed = false
execution_started = false
permit_issued = false
credential_accessed = false
network_accessed = false
preparation_available = false
execution_available = false
```

## Exact-head validation

| Evidence | Result |
| --- | --- |
| PR #39 CI `29812506939` | Pass |
| PR #39 code-security `29812506919` | Pass |
| PR #39 schema-check `29812506783` | Pass |
| PR #39 security-policy `29812507063` | Pass |
| PR #40 CI `29814299428` | Pass |
| PR #40 code-security `29814299449` | Pass |
| PR #40 security-policy `29814299432` | Pass |
| Canonical local full matrix | Pass |
| Portable AIDE Lite | Pass |

The canonical local matrix passed 44/44 native tests and 360 Python tests with
seven declared optional frontend skips. Strict validation passed with 261
schemas, 125 command contracts, 123 registered routes, and 217 refusal codes.
The final evidence-only closeout matrix passed the same 44 native tests and 361
Python tests after adding the reproduction-path regression test.

## Exact merged-dev validation

| Evidence | Result |
| --- | --- |
| Final `dev` CI `29815159526` | Pass |
| Final `dev` code-security `29815159602` | Pass |
| Final `dev` security-policy `29815159595` | Pass |
| Instance merge schema-check `29813605517` | Pass |
| Clean pinned three-repository reproduction | Pass |

The final correction changed only the path-relative CMake architecture scan
and its regression test, so the path-filtered schema workflow did not rerun at
`bbb46c5`. Schema validation remained part of the final exact-`dev` CI strict
matrix and the clean reconstruction. The Instance merge itself passed the
dedicated schema workflow at `7113011`.

The clean reconstruction pinned Universal Launcher at
`7bd4425f0c35414f738159b45d8bec42edf70235`, Universal Setup at
`3f8489275077347c2918f3bb03614ec6431362ff`, and FacMan at final exact `dev`
`bbb46c5bfd10cd35fb965b23edc4951784f93ef4`. All three source checkouts were
detached and clean before and after the 387.0-second matrix. Both providers and
FacMan configured, built, tested, and passed strict checks; FacMan also passed
AIDE Lite and the complete Python suite. The single temporary source/build root
was then removed.

The first isolated attempt exposed that the CMake architecture validator
mistook an ancestor directory named `build` for an in-repository generated
tree. PR #40 made that filter repository-relative and added a regression test.
The failed scratch root was removed before the final proof.

## Continuing boundary

The active WorkUnit is now `FACMAN-OPERATION-PERMIT-01`. It may define exact,
short-lived, plan/evidence/resource-bound permits and independent provider
revalidation, but `permit_issuance_authority` remains false until that bounded
infrastructure is reviewed and accepted.

Real Factorio execution, instance preparation, installation apply, credentials,
network access, host mutation, canonical `main`, signing, publication, and Safe
beta remain unpromoted. The next intended real-product programme freezes policy
in `FACMAN-HERMETIC-STANDALONE-PLAY-POLICY-01`, implements only that reviewed
candidate in `FACMAN-HERMETIC-STANDALONE-PLAY-CANDIDATE-01`, and records the
separate human result in `FACMAN-HERMETIC-STANDALONE-PLAY-VERDICT-01`, always
with explicit `menu` intent.
