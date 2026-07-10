# Distribution Contracts

`FACMAN-DISTRIBUTION-CONTRACT-02` defines package lanes before it builds real
release artifacts. The goal is to make portable, user-installed, and
system-installed FacMan layouts validate the same contract across Windows,
macOS, and Linux.

## Contract Files

- `release/index/release_index.v1.toml` lists the active contract set.
- `release/index/package_manifest.v1.toml` lists required paths and forbidden
  payload markers.
- `release/index/distribution_lanes.v1.toml` lists the first release lanes.
- `release/index/support_matrix.v1.toml` records support and proof levels.
- `release/profiles/*/profile.toml` binds one lane to package manifests,
  entrypoints, components, unsupported behavior, and support metadata.
- `release/packaging/common/*.toml` records shared component and app-mode
  expectations used by package profiles.

The first profile set is:

- `windows_portable_cli_x64`
- `windows_legacy_winforms_x64`
- `macos_legacy_appkit_x64`
- `linux_x11_gtk_x64`
- `portable_cli_x64`
- `portable_tui_x64`

`FACMAN-PACKAGE-SKELETON-02` turns those profiles into generated fixture
package trees. See [package_skeletons.md](package_skeletons.md).

## Required Package Surface

Every release profile must account for:

- required binaries
- required libraries
- `contracts/schema/`
- `content/factorio/`
- license files
- frontend command manifest
- package manifest
- support matrix
- entrypoints
- unsupported features and commands
- minimum OS/runtime floor

Profiles must use relative paths, must not bundle Factorio binaries, must not
store credentials, and must keep GUI toolkit requirements out of CLI/TUI-only
packages.

## Deferred Publication

These contracts do not claim package publication. The following remain
deferred until later release work:

- real installer generation
- signing and notarization
- package-manager publication
- auto-update
- Mod Portal networking
- Universal Setup mutation
- server/dev execution

The package can feel like one product to the user. Internally, each executable
remains a separate frontend over the shared command graph.
