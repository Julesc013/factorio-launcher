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

The low-level builder accepts an explicit output root. Governed development and
release invocations must route that output to a marker-owned external task root
through `tools/dev.py` (tests may use their bounded temporary directory); its
historical in-checkout default is not a persistent-output allowance.
Persistent in-checkout `build`, `dist`, `out`, and `tmp` roots are forbidden.
Each skeleton records:

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

Current package status separates the unified product profiles from retained
legacy/laboratory producers. The exact alpha.5 candidate result is bound to
revision `a7a518dbfe2a6d54da7b9c84fbd318300265e31d`, tree
`1ebcd2b230ed188e021880ffa4c438de2ede655b`, run `33576140943` attempt 1; it does
not promote support or publication.

| Package lane | contract-only | skeleton-layout | built-artifact | runtime-smoke | signed-published |
| --- | --- | --- | --- | --- | --- |
| Windows product: WinForms .NET 4.8 + `facman` | yes | yes | exact candidate | exact-candidate machine-qualified | no |
| macOS Intel product: AppKit + `facman` | yes | yes | exact candidate | machine-qualified semantic preview | no |
| Ubuntu 24.04 x64 product: GTK3/X11 + `facman` | yes | yes | exact candidate | machine-qualified semantic preview | no |
| Legacy portable CLI | yes | yes | historical proof | historical proof | no |
| Legacy portable TUI | yes | yes | historical proof | historical proof | no |

## Non-Goals

Skeleton proof by itself does not add:

- MSIX, DMG, or AppImage generation
- codesigning or notarization
- auto-update
- package publication
- Mod Portal networking
- live managed Factorio-install acceptance
- server/dev execution
- new GUI implementation
