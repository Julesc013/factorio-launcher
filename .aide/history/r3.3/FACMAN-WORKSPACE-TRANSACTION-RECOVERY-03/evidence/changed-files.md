# Changed Files

- `runtime/transaction/fl_transaction.{h,cpp}`: durable transaction records,
  validated state transitions, platform-specific atomic journal replacement,
  bounded recovery inspection/planning/application, explicit locking, and
  owned-staging cleanup.
- `runtime/factorio/application/flb_factorio_application.cpp` and
  `runtime/factorio/binding/flb_api.c`: canonical recovery descriptors,
  typed boundary decoding, dry-run refusal, and doctor reporting.
- `runtime/factorio/modsets/flb_factorio_modset_operations.cpp` and
  `runtime/factorio/saves/flb_factorio_save_operations.cpp`: journal coverage
  for the currently enabled multi-file writers named by the WorkUnit.
- `apps/cli/command_dispatch.cpp`: parser and renderer support for the three
  canonical workspace recovery commands; no recovery policy is implemented in
  the frontend.
- `contracts/**`, command goldens, and frontend metadata: recovery schemas,
  effects, success/refusal envelopes, canonical IDs, and four new refusal
  codes.
- `tests/test_recovery.py`, `tests/test_save_transfer.py`, and the native
  bridge smoke: state fault injection, idempotence, corruption, contention,
  missing/substituted staging, read-only failure ordering, and post-commit
  preservation proof.
- `tools/transaction_recovery_check.py` and strict-policy updates: mechanical
  enforcement of journal coverage and recovery route boundaries.
- `docs/architecture/workspace-transaction-recovery.v1.md`: state model,
  ownership, recovery decisions, and platform durability limits.
- `CMakeLists.txt` and AIDE task evidence: native target wiring and governed
  scope.

No public ABI layout, provider repository, external dependency, workflow,
release profile, setup mutation, diagnostic export, or launch-execution file
changed.
