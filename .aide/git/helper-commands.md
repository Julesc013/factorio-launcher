# AIDE Git Helper Commands

Q29 adds local helper commands for branch-sensitive work. They are designed to
make the next safe action explicit without mutating live AIDE branches during
this phase.

## Default Safety

- All helper commands default to dry-run/report-only behavior.
- `--apply` is required before local Git mutation.
- Q29 validation never runs `--apply` in the live AIDE repository.
- `--push` is explicit and is not executed in Q29.
- Force push is forbidden.
- Protected roles are `canonical`, `integration`, `release`, and `deploy`.
- Prune eligibility requires `git merge-base --is-ancestor <branch> <target>`.

## Automatic Task-Branch Actions

Routine reversible development actions do not require human confirmation.
Creating a `task/*` branch is allowed when the WorkUnit exists in `ready` or
`active` state, its recorded exact base equals the requested base, the branch
is absent or already at that revision, the current worktree is clean, and no
protected ref changes. The same classification covers task worktrees, bounded
edits and checks, ordinary commits, non-protected task-branch pushes, and draft
pull-request creation or updates.

`--apply` remains an explicit command-intent flag for helpers; it is not a
repository-authority approval. Merge into `dev` or `main`, protected-ref
updates, published-history rewrites, release tags, signing, and publication
remain explicit repository authority. Credentials, Setup/foreign mutation,
permits, Factorio execution, observer capture, verdicts, and route promotion
remain separate product authority.

## Commands

```text
py -3 .aide/scripts/aide_lite.py git plan
py -3 .aide/scripts/aide_lite.py git commit-plan --classification <receipt.json> --message-file <commit-message.txt>
py -3 .aide/scripts/aide_lite.py git sync --dry-run
py -3 .aide/scripts/aide_lite.py git land --dry-run --target dev
py -3 .aide/scripts/aide_lite.py git promote --dry-run --from dev --to main --merge-evidence <absolute-external-receipt.json> [--bootstrap-evidence <absolute-external-bootstrap.json>]
py -3 .aide/scripts/aide_lite.py git task-to-dev-status --repository <owner/name> --pull-request <N> --base <OID> --head <OID> --output <absolute-external-status.json>
py -3 .aide/scripts/aide_lite.py git prune --dry-run
```

## `git plan`

Writes:

- `.aide/git/latest-helper-plan.json`
- `.aide/git/latest-helper-plan.md`

The plan includes current branch, role, dirty state, local/remote branch
summary, policy readiness, upstream status when available, recommended action,
warnings, blockers, and exact planned commands for helper operations.

For a dirty task or subtask branch, `git plan` points to `git commit-plan`
instead of requiring the edits to disappear. Dirty integration, canonical,
release, deploy, or unknown-role worktrees remain blocked for investigation.

## `git commit-plan`

Preparing a commit and preparing integration are separate operations.

Preparing a commit accepts a dirty task/subtask worktree only when one bounded
classification matches the current branch and HEAD, identifies every changed
path as `task_owned`, binds the exact content SHA-256 values, binds a
`compact_v1` message and Work-Item, and cites at least one exact passing review
receipt. The command is report-only. It returns `ready_to_stage` before staging
and `ready_to_commit` only when the index contains exactly the classified
snapshot with no remaining unstaged edits.

The classification uses this shape:

```json
{
  "schema_version": "aide.git-commit-classification.v1",
  "branch": "task/example",
  "base_commit": "<full HEAD>",
  "work_item": "FAC-123",
  "snapshot_sha256": "<SHA-256 of the canonical changed_paths array>",
  "message_sha256": "<SHA-256 of the exact message file bytes>",
  "changed_paths": [
    {
      "path": "relative/file",
      "state": "content",
      "sha256": "<SHA-256 of exact file bytes>",
      "git_blob_oid": "<Git object ID after clean filters>",
      "ownership": "task_owned"
    }
  ],
  "reviews": [
    {
      "path": "review.json",
      "sha256": "<SHA-256 of exact review receipt bytes>",
      "verdict": "PASS"
    }
  ]
}
```

