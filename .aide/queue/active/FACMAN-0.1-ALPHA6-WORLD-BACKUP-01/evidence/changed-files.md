# World backup implementation slice

Base: `9361ada9c502f0ce65e75cd11a20c7837beb569c` (`origin/dev`).

- `runtime/factorio/saves/flb_factorio_save_operations.*`: pin the selected save,
  validate the owned source workspace and exact selected destination, preflight space, check source content
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
  process-loss recovery in an external selected directory, destination safety,
  lock, and package-path tests.
- `docs/product/save_export.md`: document the reachable behavior and limits.

The initial slice stayed planned because all four WorkUnit slots were occupied
at that time. Its allowed paths included the required generated projections.

## 2026-10-04 continuation

The original task branch and marker-owned root are reused from integrated dev
`6668ef2c55f0e59ed40782121b832878c71e40c9`. WorldBackup now occupies the fourth
active slot. Original acceptance clauses and historical failure evidence are
preserved.

- `tests/integration/facman_world_backup_low_space.py` adds the independently
  reviewed produced-CLI regression for real filesystem exhaustion, preservation
  and retry of the identical target after capacity recovery.
- `tests/integration/README.md` records caller custody, privilege, output,
  timeout and qualification requirements.
- The existing queue item moves from next to active through the lifecycle
  helper, retaining its historical files. New public evidence binds exact
  source, package, script, reviews, runtime receipts and cleanup observation.
- Canonical plan, queue index, target project state and generated human views
  record normal admission. This continuation changes no runtime engine,
  provider pin, workflow, protected control, release or product authority.
