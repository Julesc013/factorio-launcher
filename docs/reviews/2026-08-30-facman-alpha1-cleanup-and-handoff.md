# FacMan alpha.1 cleanup, status, and handoff

Date: 2026-08-30 (Australia/Sydney)

This is the durable operator handoff for the FacMan `0.1.0-alpha.1` manual-test
pause. It records what is safe to test, what was cleaned, what remains
deliberately preserved, what is blocked, and how work resumes without restoring
the previous machine sprawl.

## Answer first

- The exact product is `FacMan 0.1.0-alpha.1`, source commit
  `fa60aaa17e9044bef7bb7347261056959690f1cd`, immutable tag
  `v0.1.0-alpha.1`.
- The 16 verified tag assets are attached to the private GitHub draft
  prerelease: <https://github.com/Julesc013/factorio-launcher/releases/tag/untagged-3b60f2c730b89bd76e8a>.
- For ordinary Windows GUI testing, download
  `FacMan-0.1.0-alpha.1-windows-x64-portable.zip`.
- The draft is intentionally not public. Public alpha still requires the exact
  nine-lane human Pass, the separately accepted real route, and one-use
  publication authority.
- Manual observations do not mutate alpha.1. Any changed product bytes must be
  allocated forward as `0.1.0-alpha.2`.

## Verified package identities

| Package | SHA-256 |
| --- | --- |
| `FacMan-0.1.0-alpha.1-windows-x64-portable.zip` | `00fcf5dfc9597a7118ad8d81ff4489d5ace6019c272e79bcc12e966547149c86` |
| `facman-0.1.0-alpha.1-windows-tui-x64-portable.zip` | `cadd6277438ec188946fd0ea6b6b77a52f430e784583af39fc2a3ca78de39b48` |
| `facman-0.1.0-alpha.1-windows-cli-x64-portable.zip` | `62e45380674728cf7712238d96fd241bc1954780f24c5fe1dfea7e9bdde20fc5` |

Verify a download before extracting it:

```powershell
Get-FileHash -Algorithm SHA256 .\FacMan-0.1.0-alpha.1-windows-x64-portable.zip
```

Extract each test copy into a new empty directory. Do not overwrite a previous
test copy. Record the machine, Windows version, package filename and hash,
steps, expected result, actual result, screenshots/logs, and whether the lane
is Pass, Fail, or Inconclusive. The formal nine-lane procedure is
[FacMan accessibility human test packet](../quality/facman_accessibility_human_test_packet.md).

Exploratory manual use is useful defect evidence but does not by itself create
the formal human receipt or route authority. Real Factorio execution must stay
within the separately reviewed route/permit process.

## Machine cleanup result

Filesystem free space changed as follows:

| Drive | Before | After | Reclaimed |
| --- | ---: | ---: | ---: |
| C: | 180.44 GiB | 238.66 GiB | 58.22 GiB |
| D: | 34.98 GiB | 133.89 GiB | 98.91 GiB |
| E: | 52.11 GiB | 52.90 GiB | 0.79 GiB |
| **Total** |  |  | **157.92 GiB** |

Cleanup included:

- 78 secondary Git worktrees; the checkout went from 79 worktrees to one;
- repository `build`, `out`, `tmp`, nested worktree farms, old validation,
  qualification, overnight, archive-build, and duplicate evidence trees;
- 30 drive-root package fixtures on C:;
- 227 accessible FacMan/AIDE Temp roots and the 19.0 GB legacy
  `%LOCALAPPDATA%\FacMan\Tasks` store;
- old F8/F9/qualification material on E: while retaining the current route
  inputs;
- 102 obsolete local branches, 121 obsolete remote branches, and two obsolete
  proof tags.

Before removing unique old refs, two verified recovery bundles were retained:

| Bundle | SHA-256 |
| --- | --- |
| `D:\Projects\Factorio\.backups\facman\facman-pre-hygiene-cleanup-2026-08-30.bundle` | `a6728e5182c98f65ee6db98b250a401b636a2d2915cdd144138ce65e7779a46d` |
| `D:\Projects\Factorio\.backups\facman\facman-pre-hygiene-cleanup-extra-2026-08-30.bundle` | `073ed9c1514b768afe8da517d12f8bbea158f99fa08771966bb80d71c1197b31` |

The old draft PR #162 was closed as superseded. The only non-core remote task
branches left are the three branches attached to open Dependabot PRs #170,
#171, and #172.

## Deliberately preserved

- Source repositories:
  `factorio-launcher`, `industrial-revolution`, and `more-infinite-research`.
- `C:\FacManPrivateRoute` and `C:\FacManRealRoute0fb`, because they may contain
  real operator route/install data.
- `E:\Temporary\FacMan\FacManRoute`, containing the alpha route inputs needed
  for the pending manual/route work.
- Industrial Revolution custody, proof, and backup material.
- The two verified FacMan Git recovery bundles.
- The current small `FACMAN-0.1-GOAL-MODE-2026-08-27-01` evidence record,
  diagnostics, inbox, and task-message state.

