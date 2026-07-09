# Release

Owns package manifests and release profile definitions.

May contain:

- platform package manifests
- package layout declarations
- release/build profile descriptions
- release index contracts
- dependency locks and build manifests
- offline bundle contract descriptions

Must not contain:

- compiled output
- source implementation
- user state
- downloaded Factorio binaries

Generated artifacts belong in ignored roots such as `build/`, `dist/`, or
`out/`.

Primary docs:

- `docs/release/RELEASE_MODEL.md`
- `docs/release/DISTRIBUTION_MATRIX.md`
- `docs/release/INSTALL_MODES.md`
- `docs/release/VERSIONING.md`
- `docs/release/UPDATE_MODEL.md`
- `docs/release/PACKAGE_LAYOUT.md`
- `docs/release/OFFLINE_BUNDLES.md`
- `docs/release/SUPPORT_POLICY.md`
