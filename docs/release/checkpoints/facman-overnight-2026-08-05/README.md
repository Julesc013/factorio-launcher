# FacMan overnight evidence checkpoint — 2026-08-05

## Disposition

The overnight run produced a reviewable source-closure implementation and
stopped at the correct non-authorizing boundary.

- FacMan source-closure head:
  `bcc0233ccda9b7d29467d4ba5da613a2e016a36f`.
- Remote `dev` at observation:
  `22a70c0280cc410083d5d9b093f0b05245d691e1`.
- Remote `main` at observation:
  `b70be10696855628c6d2948eb016c8424912e14e`.
- Source-closure state: `required_but_blocked`.
- Task-ref source closure passed: `false`.
- Canonical source closure passed: `false`.

The remaining conditions are intentionally classified separately:

| Condition | Classification |
| --- | --- |
| Provider-lock mismatch | unresolved repository/product-governance decision |
| Native `cmd.exe` denial | execution-environment limitation |
| Source closure incomplete | consequence of the two preceding blockers |
| Play unavailable | separate product-authority boundary |

## Review topology

- PR #120 route law: merged at
  `d31a9925fd168f6fc23f2c2b1d4b4c2d7dbfc237`; non-authorizing.
- PR #121 head:
  `e5ed76e303f6e13306d3e80146872bfe6decf3ae`; retrospective review,
  already contained by `dev`.
- PR #122 head:
  `9ccfc86ef9991e842aa3d05b607c22b5541caa53`; retrospective review,
  already contained by `dev`.
- PR #123 head:
  `bcc0233ccda9b7d29467d4ba5da613a2e016a36f`; six commits ahead of
  `dev`, zero behind at observation.

PRs #121 and #122 must not create a second integration. PR #123 remains a
draft source-closure implementation and is not merge-ready until provider
identity and native closure prerequisites are resolved.

## Evidence custody

The four raw overnight artifacts named in
`evidence-manifest.v1.json` were copied byte-for-byte from temporary storage
to two separate durable stores. Every copy was rehashed after writing and
matched the tracked manifest.

Raw observations and logs are deliberately not committed here because they
contain machine-specific paths and execution-environment detail. This
checkpoint tracks normalized conclusions, exact record identities, hashes,
sizes, classifications, and security dispositions only.

## Authority statement

This checkpoint grants no provider repin, Factorio execution, observer,
stage, prepare, permit, Setup mutation, signing, publication, stable-support,
route capability, route promotion, protected merge, or protected-ref write.

## Retention

Keep both durable raw-copy sets until canonical source closure has passed and
a separate evidence-retention decision explicitly supersedes this checkpoint.