Three old Temp fixture directories remain because their ACLs deny the current
non-elevated process even ownership inspection:

- `facman-windows-package-proof-6vhxv5l5`
- `facman-windows-tui-package-pmauz97a`
- `facman-winforms-c1-smoke-s2defkov`

They are isolated under `%LOCALAPPDATA%\Temp`, not source/build roots. Remove
them later from an administrator context after revalidating those exact paths.

## Replacement development system

The repository now defines one portable external development layout:

```text
<FACMAN_DEV_ROOT>/repositories/<repository-key>/
  tasks/<task-or-branch-id>/
  worktrees/<task-branch-id>/
```

If `FACMAN_DEV_ROOT` is unset, Windows uses
`%LOCALAPPDATA%\FacMan\Development`; Unix-like systems use their standard cache
root. `FACMAN_TASK_ROOT` remains an explicit one-task override. This gives one
knob for moving all disposable work to another disk without editing source.

The system adds:

- repository/task-bound ownership markers before build or package output;
- seven-day expiry, eight-task-root and 20 GiB default budgets;
- a maximum of two secondary worktrees;
- canonical `task/` worktree creation and plan-first cleanup;
- refusal to clean unowned, mismatched, linked, source-containing, or
  out-of-allowlist roots;
- doctor checks for in-tree output, unmanaged worktrees, stale local task
  branches, forbidden backup/proof branch prefixes, and non-release tags;
- short-lived CI artifacts: seven days for ordinary evidence, 14 days for
  canonical provider packages, and 30 days for release assembly evidence;
- static enforcement through `strict_check.py` and mandatory agent guidance in
  `AGENTS.md`.

Routine commands:

```powershell
py -3 tools/workspace_hygiene.py paths
py -3 tools/workspace_hygiene.py doctor --measure
py -3 tools/workspace_hygiene.py clean
py -3 tools/workspace_hygiene.py worktrees
```

Use `--apply` only after reviewing a cleanup plan. Create a worktree only after
the normal AIDE Git plan and operator approval:

```powershell
py -3 tools/workspace_hygiene.py worktree-add task/<work-item> --start origin/dev
```

## What happens next

### Now: operator test pause

1. Download and hash the WinForms bundle from the draft release.
2. Test on this machine, then clean Windows 10/11 x64 machines where available.
3. Capture concise notes per machine and lane; do not modify the tagged files.
4. Keep route results separate from ordinary UI/CLI/TUI usability results.

### On return: triage and alpha continuation

1. Normalize notes into defects, usability findings, environment problems, and
   route/governance observations.
2. Reproduce every actionable defect against the exact alpha.1 hash.
3. If product bytes must change, allocate `0.1.0-alpha.2`; never move the
   alpha.1 tag or replace its assets.
4. Rerun affected, full, strict, three-root/package, and relevant human lanes.
5. Complete the named nine-lane human receipt and separately review the exact
   route-v5 D3/D4 execution/promotion evidence.
6. Only after G2, G3, exact assets, and one-use publication authority are true,
   assemble and publish the unsupported unsigned public alpha prerelease.

### Product train through 0.1.1

The governed order is alpha.N, beta.N, rc.N, `0.1.0`, then `0.1.1` if a
post-0.1.0 compatible patch is needed. `0.1.1` is not the next identifier for
alpha.1 test fixes. Its entry criteria are a published `0.1.0`, a bounded patch
scope, current human/route evidence for affected journeys, migration/rollback
truth, and a fresh immutable tag and asset set.

### Toward 1.0.0

Follow the repository version train rather than skipping maturity stages:

- 0.2.x AppKit product lane;
- 0.3.x GTK product lane;
- 0.4.x Qt 6 Widgets product lane;
- 0.5.x operational parity;
- 0.6.x migration and compatibility maturity;
- 0.7.x SDK and bounded extensibility;
- 0.8.x hardening;
- 0.9.x feature and contract freeze;
- 1.0.0 complete CLI JSON, human CLI, same-binary TUI, WinForms, AppKit, and
  GTK release with the support, signing, route, reconstruction, security,
  migration, and human evidence required by the release ledger.

Do not add new breadth ahead of the first accepted real route and observed C1
journey unless a measured blocker requires it.

## Resume checklist for ChatGPT or Codex

1. Read this handoff, `AGENTS.md`, `.aide/memory/project-state.md`,
   `docs/roadmap/current.md`, and `docs/release/VERSIONING.md`.
2. Run AIDE `task inspect`, `task noop-check`, Git policy/detect/plan, and
   `workspace_hygiene.py doctor --measure` before mutation.
3. Fetch and verify `main`, `dev`, tag `v0.1.0-alpha.1`, open PRs, and draft
   release asset identities.
4. Import the operator's notes without treating observations as acceptance.
5. Propose the smallest forward-only WorkUnit and version allocation supported
   by those notes.
6. Preserve the public-release, route, signing, support, and human gates unless
   their exact receipts and authority are present.
