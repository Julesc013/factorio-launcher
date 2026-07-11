# Changed Files

- `runtime/factorio/saves/flb_factorio_save_operations.{h,cpp}`: typed save
  listing, backup, clone, portable export, and import operations.
- `runtime/factorio/application/flb_factorio_application.cpp` and
  `runtime/factorio/binding/flb_api.c`: canonical registered routes, boundary
  decoding, typed dispatch, truthful effects, schemas, and dry-run behavior.
- `runtime/archive/fl_archive.{h}` and `fl_archive_reader.cpp`: optional
  extraction checkpoints used for deterministic interruption proof while
  preserving owned-staging cleanup.
- `apps/cli/command_dispatch.cpp`: alias normalization and rendering for the
  five migrated commands; legacy save parser and transfer backends removed.
- `contracts/**`, command goldens, and frontend metadata: canonical
  `instance.export` and `instance.import`, save-list/clone contracts, truth
  flags, refusals, and parity.
- WinForms and AppKit command metadata: canonical identifier reconciliation
  only; no GUI feature breadth.
- `tests/test_save_transfer.py`, existing CLI/redaction tests, and native
  bridge smoke: compressed saves, stable-handle and hardlink policy, hash
  closure, tamper/traversal refusal, dry-run, and fault-stage coverage.
- `tools/save_transfer_route_check.py` and strict-policy updates: mechanical
  prohibition of migrated CLI backend behavior.
- `docs/architecture/save-and-instance-transfer.v1.md`: truth, cross-volume,
  staging, and durability boundaries.
- `CMakeLists.txt` and AIDE task evidence: native target wiring and governed
  scope.

No public ABI, provider repository, external dependency, release profile,
workflow, setup mutation, or launch-execution file changed.
