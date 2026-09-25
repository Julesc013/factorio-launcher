# World backup implementation slice

Base: `9361ada9c502f0ce65e75cd11a20c7837beb569c` (`origin/dev`).

- `runtime/factorio/saves/flb_factorio_save_operations.*`: pin the selected save,
  validate owned workspace destinations, preflight space, check source content
  and identity around staged publication, honor the production instance run
  lock, and record consistency metadata.
- `runtime/transaction/fl_transaction.*`: bind verified copies to an optional
  expected source object and support a partial-copy fault at the write boundary.
- `contracts/command/factorio/saves.backup.v1.toml` and
  `contracts/schema/factorio/factorio_save_backup.v1.schema.json`: describe the
  public destination argument and new optional receipt fields.
- Generated command catalogs, completions, localized command text, and target
  project state: generated from the changed command contract.
- `tests/native/fl_transaction_session_smoke.cpp` and
  `tests/test_save_transfer.py`: partial-copy cleanup, source substitution,
  process-loss recovery, owned destination, lock, and package-path tests.
- `docs/product/save_export.md`: document the reachable behavior and limits.

The queue item remains planned because the canonical plan permits four active
WorkUnits and already has four. Its allowed paths now include the required
generated projections.
