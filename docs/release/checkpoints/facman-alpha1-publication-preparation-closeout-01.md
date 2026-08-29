# FacMan alpha.1 publication-preparation closeout 01

Date: 2026-08-30
Integrated WorkUnit: `FACMAN-0.1.0-ALPHA.1-PUBLICATION-PREPARATION-01`
State: protected-`dev` integration verified; G2, G3, and publication authority pending

## Outcome

PR #201 integrated the fail-closed alpha.1 publication controls into protected
`dev` with a normal merge commit. The integration changes only the release and
control plane: frozen product revision
`fa60aaa17e9044bef7bb7347261056959690f1cd`, tree
`5536891662461d3617ee40e93654cb2f0659905c`, immutable tag
`v0.1.0-alpha.1`, and all three package archives remain unchanged.

The reviewed integration is:

- base `772238ccd9a11481657b9525011ff6dfc8dfaaab`;
- task head `24688847f8b2ed0f54aafe96150ba68dce6a78b4`;
- merge `edf61bdf0fe00692a73a58c3586ac4f7c0dbfec4`;
- merge tree `7dc49419a7127a70b6085952d03d1acd179985e4`;
- parents exactly the base and task head above;
- merge actor `Julesc013` at `2026-08-29T17:30:22Z`.

## Hosted validation

The exact pull-request head passed five required workflow runs plus the
GitHub Advanced Security CodeQL check: 13 of 13 emitted checks succeeded. The
exact merge head then passed the five protected-`dev` workflows and all 12
emitted checks:

- schema check `33265801696`;
- CI `33265801707`;
- security policy `33265801710`;
- synthetic product TCK `33265801748`;
- code security `33265801809`.

The CI run includes Linux native, Linux coverage, macOS native, macOS archive,
AppKit, Windows static/shared native, WinForms, package proof,
reproducibility, strict policy, legacy compatibility, and package-composition
success.

## Remaining GO ladder

G1 remains complete. G2 remains pending because the exact nine-lane receipt is
`Inconclusive` in every lane and has no assigned tester. G3 remains pending
because the route-v5 request grants no D3/D4 authority, permit, execution,
verdict, capability, or promotion. Consequently G4 public alpha remains
unauthorized, and beta, RC, stable `0.1.0`, `main`, production signing,
publication, support, and later promotion are not reached.

The machine-readable closeout is
`release/index/alpha1_publication_preparation_closeout.v1.toml`. It records
only reviewed integration and gate truth; it creates no release environment,
credential, permit, Factorio process, signature, GitHub release, or support
claim.
