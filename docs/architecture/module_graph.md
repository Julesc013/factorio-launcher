# Module Graph (legacy path)

The current module graph is [`module-graph.md`](module-graph.md). This legacy
underscore path remains only as a documentation compatibility redirect.

## Historical sketch

```text
include/flb
  -> runtime/factorio/binding
  -> runtime/factorio/application
  -> runtime/factorio/discovery
  -> runtime/factorio/launch
  -> runtime/factorio/mods
  -> runtime/factorio/mod_portal
  -> runtime/factorio/saves
  -> runtime/factorio/server
  -> runtime/factorio/diagnostics

apps/{cli,tui,daemon,gui}
  -> runtime/client
  -> ${FLAUNCH_UNIVERSAL_LAUNCHER_ROOT}
  -> runtime/factorio/binding
  -> registered runtime/factorio/application handlers

release/packaging
  -> runtime/package
  -> content/factorio
  -> contracts/schema
```

The Factorio repo interprets Factorio. Universal setup mutates install state;
universal launcher orchestrates product state and command graph behavior.
