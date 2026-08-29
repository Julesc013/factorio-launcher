# Alpha release factory

The manual `alpha-release` workflow separates machine qualification, immutable
tag creation, tag-only assembly, route-bound public assembly, and publication.
No invocation infers the authority required by a later one.

## 1. Qualify machine assets

Dispatch `operation=qualify` with the exact accepted alpha source revision.
The Windows job uses `tools/alpha_qualification.py` to create three fresh
FacMan, ULK, and USK clones, builds all three through the stable-root wrapper,
and requires byte-identical canonical packages, intact native verification,
and deliberate drift refusal. It uploads:

- `facman-alpha-1-machine-assets`, containing three packages, their three
  SBOMs, three provenance records, three licence inventories, limitations, and
  the candidate record;
- `facman-alpha-1-qualification-evidence`, containing the complete byte table
  and the bounded machine receipts.

Both artifacts are non-authorizing. They do not contain a tag receipt,
checksums, route receipt, publication-authority receipt, public ledger entry,
or any private Factorio input.

## 1a. Produce exact tag eligibility without changing product bytes

Dispatch `operation=eligibility` from the reviewed
`FACMAN-ALPHA-TAG-ELIGIBILITY-PRODUCER-01` control-plane commit while protected
`dev` still identifies the qualified alpha.1 product source. Supply the exact
qualification run ID and frozen product revision. The producer downloads the
retained candidate and three-root result, reobserves protected `dev`, required
checks, branch rules, immutable-tag rules, and provider main refs, then emits
`facman-alpha-tag-eligibility`.

The artifact contains `eligibility.v1.json`, the byte-identical
`candidate.v1.json`, and a non-authorizing producer receipt. The eligibility
binds the frozen product source. The producer receipt separately binds the
release/control-plane source and workflow run. Producing this artifact does not
create a tag or authorize publication, signing, support, route effects, or a
human verdict.

## 2. Create an immutable unpublished alpha tag

Dispatch `operation=tag` only with the exact separately reviewed eligibility
and candidate artifact described below. The tag workflow retains
`facman-alpha-tag-receipt`; it does not assemble or publish assets.

## 3. Assemble the tag-only asset set

After tag creation, dispatch `operation=assemble-tag` with the exact source,
qualification run, tag-receipt run, and reviewed tag-receipt digest. The job
combines only the 14 machine assets with the immutable tag receipt and generated
checksums. It emits the exact 16-file `facman-alpha-1-tag-assets` inventory and
grants no publication or support authority.

## 4. Assemble the pre-authority public asset set

After separate route review, configure the exact passing JSON receipt as the
`FACMAN_ALPHA_1_ROUTE_RECEIPT_JSON` variable in the
`alpha-route-acceptance` environment. Dispatch `operation=assemble-public`
with:

- the exact accepted alpha source revision;
- the exact `assemble-tag` run ID;
- the separately reviewed SHA-256 of the normalized receipt JSON.

The read-only job downloads only `facman-alpha-1-tag-assets`, verifies the
receipt schema and its source, designated WinForms package, resolution,
provider, journey, and closed-authority bindings, then emits the exact
pre-authority `facman-alpha-1-public-assets` set with the route receipt, public
ledger entry, and recomputed checksums. It does not tag or publish and cannot
invent the still-absent publication-authority receipt.

## Tag eligibility boundary

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

## 5. Public prerelease publication remains inactive

The retained `operation=publish` path fails closed while the canonical alpha
channel has `publication_authorized = false`. A later reviewed governance
change must activate public prerelease publication before an invocation-scoped
publication receipt can be considered. The publication gate then recomputes
the complete inventory and every digest; tag authority alone never satisfies
that gate.

Do not reuse a qualification run ID as an eligibility, tag-receipt, tag-asset,
or public-asset run ID. Do not put a private Factorio archive, credentials, or
unreviewed route observations in any workflow artifact or environment variable.
