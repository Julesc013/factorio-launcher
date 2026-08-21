# Contributing to FacMan

FacMan is a native Factorio product binding and frontend set. Universal Setup
owns installed-state mutation; Universal Launcher owns product-neutral command
orchestration. Do not move either responsibility into this repository.

Start with `docs/development/getting-started.md` and the relevant extension
guide. Keep public ABI in `include/flb/`, private implementation in `runtime/`,
frontend presentation in `apps/`, compatibility law in `contracts/`, and
release definitions in `release/`.

Use the canonical developer commands:

```powershell
py -3 tools/dev.py test --affected
py -3 tools/dev.py test --fast
py -3 tools/dev.py test --full
py -3 tools/dev.py verify-all
```

These commands default generated output to a stable per-user task root outside
the source checkout. Set `FACMAN_TASK_ROOT` or pass `--task-root` to select a
named WorkUnit root. In-tree output requires the explicit reviewed legacy
escape hatch `--allow-in-tree-output`.

Focused tests are iteration evidence, not promotion. Before a production claim
or closeout, run the full matrix and record any platform proof that remains
CI-owned or operator-owned. The full runner classifies every skip; promotion
requires zero `required_blocked` skips and zero unclassified skips. Automated
checks never pass human acceptance.

Commits use the FacMan compact profile layered over the imported AIDE policy.
Keep the subject outcome-oriented, add rationale only when it is non-obvious,
and identify the WorkUnit. Add `Evidence-Ref` only when durable proof exists.
The checker continues accepting published legacy structured messages and exact
immutable-baseline entries; new templates generate only the compact format.
See `docs/development/commit-and-review-profile.md`.

```powershell
py -3 .aide/scripts/aide_lite.py commit template
py -3 .aide/scripts/aide_lite.py commit check --message "..."
```

Example:

```text
docs(release): record Technical Preview handoff

Record the remaining blockers without granting product or release authority.

Work-Item: FACMAN-TECHNICAL-PREVIEW-OVERNIGHT-01
Evidence-Ref: docs/release/checkpoints/facman-technical-preview-overnight-01.md
```

Pull requests should remain decision-oriented: outcome, non-obvious rationale,
proof links, risk and authority delta, and review focus. GitHub Checks owns the
full job matrix; durable receipts own exact identities.

Do not commit Factorio binaries, credentials, `.aide.local/`, build output, raw
prompts, raw model responses, or provider secrets. Do not claim publisher
authenticity from unsigned hashes or provenance.
