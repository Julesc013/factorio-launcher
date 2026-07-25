# Gate 4B public integration proof

## Accepted revisions

Gate 4B is closed on `dev` as a reviewed technical candidate that is eligible
for the separate human verdict and nothing more.

| Identity | Revision |
| --- | --- |
| PR #52 reviewed implementation head | `da3e2274a3dc8a5757078b20276a1a6a93084860` |
| PR #52 implementation merge | `e9c1e69fee1ae815f62638db8b7263cb01b70389` |
| PR #53 reviewed closeout head | `e60ff931317aaa6a68b7cbfd820afb4b4fce3676` |
| PR #53 closeout merge | `7fe12635f7309e4fd709810dd192d43ff920592f` |
| Universal Launcher pin | `7bd4425f0c35414f738159b45d8bec42edf70235` |
| Universal Setup pin | `3f8489275077347c2918f3bb03614ec6431362ff` |

The frozen policy remains
`6fde31f26d57e23d67c01dd598cb869a4914d11711868b46d4f817709455e7a2`.

## Hosted proof

The implementation head and merge passed the complete recorded matrices in
the Gate 4B closeout. The separate evidence-only closeout passed:

| Proof | Push | Pull request | Exact merged `dev` |
| --- | --- | --- | --- |
| CI | `29911647564` | `29911672399` | `29912502213` |
| Code security | `29911647498` | `29911672382` | `29912502124` |
| Security policy | `29911647205` | `29911672471` | `29912502140` |
| Schema | path-filtered | path-filtered | path-filtered |

The closeout changed no contract or schema. Local strict validation passed all
125 command contracts, 123 registered routes, 279 schemas, and 242 refusal
codes. The implementation's exact schema proofs remain `29909518641` at the
reviewed head and `29910545091` at its merged `dev` revision.

The final evidence branch also passed project-state, queue/target truth, AIDE
Lite, and the complete Python discovery suite: 377 tests passed with 312
target-specific skips. Its Windows package tests used the supported
`FACMAN_NATIVE_BUILD_ROOT` override against the verified task-scoped build;
no build tree was created inside the source repository.

## Clean reproduction

A detached, no-hardlink three-repository reconstruction pinned the revisions
above. Universal Launcher and Universal Setup configured, built, passed CTest,
and passed strict validation. FacMan passed its 48-test TUI-enabled native
matrix, AIDE Lite, strict validation, and all 375 Python tests. The serial run
completed in 548.3 seconds and all detached source checkouts remained clean.

## Exact disposition

```text
eligible_for_human_verdict
```

`FACMAN-HERMETIC-STANDALONE-PLAY-VERDICT-01` is active. It may conduct only the
frozen operator-reviewed Gate 4C journey. It cannot repair implementation,
change policy, or enable a product route.

This integration records no human `Pass`, `Fail`, or `Inconclusive` verdict and
promotes no public command, product permit issuance, Factorio execution, Setup,
credential, network, Steam, host-mutation, signing, publication, playability,
Safe beta, or canonical-`main` authority.
