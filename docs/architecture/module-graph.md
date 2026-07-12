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
  -> typed SetupGateway only for setup-authoritative operations

runtime/factorio/application/setup_gateway
  -> Universal Setup when FACMAN_WITH_SETUP is enabled
  -> unavailable typed results when setup support is disabled

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

Handlers never include or call Universal Setup directly. The gateway passes the
actual package target metadata and install-plan version/archive inputs to the
provider. A provider response that does not demonstrate evaluation of those
inputs is reported as unavailable, never relabeled as a FacMan plan.

Platform guarantees are selected explicitly. Secure randomness is implemented
by `BCryptGenRandom` on Windows, `getrandom` on Linux, and `arc4random_buf` on
macOS; unsupported targets fail configuration instead of falling through a
generic Unix branch. Durable operations return a `DurabilityLevel` so callers
can distinguish file-and-directory flush proof from a documented platform
limit.
