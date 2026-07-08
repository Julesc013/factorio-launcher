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

## Current Native Bridge

The native C ABI path now exists:

```text
runtime/client/fl_command_client_cabi_execute.c
  -> runtime/factorio/binding/flb_api.c
  -> ${FLAUNCH_UNIVERSAL_LAUNCHER_ROOT}/runtime/launcher/kernel/ulk_api.c
```

The Factorio binding handles `product.inspect` and
`factorio.product.inspect` with FacMan product identity. Product-neutral
commands such as `command_graph.inspect`, `install_refs.list`,
`launch_plan.build`, and `diagnostics.report` are delegated to the universal
launcher kernel. Existing CLI workspace commands are still an early frontend
slice until their behavior is moved behind this command graph.

## CLI Route Proof

The CLI exposes a minimal smoke route over the same C ABI path:

```powershell
facman product inspect --json
facman command-graph inspect --json
facman diagnostics report --json
```

These commands prove that the native CLI can call the FacMan command client,
enter the Factorio binding, and delegate generic command graph behavior to the
universal launcher kernel. Workspace-mutating commands such as install import,
instance creation, and instance launch planning remain the next thinning target;
they should move from `apps/cli/` into runtime modules behind the command graph
instead of becoming permanent CLI-owned backend behavior.

## Contract Files

Each locked command has a descriptor under `contracts/command/factorio/` and
golden success/refusal examples under `tests/golden/commands/`.

Validate them with:

```powershell
py -3 tools/command_contract_check.py
```
