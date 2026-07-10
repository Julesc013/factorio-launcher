# Universal Command Graph

The command graph is the stable model that every frontend calls.

Locked native command names:

```text
product.inspect
doctor.run
installs.scan
installs.import
instances.create
launch.plan
run.preview
run.execute
modsets.lock
saves.backup
export.instance
import.instance
```

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
```

`runtime/factorio/application/` owns the typed Factorio operations. The CLI
constructs request JSON at the compatibility boundary, calls the direct client,
and renders the returned typed payload. It no longer owns persistence or launch
construction for these commands.

## CLI Route Proof

The CLI exposes a minimal smoke route over the same C ABI path:

```powershell
facman installs scan --path <root> --json
facman installs import <root> --id <id> --json
facman installs inspect <id> --json
facman instances create <name> --install <id> --json
facman launch-plan <instance> --json
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
