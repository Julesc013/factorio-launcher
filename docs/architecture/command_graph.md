# Universal Command Graph

The command graph is the stable model that every frontend calls.

Initial command names:

```text
product.inspect
doctor.run
doctor.instance
doctor.install
installs.scan
installs.list
installs.inspect
installs.import
instances.create
instances.clone
instances.list
instances.inspect
launch.plan
launch.run
mods.import
modsets.lock
saves.backup
servers.start
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
  -> ../universal-launcher/runtime/launcher/kernel/ulk_api.c
```

The Factorio binding handles `product.inspect` and
`factorio.product.inspect` with FacMan product identity. Product-neutral
commands such as `command_graph.inspect`, `install_refs.list`,
`launch_plan.build`, and `diagnostics.report` are delegated to the universal
launcher kernel. Existing CLI workspace commands are still an early frontend
slice until their behavior is moved behind this command graph.
