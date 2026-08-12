# Commit and review profile

FacMan applies a small project-owned commit profile after the imported AIDE
Lite policy. The imported policy, immutable commit baseline, protected branch
rules, hosted checks, product boundaries, and release authorities remain
unchanged. New work uses `compact_v1`; existing seven-section messages remain
accepted as `legacy_structured_v0` and are not rewritten.

## Information ownership

| Surface | Canonical content |
| --- | --- |
| Commit | Outcome, non-obvious rationale, WorkUnit, and optional evidence reference |
| Pull request | Review decision, risk, authority delta, proof links, and review focus |
| GitHub Checks | Exact jobs, platforms, commands, logs, and conclusions |
| Evidence receipt | Exact commits, trees, runs, digests, and authority state |
| WorkUnit | Scope, status, dependencies, blockers, and next actions |
| Changelog | One user-facing change statement when a release note is warranted |
| Release record | Exact source and artifact identity, qualification, and publication authority |

Do not copy full CI matrices, file inventories, authority matrices, or operator
handoffs into commits. Link the durable authority instead.

## Compact commits

Use Conventional Commits with a lowercase kebab-case scope:

```text
type(scope): outcome
```

Generated types are `feat`, `fix`, `refactor`, `perf`, `test`, `docs`,
`build`, `ci`, `security`, `release`, `revert`, and `chore`. Existing imported
types remain accepted for compatibility. A new well-formed project scope warns
until it is added to the recommended scope list; it does not fail solely for
being new.

The subject has a 72-character soft target and a 100-character hard limit. It
must be specific and must not end in a period. Compact rationale is adaptive:
zero to 12 nonblank lines is normal, 13 to 30 warns, and more than 30 fails.
Markdown H2 headings (`##`) are forbidden in compact bodies. Put longer design
decisions in an ADR, review packet, or checkpoint and reference it.

Every managed commit names its WorkUnit. `Evidence-Ref` is added only when a
durable receipt exists:

```text
fix(winforms): reject mismatched backend responses

Treat post-dispatch identity mismatches as outcome unknown so the UI
cannot manufacture success after an ambiguous backend result.

Work-Item: FACMAN-WINFORMS-C1-TRANSPORT-HARDENING-01
Evidence-Ref: .aide/evidence/FACMAN-WINFORMS-C1-TRANSPORT-HARDENING-01.json
```

The optional release note trailer is a single categorized sentence:

```text
Changelog: Fixed: Reject mismatched backend responses
```

Changelog preview uses that trailer first, falls back to a legacy
`## Changelog` section, and otherwise emits no release note. Standard Git
trailers (`Fixes`, `Refs`, `Backport-Of`, `Co-authored-by`, and
`Signed-off-by`) remain accepted. `AIDE-Task` is accepted as a `Work-Item`
alias, but the FacMan template no longer generates the other AIDE result and
quality trailers because their canonical evidence lives elsewhere.

Run:

```powershell
py -3 .aide/scripts/aide_lite.py commit template
py -3 .aide/scripts/aide_lite.py commit check --message-file <path>
py -3 .aide/scripts/aide_lite.py commit check --range <base>..HEAD
py -3 .aide/scripts/aide_lite.py changelog preview --range <base>..HEAD
```

The checker reports `compact_v1`, `legacy_structured_v0`, or
`immutable_baseline`. The baseline is matched before either message format and
remains exact and immutable.

## Compact pull requests

Keep the visible PR body to outcome, why, proof, risk and authority, and the
one to three decisions needing review. GitHub Checks owns the complete job
list. Say `Authority delta: none` when authority did not change; enumerate only
actual changes. Put exact identities and extended evidence in a durable receipt
or the collapsed details section.

## Branch and merge flow

The current flow remains `task/* -> dev -> main`: one bounded WorkUnit per task
branch, based on an exact reviewed `dev` commit, with stack depth no greater
than three. Stack only dependent work. Do not add a closeout branch merely to
repeat another branch's proof.

Choose merge methods deliberately:

| Change | Method |
| --- | --- |
| One WorkUnit with checkpoint commits | Squash |
| Curated independently valid commits | Rebase merge |
| `dev` to `main` promotion | Merge commit |
| Provider or release train whose topology matters | Merge commit |
| Hotfix or backmerge | Merge commit or explicit cherry-pick |
| Unpublished local cleanup | Interactive rebase |

Branch deletion must use the PR source head, recorded merge method, canonical
integration commit, and unmatched-commit check. Ancestry alone is insufficient
after squash or rebase integration.

Branch hygiene (`FACMAN-BRANCH-HYGIENE-V1-01`), aggregate CI-gate compaction
(`FACMAN-CI-GATE-COMPACTION-V1-01`), and reconsidering the `dev` topology
(`FACMAN-FLOW-REASSESSMENT-V1-01`) are separate WorkUnits. They must not be
folded into a compact-history change. This profile grants no product execution,
Setup mutation, provider pin, protected-ref, signing, publication, or release
authority.
