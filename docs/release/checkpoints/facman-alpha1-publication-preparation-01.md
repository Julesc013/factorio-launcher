# FacMan alpha.1 publication preparation 01

Date: 2026-08-30
WorkUnit: `FACMAN-0.1.0-ALPHA.1-PUBLICATION-PREPARATION-01`
State: prepared, non-authorizing, pending reviewed protected-`dev` integration

## Outcome

This WorkUnit prepares the release-control machinery needed after the sealed
`v0.1.0-alpha.1` tag. It does not publish a release, activate an environment,
create a permit, run Factorio, sign an artifact, or record a human verdict.

The product and control planes are now explicit and separate:

- frozen product commit `fa60aaa17e9044bef7bb7347261056959690f1cd`, tree
  `5536891662461d3617ee40e93654cb2f0659905c`, immutable tag object
  `52a7a66092ff2b3b3c1059e9c29260f95b1cb287`;
- release-control checkout: an exact current protected-`dev` commit containing
  the reviewed public-alpha gate and workflow.

## Prepared gates

Public asset assembly requires both evidence classes that are absent today:

1. G2: `facman.alpha1_portable_human_test_receipt.v1` must be
   `human_execution_complete`, name an assigned tester, record a timestamp,
   contain exactly nine Pass lanes, bind all three exact package archives and
   the frozen qualification, retain no unresolved findings, and grant no
   authority.
2. G3: the route receipt must be the exact
   `facman.successor-play.human-verdict.05` Pass for the frozen WinForms route
   package. Publication also requires route v5 to be the current integrated
   route with capability and promotion explicitly integrated.

The publication receipt is invocation-scoped. It binds both source revisions
and trees, the G2 and G3 receipt hashes, the route-index digest, the route
package hash, and an explicit unsupported, unsigned prerelease policy. It may
authorize only publication: tag creation, signing, support promotion, and route
promotion remain false.

## Current truthful blockers

- G1 is complete: the annotated tag and sixteen tag-only assets are sealed and
  verified, and no GitHub release exists.
- G2 is pending: the current exact packet hash is
  `7f64271c91cfb0417cd205b5f22bfe79d66d746a60eef5ded33a627453950928`,
  all nine lanes are Inconclusive, and the tester is `UNASSIGNED`.
- G3 is pending: the exact D3/D4 request is integrated, but D3 and D4 are not
  authorized, no permit or route receipt exists, and route capability and
  promotion remain false.
- No publication-authority receipt exists. Production signing, publisher
  authenticity, support, beta, RC, stable, main promotion, and publication all
  remain unauthorized.

The dormant signing-preparation contract is deliberately non-operational. It
permits only a future disposable, non-release fixture rehearsal; the frozen
alpha.1 packages cannot be signed retroactively. A later reviewed WorkUnit must
assign the signing identity, certificate, timestamp authority, rehearsal
receipt, exact candidate, protected environment, and invocation-scoped owner
authority. SHA-256 Authenticode, RFC 3161 timestamping, before/after digests,
and verification of every shipped Windows executable are mandatory, while key
material in the repository or logs is forbidden. Every credential, identity,
environment, receipt, package-signing permission, and signing authority remains
absent here.

## Machine-checked evidence

- `release/index/alpha1_publication_preparation.v1.toml`
- `contracts/schema/release/alpha1_publication_preparation.v1.schema.json`
- `tools/alpha1_publication_preparation_check.py`
- `tools/alpha_release_source_check.py`
- `tools/alpha_asset_set.py`
- `tools/alpha_publication_gate.py`
- `.github/workflows/release.yml`

The prepared control record digest is
`5e6ceb433770d5ef17faaf20b5e7a45e9e1bccd02db87ccb665272b482f04685`.
The request and preparation artifacts themselves grant no release or runtime
authority.
