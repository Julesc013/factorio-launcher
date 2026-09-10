# Git Helper Workflow

Q29 adds AIDE's first local merge, land, promote, sync, and prune helper layer.
It is a dry-run-first helper surface, not live branch automation.

## Safety Model

- `main` is canonical accepted truth.
- `dev` is shareable integration truth, not release truth.
- `task/*` and equivalent task branches land to `dev`.
- `dev` promotes to `main` only through explicit review gates.
- Prune requires ancestor containment proof.
- Protected roles are never pruned.
- Force push is forbidden.
- Remote push is explicit future operator intent and is not run in Q29.

The helper inspects repo root, current branch, dirty state, local and remote
branches, upstream status, branch roles, protected roles, ancestor containment,
ahead/behind state where available, missing policy files, and unpushed
protected branches where feasible.

## Commands

```powershell
py -3 .aide/scripts/aide_lite.py git plan
py -3 .aide/scripts/aide_lite.py git sync --dry-run
py -3 .aide/scripts/aide_lite.py git land --dry-run --target dev
py -3 .aide/scripts/aide_lite.py git promote --dry-run --from dev --to main
py -3 .aide/scripts/aide_lite.py git prune --dry-run
```

`git plan` writes:

- `.aide/git/latest-helper-plan.json`
- `.aide/git/latest-helper-plan.md`

## Landing

`git land` plans a task/subtask branch merge into the integration branch:

```text
git checkout <target>
git merge --no-ff <source> -m "<helper-generated compact_v1 message>"
```

It blocks dirty trees, protected source roles, unknown roles, missing target
branches, missing policy files, and missing validation evidence unless an
explicit validation acknowledgement is provided for fixture/operator-controlled
use.

## Promotion

`git promote` plans integration-to-canonical promotion:

```text
git checkout <target>
git merge --no-ff <source> -m "<helper-generated compact_v1 message>"
```

It requires an integration source, canonical target, clean tree, review
evidence, validation evidence, changelog preview posture, and an absolute
external `verified_protected_pr_merge_v1` receipt. The receipt binds each
first-parent task-to-dev merge to the exact repository, pull request, ordered
parents/tree, protected prior base, and hash-closed raw PR, protection, and
hosted-status observations. Candidate-checkout evidence is refused.

Use full-history checking by default. `--first-parent` is intentionally limited
to `dev -> main` and requires that receipt:

```powershell
py -3 .aide/scripts/aide_lite.py commit check --range main..dev --first-parent --merge-evidence C:\external\verified-protected-pr-merge.json
```

The one-time bridge also passes its external bootstrap receipt to `git promote`
or the same first-parent command with `--bootstrap-evidence`; it cannot be
used for a changed `main`/`dev` pair.

`git land --apply` does not trust `--validation-ok`: immediately before its
merge it runs the same complete `merge-base(target, source)..source` commit
range validation. This prevents malformed nested task history from entering
`dev` through a boolean acknowledgement.

`task-to-dev-promotion-check` is a hosted `pull_request_target` status for PRs
whose base is `dev`. It checks out protected base-branch code, fetches the PR
head and the exact current protected `main` commit as Git objects, and performs
the candidate-history check without executing candidate code. The checked set
is every commit reachable from the head except history already reachable from
the exact PR base or trusted `main` commit. The workflow binds that `main` OID
to both the live GitHub API response and fetched protected ref, so a task cannot
hide its own commits by supplying an arbitrary exclusion. Repository rulesets must separately require this exact status; the workflow file and any local
receipt do not enforce a ruleset by themselves.

The sole historical bridge is `dev_to_main_bootstrap_v1`: a short-lived,
external, PR-specific receipt for one exact `main`/`dev` topology. Before the
promotion merge, its raw promotion-PR observation must be open, non-draft and
unmerged at those exact base/head OIDs, and it must bind the current
independent approval and dev-to-main preflight observations. The task-to-dev
status does not apply to this dev-to-main PR. It records
old protection/status as `not_observed`, retains the exact retrospective
full-range malformed-commit debt, binds independent human authorization and
the status-rule activation frontier, and refuses changed refs, trees, PRs,
topology, debt, expiry, or reuse. It does not add a commit-policy baseline or
manufacture an old hosted status. Generation and authorization remain external;
the checker validates the supplied receipt.

