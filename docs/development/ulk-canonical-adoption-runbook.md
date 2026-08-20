# Canonical ULK ordering-repair adoption

This runbook adopts the Last Run ordering repair only after it is part of the
exact protected Universal Launcher `main` tip. It does not authorize a merge,
provider promotion, release, signing, or publication.

## Gate

Fetch ULK and invoke:

```text
python tools/ulk_canonical_adoption.py \
  --ulk-root <fresh-universal-launcher-clone> \
  --ulk-main-sha <exact-main-tip> \
  --ulk-tree <exact-main-tree> \
  --required-ref refs/heads/main \
  --evidence <external-empty-path>
```

The gate requires the exact canonical origin, exact `origin/main` tip and tree,
the #16 repair as an ancestor, a history-preserving merge commit, all four
merge-head CI jobs green on that SHA, unchanged public ABI 1.9, compatible SDK
package version 1.8.0, and both session contracts. It refuses the #16 task SHA,
an old or development-only SHA, the wrong tree, red or wrong-head CI, and any
already-mixed FacMan source/package identities.

## Atomic projection

After the gate passes, build the exact canonical ULK revision in source,
installed-static, installed-shared, relocated-static, and relocated-shared
modes on Linux, macOS, and Windows. Record the exact SDK identity, metadata,
inventory, ABI, and contract digests. Do not reuse task-SHA package evidence.

Update the complete `atomic_projection_set` from the gate record in one task
commit. The workspace lock, dependency lock, provider lock, SBOM, build and
frontend identity, CI checkouts, provider reconciliation constants, current
state, project status, tests, and generated truth must all name the same main
SHA/tree. The six ULK SDK package rows in `providers.lock.v2.toml` must come
from the new cross-platform build evidence; mechanically replacing their
source SHA while retaining old package digests is forbidden.

Regenerate metadata and state using the repository producers, then require:

```text
python tools/provider_pin_reconciliation.py
python tools/provider_conformance.py --help
python -m unittest tests.test_ulk_canonical_adoption
python -m unittest tests.test_provider_pin_reconciliation
python -m unittest tests.test_ulk_session_provider_adoption
python tools/strict_check.py
```

Search current-truth surfaces for the retired SHA and tree. Historical evidence
may retain them; active locks, workflows, validators, generated state, frontend
identity, candidate graph, and fixtures may not. Commit only after the complete
projection and all affected tests pass together.

## Requalification and invalidation

The adoption commit invalidates every pre-adoption package, route receipt,
obligation ledger, clean-host result, and human packet. Fetch FacMan `dev`,
forward-merge it if it advanced, update the dev-sync receipt, then rebuild at
least three packages from empty clones and rerun provider modes, 23 obligations,
clean-host execution, real Factorio 2.1.14, and the frozen human packet.
