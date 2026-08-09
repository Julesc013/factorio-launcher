# Versioning and release train

The canonical current product version is authored in
`release/index/version.v2.toml`. `version.v1.toml`, the build manifest, native
headers, command catalogs, package names, and provenance are checked
projections. They are not independent version sources.

The complete train law is machine-readable in
`release/index/version_train.v1.toml`. That record defines the intended train;
it does not authorize a tag, signature, upload, support promise, or public
release.

## Independent version domains

These identities advance independently and must never be inferred from one
another:

- FacMan product SemVer;
- FacMan package revision;
- FLB, ULK, ULU, USK, and USU ABI versions;
- provider package versions and exact source commits;
- command, refusal, result, presentation, and transport contracts;
- workspace and persisted-record schemas;
- target, capability, guarantee, route, and evidence identities.

Every release ledger entry binds the exact value of every domain it consumes.
Compatibility is an explicit matrix and migration law, not a consequence of
similar version numbers.

## Precedence-correct product identities

FacMan follows SemVer precedence. Development, alpha, beta, and release
candidate builds use SemVer prerelease identifiers; build metadata is used
only for non-precedence provenance.

```text
0.1.0-alpha.0+dev.<run>.g<sha>  untagged disposable build
0.1.0-alpha.1                  autonomous immutable alpha
0.1.0-beta.1                   human-tested beta candidate
0.1.0-rc.1                     frozen release candidate
0.1.0                          stable 0.x release, marketed as Public Beta
1.0.0                          full supported release
```

`0.1.0+dev.*` is forbidden for development identity because build metadata
has the same SemVer precedence as `0.1.0`. Artifact filenames may replace `+`
with `-` when a packaging format requires it, while manifests retain the
canonical identity.

Tracked authored truth uses
`facman-0.1.0-alpha.0+dev.contract` as a non-publishable contract identity so
generated source and fixture packages remain deterministic. A real snapshot
build must project `0.1.0-alpha.0+dev.<run>.g<sha>` from its exact run and Git
identity into out-of-tree build provenance. Per-run values are never written
back into the authored version record, and `+dev.contract` can never be tagged
or published as a release identity.

## Release classes

| Class | Source | Tag | Human receipt | Publication/support |
| --- | --- | --- | --- | --- |
| Snapshot | exact accepted task or `dev` head | none | no | disposable, unpublished, unsupported |
| Alpha | exact three-key accepted `dev` head | immutable `vX.Y.Z-alpha.N` | no experiential receipt | non-public or bounded prerelease only; no stable support |
| Beta | frozen `release/X.Y` candidate | immutable `vX.Y.Z-beta.N` | required for admitted journeys | human-authorized prerelease |
| RC | frozen `release/X.Y` candidate | immutable `vX.Y.Z-rc.N` | required and current | human-authorized release candidate |
| Stable 0.x | accepted `main` | immutable `v0.Y.Z` | required | public beta support class defined by ledger |
| Stable 1.x | accepted `main` | immutable `vX.Y.Z` | required | full support class defined by ledger |

No commit receives a tag merely because it is green. A release-significant
change invalidates the candidate receipt and creates the next prerelease
number. Published tags and assets are never moved, deleted, or replaced;
withdrawal is an append-only state transition governed by the withdrawal
section of `release/index/version_train.v1.toml` and exact ledger records.

## Planned product train

The milestone contract separates internal engineering levels from public
product versions:

```text
C1 internal alpha foundation
  -> 0.1.0 Windows x64 CLI + TUI + WinForms public beta
  -> 0.2.x AppKit product lane
  -> 0.3.x GTK product lane
  -> 0.4.x Qt 6 Widgets product lane
  -> 0.5.x operational parity
  -> 0.6.x migration and compatibility maturity
  -> 0.7.x SDK and bounded extensibility
  -> 0.8.x hardening
  -> 0.9.x feature and contract freeze
  -> 1.0.0 complete CLI/TUI + WinForms/AppKit/GTK/Qt Widgets release
```

The exact release milestones live in `release/index/plan.v1.toml`; admitted
capability rows, exclusions, and proof obligations live in
`release/index/capability_frontend_matrix.v1.toml`. “Complete” means every
admitted row meets its evidence contract; it does not mean an unbounded claim
of perfection.

## Release ledger

Every tagged build eventually has one append-only directory under
`release/ledger/<version>/`. The entry binds source commit and tree, provider
source/package/ABI/contract identities, release-resolution root, artifacts,
SBOM, provenance, tests, known limits, support class, migration/rollback law,
withdrawal state, and the required human receipt. See
`release/ledger/README.md`.

Current repository state remains pre-publication. None of this document grants
Factorio execution, Setup mutation, credentials, signing, publication, support,
route capability, or route promotion.
