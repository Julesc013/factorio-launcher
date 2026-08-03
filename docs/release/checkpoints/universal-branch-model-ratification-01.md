# Universal branch-model ratification

WorkUnit: `UNIVERSAL-BRANCH-MODEL-RATIFICATION-01`  
Date: 2026-08-04  
Authority: governance-only, routine reversible development

## Result

FacMan, Universal Launcher, and Universal Setup now formally use protected
`main`, continuously integrated `dev`, exact-`dev` `task/*`, and synchronized
`hotfix/*` branch roles. Stable consumers remain pinned to exact provider
commits reachable from provider `main`; exact provider-`dev` canaries and later
consumer adoption are separate tracks.

The superseded provider `main + task/*` doctrine was removed from current
branch-governance and component-ownership authority. Historical checkpoints
remain immutable.

## Exact provider revisions

| Repository | Pre-ratification `main == dev` | Task head | Hosted-green dev integration | Synchronized `main == dev` closeout |
| --- | --- | --- | --- | --- |
| Universal Launcher | `417c8b705d7b1a320091aa20954e382dcb62be4c` | `349d113f3bfbf0ff055037b88cefdb711850043b` | `365847083925777ee3467a6649dd26cc9fb3da59` | `db58cdffefe470cbd01a79558d177db3dda8aa32` |
| Universal Setup | `1a3fe548d278da038b96579363c1ddb7d92edeee` | `c4a278404db929f050d853d92cbe110126864cbd` | `aafd8f847c73629f277686c4a0de56f86b6d38a9` | `095a6cf4e5d9635201c29c466dcb71ce359f9374` |

FacMan work started from synchronized `main == dev` revision
`85896eb24b799fb85449be78ea37be05ed13a9b9` on
`task/universal-branch-model-ratification-01`. The final FacMan ref observation
is intentionally live/out-of-tree evidence because a tracked file cannot name
its own eventual promotion closeout commit.

## Hosted validation

| Repository/ref | Run | Result |
| --- | --- | --- |
| ULK task | `30859756668` | pass |
| ULK dev integration | `30859888975` | pass |
| ULK synchronized main | `30860012971` | pass |
| ULK synchronized dev | `30860012743` | pass |
| USK task | `30859765649` | pass |
| USK dev integration | `30859893868` | pass |
| USK synchronized main | `30860018237` | pass |
| USK synchronized dev | `30860018244` | pass |

Local validation also passed:

- ULK full Python suite: 12 tests; strict policy: pass.
- USK full Python suite: 23 tests; strict policy: pass.
- FacMan branch-policy, component-ownership, canonical-plan, and focused unit
  checks: pass.

## WIP reconciliation

- `C1-PREVIEW-RUNTIME-PACKAGES-01` is `blocked`: retained provisional proof
  waits on the external legacy AppKit toolchain pin and fresh native
  accessibility observations.
- `C1-WINDOWS-RELEASE-CANDIDATE-01` is `planned`: workspace-root authority is
  an incomplete dependency.
- This ratification was the only active implementation WorkUnit during its
  closeout.

## Authority and dependency effects

- FacMan consumed ULK remains
  `7fc25340623131ba86c08dca4fb8a43b18a4520d`.
- FacMan consumed USK remains
  `3048128963dc718a7c38c1cfcdda9e813a23b0db`.
- No provider contract, provider pin, product execution, Setup mutation,
  successor route, credentials, signing, release tag, or publication authority
  was opened.
- Branch protection/workflow installation, consumer canaries, adoption bot,
  incubator enforcement, and provider contract implementation remain separate
  later WorkUnits.
