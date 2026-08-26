# Alpha release factory

The manual `alpha-release` workflow separates machine qualification, route
acceptance, immutable tag creation, and publication. No invocation infers the
authority required by a later one.

## 1. Qualify machine assets

Dispatch `operation=qualify` with the exact accepted alpha source revision.
The Windows job uses `tools/alpha_qualification.py` to create three fresh
FacMan, ULK, and USK clones, builds all three through the stable-root wrapper,
and requires byte-identical canonical packages, intact native verification,
and deliberate drift refusal. It uploads:

- `facman-alpha-1-machine-assets`, containing the package, SBOM, provenance,
  licence inventory, limitations, candidate record, and prospective ledger;
- `facman-alpha-1-qualification-evidence`, containing the complete byte table
  and the bounded machine receipts.

Both artifacts are non-authorizing. They do not contain a route receipt,
checksums, a publication-authority receipt, or any private Factorio input.

## 2. Assemble the route-bound asset set

After separate route review, configure the exact passing JSON receipt as the
`FACMAN_ALPHA_1_ROUTE_RECEIPT_JSON` variable in the
`alpha-route-acceptance` environment. Dispatch `operation=assemble` with:

- the exact accepted alpha source revision;
- the qualification run ID;
- the separately reviewed SHA-256 of the normalized receipt JSON.

The read-only job downloads only `facman-alpha-1-machine-assets`, verifies the
receipt schema and its source, package, resolution, provider, journey, and
closed-authority bindings, then emits `facman-alpha-1-release-assets` with the
route receipt and deterministic checksums. It does not tag or publish.

## 3. Create an immutable unpublished alpha tag

Dispatch `operation=tag` only with an exact `facman.alpha_tag_eligibility.v1`
record and candidate from a retained workflow artifact. The reviewed
eligibility digest, current protected `dev` ref, required GitHub check runs,
effective protected-branch check rules, tracked product version, three
independent logical attestations, provider locks, release-significant reason,
candidate digest, and next never-used alpha number are all rechecked immediately
before the effect. If the next number differs from the version recorded on
`dev`, a normal reviewed version-bump WorkUnit must land before tagging.
The gate also requires an active, no-bypass GitHub tag ruleset matching
`refs/tags/v0.1.0-alpha.*` with both tag updates and deletion restricted. It
refuses to create the first tag until that independently administered control
is observable through the authenticated API.

The workflow creates one unsigned annotated `v0.1.0-alpha.N` tag and retains a
closed `facman.alpha_tag_receipt.v1` tag receipt. It does not create or edit a GitHub release, upload release assets,
sign anything, activate support, merge a branch, run Factorio, or invent a
human verdict. An existing tag or ledger number is never moved, deleted, or
reused.

## 4. Public prerelease publication remains inactive

The retained `operation=publish` path fails closed while the canonical alpha
channel has `publication_authorized = false`. A later reviewed governance
change must activate public prerelease publication before an invocation-scoped
publication receipt can be considered. The publication gate then recomputes
the complete inventory and every digest; tag authority alone never satisfies
that gate.

Do not reuse a qualification run ID as an eligibility or publication run ID.
Do not put a private Factorio archive, credentials, or unreviewed route
observations in any workflow artifact or environment variable.
