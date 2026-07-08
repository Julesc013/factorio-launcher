# Directory Structure

Current durable layout:

```text
factorio-launcher/
  cmake/           native build policy and platform checks
  include/          public C ABI headers for usk, ulk, and flb
    usk/            universal setup kernel ABI
    ulk/            universal launcher kernel ABI
    flb/            Factorio launcher binding ABI

  src/              private native implementation boundaries
    base/           shared portable primitives
    platform/       common, windows, posix, macos, linux adapters
    usk/            setup kernel implementation
    ulk/            launcher kernel implementation
    factorio/       Factorio binding implementation

  apps/             native and platform frontend executables
    factorio_cli/
    factorio_tui/
    factorio_daemon/
    winforms/
    appkit/
    gtk/
    qt/

  data/             product templates, discovery rules, and policy
    factorio/
      product/
      discovery/
      launch_templates/
      instance_templates/
      policy/

  schemas/          versioned compatibility contracts
    common/
    usk/
    ulk/
    factorio/

  docs/             architecture, product, and platform documentation
  launcher/         current Python prototype/frontend compatibility package
  tests/            unit, integration, contract, golden, and fixture tests
  tools/            repo automation and validation tools
```

`launcher/` is transitional. It keeps the current runnable prototype alive while
the native command graph and C ABI are introduced. It should shrink over time
as native `include/`, `src/`, and `apps/` code reaches parity.

Factorio-specific manifests, policies, and launch templates live under
`data/factorio/` so the repo root does not pretend they are universal.
