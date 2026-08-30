# Development workspace hygiene

FacMan development has one source checkout and one disposable external
development store per checkout. Build output, package staging, distribution
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
    worktrees/<task-or-branch-id>/
```

Each task root is bound to one repository and task identity by an ownership
marker. Recursive automated cleanup refuses an absent, invalid, or mismatched
marker. `tools/dev.py` and direct package defaults create and refresh this
marker automatically.

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

The worktree command removes only a clean secondary worktree beneath the
canonical external worktree store whose exact HEAD is already contained in
`origin/main`. It never deletes a branch or remote ref. `doctor` reports
in-checkout output roots, unmanaged worktrees, merged local task branches,
forbidden permanent branch prefixes, and non-release tags.

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
