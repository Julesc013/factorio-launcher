# AGENTS.md

<!-- AIDE-PORTABLE:BEGIN section=aide-lite-pack-v0 mode=managed -->
## AIDE Lite Portable Guidance

- This repository uses a portable AIDE Lite Pack imported from AIDE.
- Keep target-specific project state in `.aide/memory/`; do not copy source AIDE memory.
- Do not copy source `.aide/queue/`, generated context, reports, route decisions, cache-key reports, Gateway/provider status reports, `.aide.local/`, raw prompts, raw responses, or secrets.
- Generate target-local context with `py -3 .aide/scripts/aide_lite.py snapshot`, `index`, `context`, and `pack`.
- Use `py -3 .aide/scripts/aide_lite.py test` for portable AIDE Lite validation.
- Use `commit check`, `commit template`, and `changelog preview` for Q27-style structured commits.
- Use `task inspect`, `task noop-check`, and `task recover` before repeated or out-of-order work.
- Use `git policy`, `git detect`, and `git plan` before branch-sensitive work; do not mutate branches without explicit helper plan, validation evidence, and operator approval.
- Use `github advisory` and `github validate` for report-only GitHub/CI planning; do not install workflows or mutate GitHub settings without a later reviewed target item.
- Provider/model/network calls and Gateway forwarding remain forbidden unless a future reviewed target queue item enables them.
<!-- AIDE-PORTABLE:END section=aide-lite-pack-v0 -->

## FacMan commit and review profile

FacMan loads `.aide/policies/facman-commit-messages.yaml` after the imported
policy. Generate `compact_v1` commits with the FacMan template: a clear
Conventional Commit subject, optional non-obvious rationale, `Work-Item`, and
conditional `Evidence-Ref`. Do not generate Markdown H2 sections or the old
AIDE result/phase/quality trailers. The checker still accepts
`legacy_structured_v0` and exact immutable-baseline commits; never rewrite
published history to migrate formats.

Keep pull requests decision-oriented and link GitHub Checks and durable
receipts instead of copying their full contents. Follow
`docs/development/commit-and-review-profile.md` for line limits, changelog
trailers, branch flow, and merge-method selection.
