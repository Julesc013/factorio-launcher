# Changed Files

- `runtime/factorio/modsets/flb_factorio_modset_operations.{h,cpp}`: typed
  import, lock, verify, and export application operations.
- `runtime/factorio/mods/flb_factorio_mods.cpp`: production archive inspection
  and streamed hashing for compressed Factorio mod metadata.
- `runtime/factorio/application/flb_factorio_application.cpp` and
  `runtime/factorio/binding/flb_api.c`: typed boundary decoding and canonical
  registered descriptors.
- `apps/cli/command_dispatch.cpp`: alias normalization and rendering only for
  the migrated commands; duplicated backend behavior removed.
- `runtime/archive/fl_archive_platform.{h,cpp}`: owned, no-clobber staged-file
  commit with explicit uncertain-state reporting.
- `contracts/command/**`, `contracts/schema/factorio/**`, and
  `contracts/refusal/**`: truthful command, schema, effect, and refusal
  surfaces.
- `tests/**`: live route, deflate, adversarial archive, metadata drift,
  no-partial-copy, schema, and dry-run mutation proofs.
- `tools/**`: mechanical route ownership, contract count, frontend parity, and
  archive-boundary checks integrated into strict validation.
- `CMakeLists.txt`: archive/modset/application target wiring.
- `.aide/queue/FACMAN-MODSET-ARCHIVE-ROUTE-03/**`: scoped task and evidence.

No save, diagnostic, launch, release, external dependency, workflow, or public
ABI file changed.
