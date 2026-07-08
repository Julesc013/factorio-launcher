# Directory Structure

Current durable layout:

```text
factorio-launcher/
  cmake/           native build policy and platform checks
  include/          public C ABI headers for usk, ulk, and flb
    usk/            universal setup kernel ABI
    ulk/            universal launcher kernel ABI
    flb/            Factorio launcher binding ABI

  source/           single private implementation and app-source tree
    base/           shared portable primitives
    client/         frontend-neutral command client transports
    platform/       common, windows, posix, macos, linux adapters
    runtime/        package/runtime locator and component verification
    usk/            setup kernel implementation
    ulk/            launcher kernel implementation
    factorio/       Factorio binding implementation
    apps/           CLI, TUI, daemon, and GUI implementation files
    prototypes/
      python_launcher/ current Python prototype, not production runtime

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
    packaging/

  packaging/        versioned platform package manifests
    windows/
    macos/
    linux/
    portable/

  docs/             architecture, product, and platform documentation
  tests/            unit, integration, contract, golden, and fixture tests
  tools/            repo automation and validation tools
```

`source/` is the only implementation source root. Do not create nested `src/`
or `source/` directories under apps or modules. `apps/` contains frontend
package/project shells; implementation files live under `source/apps/`.
The closed root model is enforced by `tools/structure_policy_check.py`.

`source/prototypes/python_launcher/` is transitional. It keeps the current
runnable prototype alive while the native command graph and C ABI are
introduced. It is not bundled in Windows 7, macOS legacy, or Linux legacy
production artifacts. It should shrink over time as native `include/`,
`source/`, and `apps/` code reaches parity.

Factorio-specific manifests, policies, and launch templates live under
`data/factorio/` so the repo root does not pretend they are universal.

Durable AIDE-compatible policy inputs may live under `.aide/policies/`.
Generated AIDE snapshots, ledgers, reports, queue state, and local knowledge are
not source truth and stay ignored unless a future task explicitly promotes a
curated artifact.
