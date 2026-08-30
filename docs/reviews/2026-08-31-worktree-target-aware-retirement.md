# Target-aware worktree retirement checkpoint

Date: 2026-08-31  
WorkUnit: `FACMAN-WORKTREE-TARGET-AWARE-RETIREMENT-01`

## Outcome

The external development store now binds every managed worktree to the shared
control checkout, its canonical path, branch, and declared merge target. A
linked worktree uses Git's common directory for repository identity instead of
creating a second path-derived repository store.

Retirement is fail closed. Removal requires all of the following:

- a valid store marker and per-worktree ownership record;
- a canonical external path that is not locked, linked, detached, or dirty;
- the local branch and worktree at the same exact head;
- that head reachable from the declared target;
- a GitHub pull request with that exact head merged to the declared target;
- no open pull request using the retiring branch as its base.

The helper uses plain `git worktree remove`. It does not force removal, prune
other administrative records, or delete local or remote branches. Default
retirement targets are `origin/dev` for `task/*` and `origin/main` for
`release/*` and `hotfix/*`; evidence worktrees require an explicit target.

Task-root cleanup also retains roots belonging to every active registered
worktree, not only the checkout that invoked the command. Reparse-point and
linked task roots are reported and refused.

## Live adoption observation

The one existing FacMan secondary worktree was explicitly adopted at its exact
canonical path with declared target `origin/dev`. The resulting doctor report
passed with two total worktrees: the primary `dev` control checkout and this
active task worktree. The cleanup plan contained no task-root deletion, and the
worktree plan refused the active dirty worktree.

This is the day-zero observation for the requested seven-day retention cycle.
Seven elapsed days have not yet occurred, so the retention-cycle claim remains
open and must not be reported as complete.

## Validation

- `python -m unittest tests.test_development_layout -v`: 17 passed.
- `python -m py_compile tools/development_layout.py tools/workspace_hygiene.py`:
  passed.
- `python tools/source_format_check.py`: passed.
- `python tools/workspace_hygiene_check.py`: passed.
- `git diff --check`: passed.
- Live `paths`, `doctor --measure`, `clean`, and `worktrees` dry runs: passed.
- Broad unit discovery: 1,320 tests run; 967 passed and 349 skipped. Four
  environment-dependent checks did not pass in the isolated task worktree:
  the built-package runtime fixture was absent, and three checks could not use
  the workspace lock because the isolated worktree has no sibling provider
  checkouts at its relative paths. The focused hygiene tests and all directly
  changed static checks passed.

## Remaining verification

- Prove the exact task-head merged-PR path after this branch merges to `dev`.
- Retire this worktree from the primary control checkout and then delete the
  local task branch as a separate operation.
- Complete the seven-day retention observation on or after 2026-09-07.
- Port the reviewed behavior through independent Universal Launcher and
  Universal Setup changes rather than editing those repositories from FacMan.
