# Module Graph

```text
include/flb
  -> runtime/factorio/binding
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

release/packaging
  -> runtime/package
  -> content/factorio
  -> contracts/schema
```

The Factorio repo interprets Factorio. Universal setup mutates install state;
universal launcher orchestrates product state and command graph behavior.
