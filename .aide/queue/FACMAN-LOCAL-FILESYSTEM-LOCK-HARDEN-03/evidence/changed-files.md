# Changed Files

- `runtime/base/fl_local_operation_lock.*`: cross-platform stable-handle lock,
  identity, local-filesystem classification, and exact-object removal.
- `runtime/factorio/launch/flb_factorio_launch_plan.*`: run-lock handle and
  identity lifetime, safe stale recovery, and substitution-aware release.
- `runtime/transaction/fl_transaction.cpp`: recovery apply uses the same
  stable lock and structured identity-drift refusal.
- `tests/` and `tools/local_lock_check.py`: hardlink, contention, stale,
  hostile replacement, renamed-parent, recovery-link, and mechanical proofs.
- `CMakeLists.txt`, docs, claim ledger, roadmap, and AIDE state: build wiring
  and bounded local-filesystem truth.

No provider, ABI header, release profile, workflow, dependency, or quarantined
execution capability changed.
