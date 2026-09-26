# FacMan development cleanup, 26 September 2026

The operator requested immediate cleanup and bounded resource use. Builds were
stopped during inventory; the active managed-install patch was preserved.

## Removed and retained

- Removed 35 explicitly inventoried FacMan CMake output directories:
  10.613 GiB on C:, 16.759 GiB on D:, and 4.370 GiB on E:.
- Retained each build's configuration, source identity and CTest logs in
  verified archives before removal. Receipts record exact paths and digests.
- Removed 12.858 GiB from the obsolete `C:\FacManPrivateRoute` staging root.
  Its three private archives matched the retained original's SHA-256
  `cd96202e93ef93e170c8f37dda0ebacb9031011ab81770a5eec075a067e3da30`.
  The original remains under `E:\Temporary\FacMan\FacManRoute`.
  Other route evidence was retained in a verified archive.
- Relocated all `C:\FacManRealRoute0fb` data intact, on the same volume, into
  the existing owned lab-input task root under LocalAppData. No game data was
  discarded or executed.
- Stopped 11 orphaned MSBuild nodes, approximately 800 MiB of working memory.
- Consolidated 18 FacMan download directories into verified archives in the
  owned task root, then removed their expanded copies. Each retained file has
  a SHA-256 relocation manifest; the disposable WSL coverage venv retains its
  configuration rather than linked interpreter copies.
- Archived and retired three small inactive task roots, restoring the
  canonical task-root count to eight. Their clean pinned provider checkouts
  and metadata remain recoverable from the retained archives.
- Corrected the resource-identity worktree's stale path/branch binding, then
  retired its clean exact-head checkout through the hygiene tool and deleted
  the merged local branch. PR #259 binds source `fd051e661f036823efaeeaccbfc541cd46b12d73`
  to `dev`; no open PR uses that branch as its base. The provider-canary
  checkout remains retained because its head lacks an exact merged task PR.

The combined deleted file inventory was 44.600 GiB. This is a logical file
size total, rather than a claim about physical allocation or other sessions'
cleanup. The concurrent USK session's deletions are not counted here.

Machine receipts and retained evidence reside under the current owned root:
`D:\Development\FacMan\repositories\factorio-launcher-5db2844e2f29\tasks\task-facman-m-a2c1c5db81`.
The download archives carry per-file SHA-256 relocation manifests. Historical
receipts retain their original source and candidate identities.

## Prevention

The developer entry point now refuses unowned output overrides and output
owned by a different task. It checks an 8 GiB free-space reserve before
configure, native build and package operations. Native builds default to two
workers, and Visual Studio does not retain reusable MSBuild nodes after exit.
The clean rebuild requirement for disabled FileTracker remains in place.

Validation: `python -m unittest tests.test_development_resource_limits
tests.test_development_layout -q` passed 30 tests. The engineering source
budgets and `git diff --check` passed. These checks qualify the resource
guard changes; the uncommitted managed-install implementation still needs its
own runtime and packaged recovery verification.

## Implementation custody

Two unowned historical task directories were consolidated intact into the
current marker-owned task's `retained-historical-task-roots` folder. They held
1,022,518,051 bytes. The operation used same-volume directory renames, verified
file counts and byte totals, and deleted no files. Linked worktrees and running
process references were checked before the move. The custody receipt is
`historical-task-root-consolidation.json` in the current task root.

The measured canonical task store now has six task roots and no unowned roots.
Three obsolete local task branches were retired after verifying exact merged
PR heads, dev integration, no unmatched commits, no dependent open PR and no
linked worktree. The custody receipt is
`merged-local-branch-retirement-receipt.json`. The abandoned reactivation branch
and legacy provider canary worktree remain preserved because their exact
retirement evidence is incomplete. The earlier 44.600 GiB logical cleanup
total is unchanged; consolidation did not reclaim those preserved bytes.

PR #339 is integrated at `dev@3111b853664b968d82919c79dfdfad9a12839f9e`.
Requested commit `07f00ece1a34203b93e07491c86486d0281d44d9` is an ancestor.
The active branch is `task/facman-managed-install-verification-01`, retaining
the committed request-binding slice and uncommitted install/recovery work.
The full 0.1 goal and remaining acceptance leaves stay open.
