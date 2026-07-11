# Universal Command Graph

The command graph is the shared model that every frontend calls. Its public ABI
remains an experimental correctness floor.

Canonical registry IDs in the authoritative preview slice:

```text
install_refs.scan
install_refs.import
install_refs.inspect
instance.create
launch_plan.build
launch_plan.preflight
run.preview
```

Frontend spellings such as `instances.list`, `diagnostics.report`, and
`launch.plan` are aliases. Frontend parsers normalize them to `instance.list`,
`diagnostics.run`, and `launch_plan.build` before registry invocation.

Each command declares:

- schema-versioned request payload
- schema-versioned response payload
- dry-run support
- audit behavior
- required capabilities
- secret redaction policy
- cancellation/progress behavior for long-running work

The command graph belongs to the universal launcher layer. The Factorio binding
implements product-specific handlers behind that model.

## Authoritative Vertical Slice

The native C ABI path now exists:

```text
runtime/client/fl_command_client_cabi_execute.c
  -> runtime/factorio/binding/flb_api.c
  -> ${FLAUNCH_UNIVERSAL_LAUNCHER_ROOT}/runtime/launcher/kernel/ulk_api.c
```

The Factorio binding handles product identity and statically registers real
handlers with its Universal Launcher context. Registered handlers take
precedence over generic kernel previews.

The first authoritative slice is:

```text
install_refs.scan
install_refs.import
install_refs.inspect
instance.create
launch_plan.build
launch_plan.preflight
run.preview
```

`runtime/factorio/application/` owns the typed Factorio operations. The CLI
constructs request JSON at the compatibility boundary, calls the direct client,
and renders the returned typed payload. It no longer owns persistence, launch
argument construction, or preflight behavior for these commands.

## CLI Route Proof

The CLI exposes a minimal smoke route over the same C ABI path:

```powershell
facman installs scan --path <root> --json
facman installs import <root> --id <id> --json
facman installs inspect <id> --json
facman instances create <name> --install <id> --json
facman launch-plan <instance> --json
facman launch-plan <instance> --preflight --json
facman run <instance> --json
```

These commands prove the direct route from CLI through ULK registration to the
Factorio application operation. Other command families remain migration work;
the completed slice must not move back into a frontend.

## Contract Files

Each locked command has a descriptor under `contracts/command/factorio/` and
golden success/refusal examples under `tests/golden/commands/`.

Validate them with:

```powershell
py -3 tools/command_contract_check.py
```
