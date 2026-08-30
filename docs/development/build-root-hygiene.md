# Build root hygiene

New local builds for FacMan, Universal Launcher, and Universal Setup must use a
marker-owned out-of-tree root:

```text
<FACMAN_DEV_ROOT>/repositories/<repository-key>/tasks/<task-id>/
```

`py -3 tools/dev.py ...` enforces this by default. Without an explicit
`FACMAN_TASK_ROOT` or `--task-root`, it derives a repository- and branch-scoped
external root. Windows uses `%LOCALAPPDATA%\FacMan\Development`; other
platforms use the configured cache root. `FACMAN_DEV_ROOT` moves the complete
development store to another disk. `--build-root`, `--out`, and `--dist`
remain available, but an in-checkout path is refused unless the reviewed
legacy-only `--allow-in-tree-output` switch is present.

Keep source checkouts beneath `D:\Projects` free of generated `build/`, package,
distribution, and proof output. A WorkUnit may use multiple children beneath
its task root, for example:

```text
<task-root>/ulk-build
<task-root>/facman-consumer-build
<task-root>/artifacts
```

Before removing an old in-repository build root:

1. Resolve and compare its exact absolute path.
2. Confirm the parent is the intended Git repository.
3. Confirm Git ignores the root.
4. Reject reparse points and links.
5. Record file count, byte total, and repository revision.
6. Remove or recycle only the exact root.
7. Verify the root is absent and the source repository remains clean.

Historical checkpoint commands may preserve their original in-repository paths
as evidence. They are not current build-location guidance.

Use `py -3 tools/workspace_hygiene.py paths` to see the exact current layout,
and follow [Development workspace hygiene](workspace-hygiene.md) for quotas,
retention, worktrees, legacy cleanup, and GitHub ownership.
