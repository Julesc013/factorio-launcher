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

Focused tests are iteration evidence, not promotion. Before a production claim
or closeout, run the full matrix and record any platform proof that remains
CI-owned or operator-owned. Automated checks never pass human acceptance.

Commits use the repository AIDE template and check:

```powershell
py -3 .aide/scripts/aide_lite.py commit template
py -3 .aide/scripts/aide_lite.py commit check --message "..."
```

Do not commit Factorio binaries, credentials, `.aide.local/`, build output, raw
prompts, raw model responses, or provider secrets. Do not claim publisher
authenticity from unsigned hashes or provenance.
