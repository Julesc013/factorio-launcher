# Commit Discipline

Q27 defines AIDE's changelog-ready commit standard. New AIDE-managed queue work
uses:

```text
type(scope): summary
```

Subjects must be specific, 72 characters or fewer, and must not end with a
period. Substantive commits require these Markdown body sections:

- `## Summary`
- `## Why`
- `## Changed`
- `## Validation`
- `## Changelog`
- `## Risks`
- `## Follow-up`

Run:

```powershell
py -3 .aide/scripts/aide_lite.py commit check --latest
py -3 .aide/scripts/aide_lite.py commit check --range HEAD~5..HEAD
py -3 .aide/scripts/aide_lite.py commit template
```

The optional hook is installed only when explicitly requested:

```powershell
py -3 .aide/scripts/aide_lite.py commit install-hook
```

Q27 does not rewrite old commits. Q34 reports malformed history and consumes
the structured body categories and AIDE trailers through `changelog preview`,
`changelog validate`, and `changelog status` to produce preview-only release
drafts.

## Portable Pack

Q31 and later pack exports include this policy, `.aide/hooks/commit-msg`,
`.aide/git/commit-template.md`, the commit checker commands, changelog preview
support, and the related reference docs through `aide-lite-pack-v0`. Imported
target repos receive the hook template but do not get `.git/hooks/commit-msg`;
hook installation remains an explicit target-repo operator action.
