# Validation

Result: PASS, including exact-SHA artifact provenance CI.

- Complete Python suite: PASS (222/222, zero skips).
- Strict checks: PASS with 63 schemas and the new provenance checker.
- AIDE Lite portable suite: PASS.
- Local Windows selected package build, 165-file runtime integrity, SPDX schema,
  external provenance generation, and verifier: PASS.
- Mutation proof rejects artifact, component manifest, hash manifest, workspace
  lock, source revision, and CI identity drift.
- Source format and `git diff --check`: PASS.

The local dirty-tree provenance records `dirty: true` plus a digest of the
binary diff and untracked source bytes; it does not masquerade as clean commit
evidence. Exact Linux CI must record a clean source state, the exact GitHub run
identity, the final tarball digest, and upload the adjacent provenance before
this WorkUnit is promoted.

All records say `publisher_authenticity_not_proven`, `signed: false`, and
`published: false`. No signature or trusted attestation claim is made.

Revision `a8aeef52c041dabcff23bf2b1de82f45a24e6691` passed Linux target
package/provenance, macOS archive, AppKit, schema, and security gates in runs
`29158099720`, `29158099731`, and `29158099722`. The Windows Python lane found
that its CI-identity mutation assigned `github_actions` to a record already
holding that value. The repair corrupts the CI-bound source SHA and additionally
compares GitHub run identity with the active build environment; no provenance
field or validation rule is weakened.

Final revision `4819b9d1bd70756bb60f44719565f3020adabab0` passed replacement
CI `29158246484` across Linux native/package/provenance, Windows
native/package/provenance, macOS archive, and AppKit compile-only. Security run
`29158246490` passed; schema run `29158099731` passed the unchanged 63-schema
surface introduced by the implementation revision.

The clean Linux tarball is 810160 bytes with SHA-256
`cfb0123a98a9f8c26619aaeb680daaa5655cb9dfe83d38a6ce0c65de54135176`.
Its adjacent provenance SHA-256 is
`09469b1097e0baf14a922af11479f6faee810ca317325489a2f3bdb9af8d65d5`
and records Actions run `29158246484`, clean source-state digest
`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`,
and `publisher_authenticity_not_proven`.
