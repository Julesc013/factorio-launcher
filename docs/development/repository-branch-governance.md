# Repository branch governance

## Authority classification

Routine reversible development is automatic when a bounded WorkUnit and its
mechanical guards exist. This includes fetch, creating `task/*` from the
recorded exact reviewed revision, task worktrees, in-scope edits and checks,
ordinary commits, non-protected task-branch pushes, draft pull requests, and
cleanup of abandoned local task branches or worktrees.

Task-branch creation requires an existing `ready` or `active` WorkUnit, an
exact recorded base match, a non-conflicting `task/*` name, a clean current
worktree, and no protected-ref change. These checks replace human confirmation;
they do not bypass validation.

Merging into `dev` or `main`, direct protected-ref updates, force-push or
published-history rewrites, release tags, signing, and publication require
explicit repository authority. Credentials, authenticated product writes,
Setup or foreign-installation mutation, permit issuance, Factorio execution,
observer capture, human verdict, and route promotion remain separately
authorized product actions.

FacMan, Universal Launcher, and Universal Setup form a continuously integrated,
independently releasable platform train. They use the same branch roles without
coupling repository histories or consumer locks.

| Repository | Canonical model | Reason |
| --- | --- | --- |
| FacMan | `main` + integration `dev` + short-lived `task/*` and `hotfix/*` branches | Product gates and product-owned changes integrate before reviewed canonical promotion |
| Universal Launcher | `main` + integration `dev` + short-lived `task/*` and `hotfix/*` branches | Provider changes integrate continuously and remain independently releasable |
| Universal Setup | `main` + integration `dev` + short-lived `task/*` and `hotfix/*` branches | Setup changes integrate continuously without opening product mutation authority |

For every repository, `main` is stable canonical source and `dev` is the green
next integration train. `main` must always be an ancestor of `dev`. Normal
`task/*` work starts from an exact recorded `dev` revision and targets `dev`.
Only reviewed `dev -> main` promotions or explicit `hotfix/* -> main` changes
target `main`; a hotfix is immediately synchronized back to `dev`. Release tags
are created only from accepted `main`.

Protected refs reject force pushes, deletion, and direct writes. A provider
may have at most one completed-but-unpromoted WorkUnit on `dev`. This keeps
provider `main` current without no-op commits or unrelated history copying.

## Provider-first product train

Cross-repository work follows this order:

1. create the provider task branch from an exact recorded provider `dev`;
2. implement a product-neutral contract and pass provider-local validation;
3. merge the task to provider `dev` and run exact-SHA consumer canaries;
4. promote the reviewed provider `dev` to provider `main`;
5. open a separate consumer-adoption change for one exact provider pin;
6. reject local configure, verification and packaging if either Universal
   checkout differs from the lock;
7. reconstruct detached clean worktrees at the exact three revisions;
8. run provider tests, the FacMan superbuild, installed/package proof and
   cross-repository boundary checks;
9. promote FacMan through its normal `dev` to `main` process.

No cross-repository commit is atomic. The workspace lock is the product-train
identity. A provider change is not part of FacMan until the consumer pin and
clean compatibility proof are accepted.

## Dependency tracks

- Stable consumer builds use exact provider commits reachable from provider
  `main`; tracked locks never point to `dev`.
- Canary CI may test exact provider `dev` SHAs supplied as workflow inputs, but
  writes observations out of tree and does not change the stable lock.
- Adoption follows provider promotion through a separate bot-created or human
  task branch and pull request. Automation may open or update that PR, but it
  cannot approve, merge, publish, sign, or push a protected branch.

## Integration limits

- Provider work starts from a real FacMan or Dominium consumer need; equal
  weekly commit counts are not a goal.
- Provider `dev` moves only for reusable provider code, contracts, tests, SDKs,
  tools, or documentation; product-only FacMan work creates no provider commit.
- Compatibility evidence can move on every relevant consumer change even when
  provider source does not.
- Universal Setup remains the only install-mutation authority.
- An open FacMan authority gate may coexist with bounded product task branches.
  The gate blocks only its enumerated authority and the plan's WIP and
  path-ownership limits govern unrelated development.
- Local validation verifies revisions without switching provider branches.
  Alignment is a separate explicit operation.
- Detached worktrees are valid proof inputs and must pass the same exact-HEAD
  checks as ordinary checkouts.
- No task branch, local proof, or automated check grants signing,
  publication, real-Play or human-verdict authority.
