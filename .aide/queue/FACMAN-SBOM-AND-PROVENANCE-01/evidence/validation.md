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