The snapshot binds both the physical SHA-256 and the Git blob identity that
will enter the index after configured clean filters. Each review receipt uses
`aide.git-commit-review.v1` and binds the same branch, base commit, snapshot
SHA-256, message SHA-256, and an exact `PASS`, `PASSED`, `APPROVED`, or
`ACCEPTED` verdict. Relative
review paths resolve beside the classification. Classification, message, and
review inputs may live outside the checkout, but must be bounded regular files
and must not be symlinks.

An unclassified path, an unrelated staged path, changed bytes after review,
rename/copy status, or an unresolved conflict blocks the plan. The helper never
stages or commits files itself. Exact paths appear as structured `planned_argv`
arrays in the JSON report. The Markdown/console command uses a non-copyable
placeholder so shell metacharacters in legal Git paths cannot become commands.

Preparing integration starts after commit creation. `git land`, `git promote`,
and `git sync` retain their clean-worktree, validation, review, role, and
protected-ref requirements.

## `git sync`

Dry-run reports whether the current branch has an upstream and whether a
fast-forward-only pull would be the expected local sync action. It does not
fetch, pull, rebase, merge, or push unless a future operator explicitly uses
`--apply`; Q29 does not exercise that live path.

## `git land`

Dry-run validates task/subtask source role, integration target role, clean tree,
target existence, validation evidence or explicit validation acknowledgement,
and protected-branch rules. The planned local commands are:

```text
git checkout <target>
git merge --no-ff <source> -m "<helper-generated compact_v1 message>"
```

`--apply` is tested only in temporary fixture repositories.
Immediately before the merge, it validates every commit in
`merge-base(<target>, <source>)..<source>`; `--validation-ok` is not a
substitute for that check.

## `git promote`

Dry-run validates integration source role, canonical target role, clean tree,
review/validation evidence, changelog preview availability or recommendation,
protected-role semantics, and an absolute external
`verified_protected_pr_merge_v1` receipt. The planned local commands are:

```text
git checkout <target>
git merge --no-ff <source> -m "<helper-generated compact_v1 message>"
```

The helper emits a stable Conventional Commit subject and deterministic
`Work-Item` trailer derived from the operation and branch names. It does not
place branch text in the subject, so untrusted or overlong ref names cannot
make the resulting merge message invalid.

`--apply` is tested only in temporary fixture repositories.

`--first-parent` is not a general commit-check shortcut. It is reserved for
`dev -> main` and requires the same external receipt, whose hash-closed raw
PR, protection, and `task-to-dev-promotion-check` status records prove the
complete task PR range was checked. Evidence stored in the candidate checkout,
or duplicate/conflicting records, is refused.

For the one-time historical `dev -> main` bridge only, an external
`dev_to_main_bootstrap_v1` receipt may accompany that check. It binds exact
local and remote `main`/`dev` refs and trees, a promotion PR, short expiry,
ordered first-parent topology, raw PR observation, explicitly
`not_observed` historical protection/status, exact retrospective debt, an
independent human authorization, and the authenticated `dev` status-rule
activation frontier. It never turns historical failures into PASS or baseline
entries. Receipt generation remains an external human-review operation; this
helper only validates its required inputs and hashes.

## `git prune`

Dry-run lists local branches and reasons for eligibility or refusal. Protected
roles are never eligible. Task-like branches become eligible only after
ancestor containment in the integration or canonical target is proven.

`--apply` deletes local eligible branches with `git branch -d <branch>` only in
explicitly invoked contexts. Q29 tests this only in temporary fixture
repositories.

## Q29 Boundary

Q29 does not create AIDE `dev`, merge into `main`, update protected refs,
force-push, install CI, publish releases, or call providers/models. The later
automatic task-branch classification above does not weaken this historical
protected-branch boundary.
