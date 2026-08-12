# Packaging Model

FacMan ships as one seamless user-visible package per platform, not as one
giant executable internally.

Each package contains replaceable modules and only the admitted executables:

- GUI frontend for the selected release profile
- `facman` terminal host for CLI JSON, bounded human CLI, and TUI
- TUI renderer/controller module linked into `facman`
- optional local service mode only after separate admission
- universal launcher kernel
- universal setup kernel or setup adapter
- Factorio binding
- `contracts/schema/`
- `content/factorio/`
- platform helpers

The package may feel like one app to the user. Internally, components stay
separate so they can be debugged, replaced, backported, or omitted in legacy
profiles.

## Windows

The canonical Windows artifact is a portable ZIP:

```text
FacMan-<version>-windows-x64-portable.zip
  bin/
    FacMan.WinForms.exe
    facman.exe
    ulk.dll
    usk.dll
    flb_factorio.dll
  content/
    factorio/
  contracts/
    schema/
  docs/
```

The installer is optional. The single EXE is only a bootstrapper and must
extract to a versioned `%LOCALAPPDATA%/FacMan/runtime/...` directory, never to
`%TEMP%` for normal execution.

## macOS

The bounded CLI package-preview lane is a target-specific Intel tarball:

```text
bin/facman
contracts/schema/
content/factorio/
manifest/
licenses/
```

It is proven separately from the GUI package model and does not imply AppKit
runtime, Apple Silicon, universal binary, signing, or notarization support.

The planned macOS GUI package is an `.app` bundle:

```text
FacMan.app/
  Contents/MacOS/
    FacMan
    facman
  Contents/Frameworks/
    libulk.dylib
    libusk.dylib
    libflb_factorio.dylib
  Contents/Resources/
    content/
      factorio/
    contracts/
      schema/
    docs/
```

Executables and dylibs do not live in `Contents/Resources`.

## Linux

Linux GUI packages are profile-specific. `linux_x11_gtk` packages the GTK
frontend, `linux_wayland_qt` packages the Qt frontend, and `portable_cli`
keeps old distro/server lanes free of GUI toolkit requirements.

## Manifests

Versioned package manifests live under `release/packaging/`. They declare
component names, source targets, package destinations, architecture, hashes,
signature policy, extraction policy, runtime search path, and license notices.

The distribution contract layer lives beside those manifests:

- `release/index/release_index.v1.toml`
- `release/index/package_manifest.v1.toml`
- `release/index/distribution_lanes.v1.toml`
- `release/index/support_matrix.v1.toml`
- `release/profiles/*/profile.toml`
- `release/packaging/common/*.toml`

This layer validates package lanes before real artifacts exist. It proves the
required binaries, libraries, contracts, content, licenses, frontend manifest,
package manifest, support matrix, entrypoints, unsupported behavior, and
minimum runtime floor are declared for each lane.

The first contract-backed lanes are historical inputs to the convergence:

- `windows_legacy_winforms_x64`
- `macos_legacy_appkit_x64`
- `linux_x11_gtk_x64`
- `portable_cli_x64`
- `portable_tui_x64`

The successor Technical Preview composition must map CLI and TUI entrypoints
to `facman` and reject a required `facman-tui` or `facmand` payload. Existing
profiles remain truthful until their implementation WorkUnit migrates them.

`tools/package_check.py` enforces the packaging rules.
`tools/package_layout_check.py` expands bundle layouts and rejects missing
contracts/content, duplicate destinations, forbidden payload markers, missing
license notices, and GUI toolkit leaks into CLI/TUI-only bundles.
`tools/package_manifest_check.py` validates the release index, profile TOML,
support matrix, frontend manifest, required paths, install modes, and package
manifest alignment.

See [../release/distribution_layout.md](../release/distribution_layout.md) for
the frontend/helper/library layout expected in each package family.

See [../product/install_distribution_modes.md](../product/install_distribution_modes.md)
for the portable, user-installed, and system-installed mode contract across
Windows, macOS, and Linux.

See [../release/distribution_contracts.md](../release/distribution_contracts.md)
for the `FACMAN-DISTRIBUTION-CONTRACT-02` profile contract.
