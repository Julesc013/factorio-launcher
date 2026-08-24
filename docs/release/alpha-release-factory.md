# Alpha release factory

The manual `alpha-release` workflow separates machine qualification, route
acceptance, and publication into three invocations. No invocation infers the
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

## 3. Publish the already assembled bytes

Dispatch `operation=publish` only after the `alpha-publication` environment
contains the separately reviewed `FACMAN_ALPHA_1_PUBLICATION_AUTHORITY_JSON`.
The input run ID must identify the route-bound assembly run. The publication
gate recomputes the complete inventory and all digests before creating the
annotated tag, draft prerelease, assets, and final public prerelease.

Do not reuse a qualification run ID as a publication run ID. Do not put a
private Factorio archive, credentials, or unreviewed route observations in any
workflow artifact or environment variable.
