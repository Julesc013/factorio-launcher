# Package Skeletons

`FACMAN-PACKAGE-SKELETON-02` proves that release profiles can materialize
fixture package trees without building real artifacts.

The skeleton builder reads:

- `release/index/release_index.v1.toml`
- `release/index/package_manifest.v1.toml`
- `release/index/distribution_lanes.v1.toml`
- `release/index/support_matrix.v1.toml`
- `release/profiles/*/profile.toml`
- `release/packaging/common/*.toml`

It writes generated layouts under `build/package-skeletons/`, which is ignored
by Git. Each skeleton records:

- placeholder entrypoints and libraries
- `contracts/`
- `content/factorio/`
- `docs/`
- `licenses/`
- `release/`
- `manifest/package.v1.toml`
- `manifest/components.v1.toml`
- `manifest/skeleton.v1.json`

The skeleton marker sets:

```json
{
  "schema": "facman.package_skeleton.v1",
  "real_artifact": false,
  "purpose": "layout validation only"
}
```

## Proof Levels

| Level | Meaning |
| --- | --- |
| `contract-only` | Release/profile/package manifests validate, but no package tree exists. |
| `skeleton-layout` | A generated fixture package tree validates with placeholder files. |
| `built-artifact` | Real binaries/libraries are copied into a package layout. |
| `runtime-smoke` | The built package can run a command/result/refusal smoke. |
| `signed-published` | The package is signed/notarized/published for its lane. |

Current package status:

| Package lane | contract-only | skeleton-layout | built-artifact | runtime-smoke | signed-published |
| --- | --- | --- | --- | --- | --- |
| Windows WinForms | yes | yes | no | no | no |
| macOS AppKit | yes | yes | no | no | no |
| Linux GTK | yes | yes | no | no | no |
| Portable CLI | yes | yes | no | no | no |
| Portable TUI | yes | yes | no | no | no |

## Non-Goals

This milestone does not add:

- real installer generation
- Windows setup EXE or MSIX
- DMG or AppImage generation
- codesigning or notarization
- auto-update
- package publication
- Mod Portal networking
- Universal Setup mutation
- server/dev execution
- new GUI implementation
