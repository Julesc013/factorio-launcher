# Development workspace hygiene

FacMan development has one primary control checkout and one disposable
external development store per repository. Build output, package staging, distribution
assemblies, proof clones, and task worktrees must not form new ad-hoc roots in
the source tree or at a drive root.

## Canonical layout

`tools/development_layout.py` resolves the layout without machine-specific
source edits. Set `FACMAN_DEV_ROOT` to place the whole store on another disk.
Otherwise Windows uses `%LOCALAPPDATA%\FacMan\Development`, and Unix-like
systems use `$XDG_CACHE_HOME/facman/development` or `~/.cache`.

```text
<development-base>/
  repositories/<repository-name-and-path-key>/
    tasks/<task-or-branch-id>/
      .facman-development-root.v1.json
      native-smoke/
      packages/
      dist/
      evidence/
    worktrees/
      .facman-worktree-store.v1.json
      .records/<branch-and-hash>.json
      <task-or-branch-id>/
```

Each task root is bound to one repository and task identity by an ownership
marker. The worktree store and every managed worktree are separately bound to
the shared control checkout, canonical path, branch, and declared merge target.
Linked worktrees resolve repository identity through Git's common directory, so
they cannot create a second store merely because their checkout path differs.
Automated cleanup refuses an absent, invalid, or mismatched marker or record.
`tools/dev.py` and direct package defaults create and refresh task-root markers
automatically.

Windows task-directory names use a deterministic 24-character, digest-suffixed
slug so CMake and MSBuild descendants remain below legacy path limits. The
ownership marker retains the full task identity; shortening the directory name
does not merge task roots or weaken cleanup checks. During migration, the
reader also accepts the exact former 64-character slug for that same marker
identity so old owned caches can be retired safely; no other path is admitted.

The primary checkout is a clean control surface, normally on synchronized
`dev`. Use it for fetch, inspection, planning, worktree creation, hygiene,
accepted merges, and release observation. Perform task edits, builds, package
staging, and test evidence in a secondary worktree and its external task root.

Inspect the resolved paths before building:

```powershell
py -3 tools/workspace_hygiene.py paths
py -3 tools/workspace_hygiene.py doctor --measure
```

## Lifecycle and limits

- Use one task root per task branch or explicit `FACMAN_TASK_ID`.
- Keep at most two secondary worktrees and eight retained task roots per
  repository checkout.
- The default retained task-root budget is 20 GiB.
- Marker-owned task roots expire after seven days without use.
- Task roots belonging to registered active worktrees are retained regardless
  of age; linked or reparse-point roots are refused.
- A merged task worktree is removed after its pull request is accepted.
- A merged remote branch is deleted automatically by GitHub.
- At idle, local refs are `main`, `dev`, and any branch with active work.
- Release tags are immutable; proof labels do not become permanent tags.
- Release assets live on the GitHub release, not in long-lived local `dist`
  copies.

Cleanup is plan-first:

```powershell
py -3 tools/workspace_hygiene.py clean
py -3 tools/workspace_hygiene.py worktrees
```

Create secondary worktrees only through the bounded helper, after the normal
AIDE Git policy/detect/plan checks and operator approval:

```powershell
py -3 tools/workspace_hygiene.py worktree-add task/<work-item> --start origin/dev
```

Apply only after reviewing the JSON plan:

```powershell
py -3 tools/workspace_hygiene.py clean --apply
py -3 tools/workspace_hygiene.py worktrees --apply
```

The helper records a target-aware retirement contract: `task/*` targets
`origin/dev`, while `release/*` and `hotfix/*` target `origin/main`. An
`evidence/*` worktree requires an explicit `--target`. The worktree command
removes only a canonical marker-owned secondary worktree when it is clean and
unlocked, its branch equals its exact HEAD, that HEAD is reachable from the
declared target, GitHub records an exact-head merged pull request to that
target, and no open pull request uses the task branch as its base. It uses plain
`git worktree remove`; it does not force removal, prune unrelated records, or
delete a branch or remote ref. Detached worktrees require a separately governed
disposable receipt and are never adopted by this helper. `doctor` reports
in-checkout output roots, unmanaged worktrees, target-contained local task
branches, forbidden permanent branch prefixes, and non-release tags.

One canonical worktree created before store ownership was introduced can be
adopted explicitly after its path, branch, and target are reviewed:

```powershell
py -3 tools/workspace_hygiene.py worktree-register `
  --path <canonical-worktree-path> `
  --target origin/dev `
  --acknowledge-existing-unowned-store
```

## Legacy recovery

Old unmarked roots require an explicit path and containment root. The command
is dry-run by default and rejects top-level links or reparse points, source
checkouts, home directories, unrecognized names, and filesystem-root
allowlists unless the filesystem-root exception is separately present.
Contained links are inventoried and unlinked without traversing their targets.

```powershell
py -3 tools/workspace_hygiene.py legacy-clean `
  --allowed-root D:\Projects\Factorio `
  --path D:\Projects\Factorio\.facman-old-proof
```

Applying legacy deletion additionally requires both `--apply` and
`--acknowledge-unowned`. This mode exists for one-time migration only. New
output must carry an ownership marker. `legacy-prune` is the corresponding
plan-first tool for removing direct children of one reviewed legacy root while
retaining explicitly named children.

## CI and governance

Every uploaded CI artifact has an explicit retention period. Ordinary CI
evidence is short-lived; release assembly evidence may live longer but remains
bounded. Protected branch and tag rules remain the authority for `main`,
`dev`, and release tags. GitHub's delete-branch-on-merge setting owns routine
remote task-branch cleanup.

The hygiene command reports state and performs narrowly authorized cleanup; it
does not merge protected branches, retarget tags, publish releases, sign
artifacts, or invent human acceptance.
