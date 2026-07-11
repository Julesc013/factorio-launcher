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
    factorio/         Factorio binding implementation by product domain
    platform/         common, windows, posix, macos, linux adapters

  apps/
    cli/              native console CLI frontend
    tui/              native TUI frontend
    daemon/           daemon / job runner frontend
    gui/
      windows/
        winforms/     Windows legacy .NET Framework 4.8 shell
        winui/        Windows modern WinUI shell
      macos/
        appkit/       macOS legacy AppKit frontend
        swiftui/      macOS modern SwiftUI frontend
      linux/
        gtk/          Linux X11 GTK frontend
        qt/           Linux Wayland Qt frontend

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
    profiles/         target-specific release/build profile definitions

  LICENSES/           REUSE and packaged dependency license texts
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

Universal setup and universal launcher are consumed as separate workspace
repositories. A common local workspace layout keeps them outside the Factorio
folder:

```text
<workspace>/Universal/universal-setup/include/usk/
<workspace>/Universal/universal-setup/runtime/setup/

<workspace>/Universal/universal-launcher/include/ulk/
<workspace>/Universal/universal-launcher/runtime/launcher/
```

CMake and cross-repo checks use a portable locator:

1. explicit CMake cache or environment variables:
   `FLAUNCH_UNIVERSAL_SETUP_ROOT` and `FLAUNCH_UNIVERSAL_LAUNCHER_ROOT`
2. shared roots: `FLAUNCH_UNIVERSAL_ROOT` or `FLAUNCH_WORKSPACE_ROOT`
3. pinned local checkouts under `external/universal-*`
4. common relative layouts such as `../universal-*`,
   `../../Universal/universal-*`, and nearby workspace parents

This keeps long-lived checkouts, forks, branches, and contributor machines from
needing source edits just because repositories are arranged differently.

Python has no product app root. It may be used under `tools/` and `tests/`
for validators, fixture helpers, and automation, but FacMan runtime entrypoints
must be native.

Runtime domain folders must not be named after language standards. `c11/`,
`cpp11/`, `c17/`, and similar buckets are retired; implementation belongs under
the Factorio domain it serves, such as `install_validation/`, `modsets/`, or
`mod_portal/`.

GUI frontends are grouped below `apps/gui/<os>/<toolkit>/` so multiple
toolkits can coexist on the same operating system without making `apps/` a
provider junk drawer. Distributions may bundle multiple frontend executables,
but each executable remains a thin command client over the shared backend.
