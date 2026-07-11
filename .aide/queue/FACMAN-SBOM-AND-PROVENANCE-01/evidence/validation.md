# Validation

Result: LOCAL GATES PASS; EXACT-SHA ARTIFACT CI PENDING.

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
