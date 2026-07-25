# Repository branch governance

FacMan, Universal Launcher, and Universal Setup ship as one pinned product
train, but they intentionally do not use identical branch models.

| Repository | Canonical model | Reason |
| --- | --- | --- |
| FacMan | `main` + integration `dev` + short-lived task/promotion branches | Product gates and several product-owned changes may be integrated before a reviewed canonical promotion |
| Universal Launcher | `main` + short-lived task branches | Provider contracts are independently validated and merged as bounded trunk changes |
| Universal Setup | `main` + short-lived task branches | Setup lifecycle waves are independently validated and merged as bounded trunk changes |

The absence of Universal `dev` branches is deliberate, not missing
infrastructure. Do not create branch symmetry solely to make commit graphs look
alike.

## Provider-first product train

Cross-repository work follows this order:

1. implement a product-neutral contract in its owning Universal repository;
2. pass that repository's independent validation;
3. merge or otherwise select the reviewed provider revision;
4. update FacMan's workspace and dependency locks in a separate consumer
   change;
5. reject local configure, verification and packaging if either Universal
   checkout differs from the lock;
6. reconstruct detached clean worktrees at the exact three revisions;
7. run provider tests, the FacMan superbuild, installed/package proof and
   cross-repository boundary checks;
8. promote FacMan through its normal `dev` to `main` process.

No cross-repository commit is atomic. The workspace lock is the product-train
identity. A provider change is not part of FacMan until the consumer pin and
clean compatibility proof are accepted.

## Integration limits

- Provider work starts from a real FacMan or Dominium consumer need; equal
  weekly commit counts are not a goal.
- Universal Setup remains the only install-mutation authority.
- A FacMan integration branch should contain no more than one open authority
  gate or one completed-but-unpromoted WorkUnit train.
- Local validation verifies revisions without switching provider branches.
  Alignment is a separate explicit operation.
- Detached worktrees are valid proof inputs and must pass the same exact-HEAD
  checks as ordinary checkouts.
- No task branch, local proof, or automated check grants signing,
  publication, real-Play or human-verdict authority.
