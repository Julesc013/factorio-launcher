# Gates 0-3 canonical public integration proof

Status: accepted canonical pre-Play baseline; `main` promoted and `dev`
synchronized; no authority promotion.

## Gate 3 closeout integration

PR #43 merged the atomic closeout commit
`ec4159f05678ad1ea55326ea881728354f5182c6` into `dev` at
`11feb2e53539e4b272f061374b2a07450c8e32bf`.

The exact closeout head passed:

| Gate | Run | Result |
| --- | --- | --- |
| CI | `29828529397` | Pass |
| Code security | `29828529368` | Pass |
| Security policy | `29828529380` | Pass |

The exact closeout `dev` merge passed:

| Gate | Run | Result |
| --- | --- | --- |
| CI | `29829439259` | Pass |
| Code security | `29829439147` | Pass |
| Security policy | `29829439134` | Pass |

The implementation schema proof remained revision-pinned separately; the
truth-only closeout introduced no schema change.

## Canonical promotion

The AIDE promotion helper reported `ready_dry_run` for the clean, reviewed
`dev` source. PR #44 then promoted exact source revision
`11feb2e53539e4b272f061374b2a07450c8e32bf` to canonical `main` at
`810e92ccd52ad89fada8a9bb5699805cb5580c24`.

The promotion head passed:

| Gate | Run | Result |
| --- | --- | --- |
| CI | `29830315611` | Pass |
| Code security | `29830315615` | Pass |
| Schema check | `29830315614` | Pass |
| Security policy | `29830315656` | Pass |

The exact canonical `main` merge passed:

| Gate | Run | Result |
| --- | --- | --- |
| CI | `29831299212` | Pass |
| Code security | `29831299101` | Pass |
| Schema check | `29831299292` | Pass |
| Security policy | `29831299545` | Pass |

The promoted source and canonical merge share tree identity
`1f15a9ff477db9f4713e82ce23aedea1914293d9`.

## Development ancestry synchronization

PR #45 reviewed the ancestry-only synchronization head
`ff57488e3cd5a04d6aab7a28f667be64ac54992a`. It contained no file changes,
made canonical `main` an ancestor, and retained the same tree identity.

The exact PR head passed:

| Gate | Run | Result |
| --- | --- | --- |
| CI | `29832438748` | Pass |
| Code security | `29832438688` | Pass |
| Security policy | `29832438665` | Pass |

The duplicate push-triggered runs `29832435868`, `29832436172`, and
`29832435890` also passed against the same synchronization head.

PR #45 merged to final synchronized `dev` revision
`08d4318ffd32bd9553ce8914cbd8bfc98fde7b74`. Its exact workflows passed:

| Gate | Run | Result |
| --- | --- | --- |
| CI | `29833442835` | Pass |
| Code security | `29833442940` | Pass |
| Security policy | `29833442807` | Pass |

At this checkpoint:

- canonical `main` is an ancestor of `dev`;
- `main` and synchronized `dev` share tree identity
  `1f15a9ff477db9f4713e82ce23aedea1914293d9`;
- local `main` and `dev` track their exact remote revisions;
- the promotion and synchronization branches are deleted after merge.

The post-promotion truth record additionally passed locally:

- canonical Visual Studio Debug configure and warnings-as-errors build;
- full native CTest, 47 of 47;
- full Python suite, 364 passed and 2 skipped;
- strict validation, AIDE Lite, project-state validation, and diff checking.

An initial Python invocation after deliberate build cleanup stopped at the
required package-runtime fixture because `build/native-smoke/Debug/facman.exe`
had already been removed. The canonical root was rebuilt, the complete suites
passed, and the temporary build root was removed again after validation. This
was validation-order evidence, not a product or source failure.

## Promoted product truth

Canonical `main` now accepts only the Gates 0-3 pre-Play baseline:

- integrated execution and installation foundations;
- read-only installation evidence and deterministic plan-only reconciliation;
- read-only portable instance specification, local binding, readiness, and
  view projections with `menu` as the only supported intent;
- authenticated, exact-resource, expiring, replay-resistant OperationPermit
  infrastructure with dormant independent-provider proof.

`FACMAN-HERMETIC-STANDALONE-PLAY-POLICY-01` remains active on `dev`. Policy,
candidate implementation, and human verdict remain three separate reviews.

## Authority boundary

This canonical promotion does not enable or claim:

- product permit issuance;
- real Factorio execution or a Play verdict;
- installation or instance preparation apply;
- Setup, credential, network, or host-mutation authority;
- signing, publication, Safe beta, or release authenticity.

Readiness and plans remain non-authoritative. The canonical baseline is a
stable architectural and contract checkpoint, not a playable release.
