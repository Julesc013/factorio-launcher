# Directory Structure

This repository is now product-only. It owns the Factorio binding, Factorio
content/contracts, app frontends, and release manifests. It does not own the
universal setup or universal launcher kernels.

```text
factorio-launcher/
  include/
    flb/              Factorio binding public C ABI only

  runtime/
    base/             small private support primitives
    package/          runtime locator, component manifest, extraction, verify
    client/           frontend-neutral command clients and transports
    factorio/         Factorio binding implementation
    platform/         common, windows, posix, macos, linux adapters

  apps/
    cli/              native console CLI frontend
    tui/              native TUI frontend
    daemon/           daemon / job runner frontend
    gui/
      win32/          Windows provider; WinForms .NET Framework 4.8 shell
      appkit/         macOS AppKit frontend
      gtk/            Linux GTK frontend
      qt/             optional Linux Qt frontend
    python_cli/       transitional prototype, not production runtime

  content/
    factorio/         product manifest, discovery rules, templates, policy

  contracts/
    abi/              ABI policy and notes
    command/          command graph contract notes
    diagnostic/       diagnostic contract notes
    policy/           repository/product policy contracts
    result/           result contract notes
    refusal/          refusal contract notes
    schema/           versioned JSON schemas

  release/
    packaging/        platform package manifests
    profiles/         release/build profile definitions

  docs/               architecture, product, platform, planning docs
  tests/              unit, contract, integration, fixtures, golden proof
  tools/              validators and repository automation
  cmake/              native build policy
  external/           optional third-party dependencies
  archive/            optional historical retained material
```

Retired roots are blocked by `tools/structure_policy_check.py`:

```text
source/
src/
data/
schemas/
packaging/
launcher/
product/
universal/
```

Universal setup and universal launcher are consumed as sibling repositories in
the early CMake split. Their public ABI headers and implementations live in:

```text
../universal-setup/include/usk/
../universal-setup/runtime/setup/

../universal-launcher/include/ulk/
../universal-launcher/runtime/launcher/
```

The transitional Python CLI remains under `apps/python_cli/` only so current
read-only discovery and command-shape tests keep running while the native
command graph catches up. Production packages must not depend on Python.

GUI frontends are grouped below `apps/gui/` so `apps/` stays organized by
frontend class first and provider/toolkit second. `win32` is the architecture
label for the Windows GUI provider; the concrete legacy-compatible shell can
remain WinForms.