Every externally retained GitHub observation is a
`facman.trusted_workflow_attestation.v1` asymmetric envelope. The checker has
only a pinned public verifier key; its signing key must remain in the separately
trusted hosted producer and is never available to a candidate checkout or local
promotion process. An unsigned JSON file, a self-declared provenance block, an
altered raw payload, a weak or unknown key, an expired receipt, or a replayed
receipt is refused. The signed payload binds purpose, repository name and ID,
actor, workflow path/ref/ID, admitted ref and commit, run/attempt/artifact IDs,
ruleset ID/version, URL, issue/expiry/unique ID, and canonical raw/artifact
digests. Duplicate unique IDs are rejected only within one supplied validation
packet; the trusted producer must retain and reject cross-packet reuse. The
initial activation receipt must be established outside the candidate: it binds
the exact public-key fingerprint and key ID, trusted producer workflow/ref,
private-key custody, and ruleset publisher binding. Key rotation must be signed
by the prior key or approved through an out-of-band trust root. A candidate-
embedded public key alone never establishes that trust. Installing the trusted
producer, its private signing material, and the ruleset workflow-publisher
binding remain external prerequisites.

When a task PR changes the workflow, AIDE Lite checker, either commit-message
policy, immutable baseline, promotion policy, merge-evidence schema, helper
policy, or branch-role/workflow enforcement inputs, the repository owner must
post exactly `/authorize-control-change <40-char-head-sha>`. The trusted
base-branch workflow re-queries the open PR, repository-owner numeric ID, every
changed-file page (including rename `previous_filename`), and every issue
comment page; it then re-reads the PR and comments immediately before it
publishes success. Commands by another actor or association, an old head, a
non-exact body, or an edited/deleted command fail. It never checks out or
executes candidate code. Ordinary source PRs do not require this extra
owner-command subgate.

`issue_comment` events only execute a workflow file already present on the
repository default branch. The workflow must therefore be deployed to `main`
and its `task-to-dev-control-change-authorization` publisher must be required
by a ruleset before owner commands can be relied upon. Source changes alone do
not activate that event path, and same-name third-party checks remain
insufficient without the ruleset publisher binding.

The publisher separately verifies `github.workflow_ref` and
`github.workflow_sha`: `pull_request_target` must use the protected `dev` ref
and exact live PR base SHA; `issue_comment` must use default `main` and its
current workflow SHA. In both cases the live PR receipt base/head remain exact.

The final exact-head `task-to-dev-promotion-check` is published only when the
repository variable `FACMAN_TASK_TO_DEV_REQUIRED_WORKFLOW_ID` names the
ruleset-bound workflow identity. An absent identity refuses admission. Setting
the variable is not a substitute for configuring the ruleset; that external
binding remains the trust anchor against a same-name GitHub Actions check.

The one-time bootstrap separately records a hash-closed default-branch
activation observation: the `main` workflow path, the exact blob OID resolved
from the bootstrap `main` commit, and the active trusted publisher. This deployment is a prerequisite for the bootstrap,
not evidence produced by the candidate PR; until it is separately completed,
the receipt refuses to claim that issue-comment authorization is active.

## Prune

`git prune` lists local branch prune eligibility. A branch is eligible only when
all of these are true:

- it is not the current branch;
- it is not canonical, integration, release, or deploy;
- it is a task-like branch role;
- containment is proven with `git merge-base --is-ancestor <branch> <target>`.

`--apply` deletes only eligible local branches with `git branch -d`. Q29 tests
that path only in temporary fixture repositories.

## Live AIDE Boundary

Q29 does not create `dev`, merge into `main`, push, delete, prune, promote,
call GitHub, install CI, publish releases, or call providers/models in the live
AIDE repository. Q30 is the phase that should decide how AIDE applies the
`dev`/`main` policy if appropriate.

## Portable Pack

Q31 exports the helper policy, helper command documentation, and dry-run helper
command implementation to target repos. It excludes source-generated
`latest-helper-plan.*` files, so every target repo must run `git plan` locally
and review the resulting target-specific plan before branch-sensitive work.
