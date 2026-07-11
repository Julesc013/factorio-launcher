# Module graph

```text
apps/{cli,tui,daemon,gui}
  -> runtime/client
  -> public command and product-binding ABIs

runtime/client
  -> runtime/core
  -> runtime/package
  -> Universal Launcher client/kernel contracts

runtime/factorio/application
  -> runtime/factorio model modules
  -> runtime/workspace, transaction, archive, platform
  -> Universal Setup only for setup-authoritative operations

runtime/factorio/binding
  -> runtime/factorio/application
  -> include/flb public C ABI

release profiles
  -> CMake install components
  -> installed contracts, content, docs, licenses, runtime, and frontends
```

The enforced target aliases are documented in
`cmake-target-and-install-graph.v1.md`. The permanent ownership rule is:
Universal Setup mutates installed state, Universal Launcher orchestrates
product-neutral runnable state, FacMan interprets Factorio, and frontends only
present client operations.
