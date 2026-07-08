# AIDE Commit Message Standard

Q27 makes AIDE commits changelog-ready and easier to audit without replaying
chat history. The first line uses Conventional Commits:

```text
type(scope): summary
```

The subject must be specific, no longer than 72 characters, and must not end in
a period. Vague placeholders such as `update`, `changes`, `misc`, or `wip` fail
the checker.

## Structured Markdown Body

Every substantive AIDE commit must include these headings:

- `## Summary`
- `## Why`
- `## Changed`
- `## Validation`
- `## Changelog`
- `## Risks`
- `## Follow-up`

Each section should contain bullet content. The validation section must include
one of `PASS`, `WARN`, `FAIL`, or `NOT RUN`.

## Changelog Categories

The `## Changelog` section uses machine-readable category prefixes:

- Added
- Changed
- Fixed
- Removed
- Deprecated
- Security
- Docs
- Tests
- Internal
- Risks
- Follow-up

Future automated changelog and release-note tooling consumes these prefixes.
Existing history is not rewritten; malformed commits are reported.

## Trailers

AIDE queue commits should include:

- `AIDE-Task`
- `AIDE-Phase`
- `AIDE-Result`
- `AIDE-Scope`
- `AIDE-Token-Impact`
- `AIDE-Quality-Gate`

## Examples

Good:

```text
policy(aide): define structured commit recovery

## Summary

- Add policy for changelog-ready commits.

## Why

- Future agents need release history without reading full chat context.

## Changed

- Added commit-message policy.

## Validation

- `py -3 .aide/scripts/aide_lite.py commit check --latest`: PASS.

## Changelog

- Added: structured commit discipline for AIDE queue work.

## Risks

- Existing old commits remain malformed and are reported.

## Follow-up

- Use range checks before promotion.

AIDE-Task: Q27-commit-discipline-workunit-recovery-v0
AIDE-Phase: Q27
AIDE-Result: PASS
AIDE-Scope: policy
AIDE-Token-Impact: lower-history-reconstruction-cost
AIDE-Quality-Gate: commit-check-pass
```

Weak:

```text
update
```

## Commands

- Check a message file: `py -3 .aide/scripts/aide_lite.py commit check --message-file .git/COMMIT_EDITMSG`
- Check latest commit: `py -3 .aide/scripts/aide_lite.py commit check --latest`
- Check a range: `py -3 .aide/scripts/aide_lite.py commit check --range HEAD~5..HEAD`
- Print template: `py -3 .aide/scripts/aide_lite.py commit template`
- Install local hook: `py -3 .aide/scripts/aide_lite.py commit install-hook`

Hook installation configures `core.hooksPath=.aide/hooks` only when explicitly
run. Q27 does not write `.git/hooks` automatically.
