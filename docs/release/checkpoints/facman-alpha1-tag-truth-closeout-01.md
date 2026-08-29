# FacMan alpha.1 tag truth closeout 01

Date: 29 August 2026

State: `active_truth_only_non_authorizing`

## Result

`FACMAN-0.1.0-ALPHA.1-TAG-TRUTH-CLOSEOUT-01` records the sealed tag-only
alpha after the effecting workflows completed. It changes no product bytes:
the three packages remain built from product source `fa60aaa17e90` and tree
`553689166246`, while the tag machinery is separately identified by control
source `871fee8d63ea`.

G0 and G1 are complete. The exact annotated tag `v0.1.0-alpha.1` points to
`fa60aaa17e9044bef7bb7347261056959690f1cd`, tag object
`52a7a66092ff2b3b3c1059e9c29260f95b1cb287`. Ruleset `21787868` is active
for `refs/tags/v0.1.0-alpha.*`, restricts update and deletion, has no bypass
actors, and reports that the authenticated operator can never bypass it.

## Retained workflow chain

```text
qualification       33200886091  success
eligibility         33243814307  success
annotated tag       33243912537  success
tag-only assembly   33243989847  success
```

The tag-only artifact contains 16 files: the three exact Windows packages,
their SBOM/provenance/licence records, candidate record, checksum manifest,
tag receipt, and known limitations. Its checksum inventory has zero failures
and zero pending members. No GitHub release exists.

## Frozen machine candidate

```text
machine completeness  29 / 29
candidate record      8e18cf7b35d34aee2e39bc6bae0710db48dceef4196d5ff0373b880bfc866573
contract set          7d59831268babc1be96192f8ed74f5aa5f5c85d9d1fdf9e392cc943f99eae264
provider lock         d33943841431afdeffb7961c7453d8999619ef371793a6310ad2c2952b118f00
CLI package           62e45380674728cf7712238d96fd241bc1954780f24c5fe1dfea7e9bdde20fc5
TUI package           cadd6277438ec188946fd0ea6b6b77a52f430e784583af39fc2a3ca78de39b48
WinForms package      00fcf5dfc9597a7118ad8d81ff4489d5ace6019c272e79bcc12e966547149c86
```

Windows is the unsupported, unsigned, unpublished portable alpha platform.
Linux CLI/TUI remains exploratory package-preview evidence, and GTK remains a
frontend-only prototype rather than a complete portable product package.

## Route and remaining gates

Route v5 integrated through PR #198 as merge `31548e443955` with all seven
fresh merged-SHA workflows successful. It remains non-authorizing: no D3/D4
request is active, no permit has been issued, no Factorio process or Sandbox
has launched, and accepted real-Play routes remain zero.

The exact-package human receipt remains `Inconclusive` in all nine lanes with
an unassigned tester. Public alpha, beta, RC, plain `0.1.0`, `main` promotion,
signing, publication, support, route promotion, and human-verdict authority all
remain false. A product/package byte change requires `0.1.0-alpha.2`; the
alpha.1 tag must never move or be reinterpreted.
