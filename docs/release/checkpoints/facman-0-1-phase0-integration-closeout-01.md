# FacMan 0.1 Phase-0 integration closeout

Date: 3 September 2026 (AEST)

Status: complete. PRs #242 and #243 are merged by normal merge commits and the
exact final `dev` merge head passed every returned workflow group.

## Canonical integrated state

Protected `dev` is `0d61feede2acd49bf54a4a7a1cd00bba3c867fb2`, tree
`5ff92f7ee668a900dfe26bbdcba2c061492358de`. Its parents are the #242 merge
`f99d96e002f5af519824942a1f8b74bcc26d96f8` and the exact #243 head
`a2b93e00c45a9c3c8b9c05a55354104bfd36f29a`.

| WorkUnit | PR | Exact head | Merge commit |
| --- | ---: | --- | --- |
| Alpha.5 final candidate closeout | #242 | `03efb41090c11bad27368071f5cb288f7c28e6fd` | `f99d96e002f5af519824942a1f8b74bcc26d96f8` |
| Active release-view consolidation | #243 | `a2b93e00c45a9c3c8b9c05a55354104bfd36f29a` | `0d61feede2acd49bf54a4a7a1cd00bba3c867fb2` |

The final merge head passed `ci`, `code-security`, `schema-check`,
`security-policy`, and `synthetic-product-tck`: five workflow groups and
twelve jobs/checks, all successful. Exact run identities are in
`release/index/phase0_integration_closeout.v1.toml`.

## Current release selection

`release/index/active_release_view.v1.toml` remains the sole selector. It
selects `windows_product_x64`, `macos_product_x64`, and `linux_product_x64`
and the six products plus `SHA256SUMS` and the evidence archive. Older CLI,
TUI, toolkit, candidate, and distribution records remain historical.

## Qualification and authority boundary

The Alpha.5 candidate remains qualified only at source `4683ecd9…`, tree
`c0793861…`, run `33603385303` attempt 1. Neither truth-only merge inherits
that product qualification. Real Play, managed-install acceptance, human GUI
acceptance, Beta allocation, signing, tagging, publication, and support remain
closed.
