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

