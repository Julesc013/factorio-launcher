# Changed files

## Execution boundary

- `runtime/platform/fl_process_supervisor.{h,cpp}` and platform implementations add the shared no-shell, bounded, cancellable process supervisor.
- `runtime/factorio/launch/flb_factorio_execution.{h,cpp}` adds the capability-scoped launch service and durable session journal.
- `runtime/factorio/application/application_configuration.{h,cpp}` freezes startup configuration.
- `runtime/factorio/application/command_admission.{h,cpp}` applies global effect/capability admission.
- `runtime/factorio/application/modules/launch_module.{h,cpp}` extracts the Play/launch application seam.
- The former client-private process implementations were removed; process transport now consumes the shared supervisor.

## Public contracts and product surfaces

- `run.execute` now truthfully declares workspace writes and process execution, while remaining unavailable for real Factorio.
- `facman play <instance>` is the preferred spelling; `facman run <instance> --execute` remains compatible.
- Capability/effect policy, launch-session schema, generated catalogs, completions, CLI/TUI/GUI metadata, and English strings were regenerated from canonical inputs.
- README, roadmap, master plan, product vision, execution architecture, safety ledger, and AIDE project state now record the completed fake-process foundation and the unstarted real-play gates.

## Verification and governance

- Native fake-process coverage, CLI/TUI compatibility tests, configuration snapshot tests, schema/policy tests, architecture validators, and fast/full developer entrypoints were extended.
- Historical closed AIDE tasks were compacted into `.aide/history/product-convergence-2026-07-20/`; the execution foundation remains the only current task until closeout.

No Factorio binary, network provider, credential provider, setup mutation, signing, publication, branch mutation, commit, or push was introduced.
