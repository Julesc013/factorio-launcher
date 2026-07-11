# Changed Files

- `runtime/factorio/diagnostics/flb_factorio_diagnostics.{h,cpp}`: anchored
  stable file reads, reviewed-format classification, path sanitization,
  structured reports, typed export results/refusals, production ZIP staging,
  transaction journaling, and post-commit audit.
- `runtime/factorio/application/flb_factorio_application.cpp` and
  `runtime/factorio/binding/flb_api.c`: canonical descriptor, boundary decode,
  typed dispatch, dry-run refusal, effects, and schema metadata.
- `apps/cli/command_dispatch.cpp`: authoritative export/doctor alias routing;
  the dormant hand-written ZIP and CLI collection backend were removed.
- `runtime/transaction/fl_transaction.cpp`: committed file-output recovery now
  cleans only recognized bound staging roots while preserving the target.
- `runtime/base/fl_sha256.{h,cpp}`: byte-buffer SHA-256 used for original and
  redacted content closure.
- Diagnostic command/schema/refusal/frontend contracts and goldens: typed
  result, manifest, stable-read report, omission report, effects, and six
  source-read refusal codes.
- `tests/test_diagnostic_export.py`, existing redaction/CLI tests, and native
  bridge smoke: no-clobber, hash closure, malformed formats, hardlinks,
  external links, every journal state, committed recovery, and graph parity.
- `tools/diagnostic_export_check.py` and strict checks: mechanical prohibition
  of the migrated CLI/legacy ZIP path and enforcement of platform handle,
  archive, journal, and self-verification anchors.
- Architecture, roadmap, README, AIDE truth, and claim ledger: enabled CLI
  scope and remaining GUI/shared-filesystem limits.

No Universal provider, public ABI layout, external dependency, workflow,
release profile, setup mutation, launch execution, signing, or publication
file changed.
