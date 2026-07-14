# M1 Public Integration Proof

Status: **accepted public integration evidence**.

This immutable checkpoint binds the already-accepted M1 implementation proof
to its final `dev` checkpoint, canonical `main` promotion, and exact hosted
workflow evidence. It is an evidence-only successor: it neither rewrites the
WU12 implementation identity nor enlarges setup or execution authority.

## Revision and tree chain

| Layer | Revision | Git tree | Meaning |
| --- | --- | --- | --- |
| WU12 task head | `2f13923a9cbdd60d47cab114ba1e280282259bb5` | `e45dc68be8b2cad93814d57c9de6f4f2863019ec` | accepted implementation and reproducibility proof |
| WU12 `dev` merge | `10b1caa915ed4ad5e934f625f3e1384ecc700eaa` | `e45dc68be8b2cad93814d57c9de6f4f2863019ec` | reviewed WU12 integration |
| final checkpoint `dev` merge | `cfd30b769cc97e3703da4027aee8078ddf320dc6` | `8a9c9dc29849db0922b7a0ffa337903c9f011e01` | final M1 machine-truth closeout |
| canonical `main` promotion | `73bec99916d509b0ab055a43562e93ef20a6b4b7` | `8a9c9dc29849db0922b7a0ffa337903c9f011e01` | reviewed public canonical integration |

The WU12 task and merge trees are identical, as are the final checkpoint and
canonical-promotion trees. The final checkpoint intentionally adds closeout
truth after WU12; its different tree is not presented as implementation proof.
The distinct revisions preserve the difference between implementation, `dev`
integration, closeout, and public canonical proof. This bookkeeping successor
is based on the canonical merge;
merging it to `dev` therefore makes `73bec999…` an ancestor of `dev` without
pretending this later evidence file was present in the frozen M1 tree.

## Exact final `dev` workflows

The final checkpoint merge `cfd30b769cc97e3703da4027aee8078ddf320dc6`
completed successfully in:

- CI `29301453095`;
- Code Security `29301453067`;
- Security Policy `29301453099`; and
- Release Policy `29301469120`.

The schema contract was unchanged from the carried-forward accepted WU11
schema proof recorded in the implementation checkpoint.

## Exact canonical `main` workflows

The canonical promotion `73bec99916d509b0ab055a43562e93ef20a6b4b7`
completed successfully in:

- CI `29310497458`;
- Code Security `29310497459`;
- Security Policy `29310497496`;
- Schema Check `29310497454`; and
- Release Policy `29310506019`.

The exact-main CI matrix covers Linux native, sanitizer, bounded fuzzing,
coverage and package proof; Windows Debug/Release native, WinForms, TUI,
package and reproducibility proof; macOS native/package/archive; and AppKit
compile. Code Security covers C/C++, C#, and Python.

## Preserved M1 implementation proof

The canonical `[m1_managed_portable_install]` record remains bound to WU12 task
head `2f13923a…`, WU12 `dev` merge `10b1caa…`, Universal Setup
`2bc4bf93…`, and Universal Launcher `c43d390e…`. The accepted validation tuple
remains the WU12 implementation suite: 35 native tests, 337 Python cases, and
the package and reproducibility identities recorded in the M1 checkpoint.

## Authority boundary

- M1 remains fixture-proven; ordinary live-target apply remains unavailable;
- the Steam-backed H1 verdict remains **Fail** and standalone isolation remains
  `unproven`;
- `run.execute`, Safe beta, networking, credentials, Steam mutation, registry,
  shortcuts, elevation, system-wide setup, signing, and publication remain
  unavailable; and
- this proof performs no product mutation and grants no setup or execution
  authority.
