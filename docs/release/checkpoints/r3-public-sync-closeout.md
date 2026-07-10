# R3 Public Sync Closeout Checkpoint

Date: July 11, 2026 AEST.

Purpose: finish the public integration checkpoint after sibling public merge by
locking exact dependency SHAs, adding workspace lock enforcement, and aligning CI
to the pinned repository layout before any public branch sync.

## Merged and Locked Revisions

| Repository | Branch | Revision |
| --- | --- | --- |
| `universal-launcher` | `main` | `eeac9ee2e6b90c393b8a18a562526c27889a1510` |
| `universal-setup` | `main` | `a777af1f930bded3e00ec27c769b841d3bf344b5` |
| `factorio-launcher` | `dev` | `cb6a0e3f197910fee5549020b6a5107ba354478d` |

## Structural Gates Added

- `release/index/dependency_lock.v1.toml`: replaced `BUILD_TIME` placeholders with
  exact public SHAs for `factorio_binding`, `universal_launcher`, and
  `universal_setup`.
- `release/index/build_manifest.v1.toml`: replaced `BUILD_TIME` placeholders with
  exact `source_commit` and explicit non-floating component versions.
- `release/index/workspace_lock.v1.toml` and
  `contracts/schema/release/workspace_lock.v1.schema.json`: introduced pinned
  workspace lock as first-class release data.
- `tools/validators/release/check_workspace_lock.py`: new validator enforcing:
  lock schema, required component ids, and 40-char pinned commits.
- `tools/validators/release/check_dependency_lock.py`: rejects `BUILD_TIME` in
  required fields and floating versions.
- `tools/release_contract_check.py` and
  `tools/validators/release/check_package_manifest.py`: include workspace lock in
  manifest + contract check graph.
- `tools/package_build.py`: package build info now uses pinned lock revisions so
  `source_revisions` cannot be `unknown`.
- `tools/verify_dependency_revisions.py`: reusable lock verification/alignment tool.

## CI Changes

- Added lock alignment/verification step in both Linux and Windows CI jobs via
  `tools/verify_dependency_revisions.py --align`.
- Added portable package build+smoke for `portable_cli_x64` and `portable_tui_x64`
  in the Linux-native lane.
- Added Windows legacy WinForms package build+runtime smoke in the WinForms lane.
- Pinned AppKit compile lane runner to `macos-13`.

## Evidence Notes

- `workspace_lock.v1` currently points to:
  - `factorio-launcher` at `2c2cce644b674d12227a194a77bce5a667fed721`
  - `universal-launcher` at `eeac9ee2e6b90c393b8a18a562526c27889a1510`
  - `universal-setup` at `a777af1f930bded3e00ec27c769b841d3bf344b5`
- `build` tooling and smoke evidence now treats these pins as authoritative and
  will fail fast on drift.
- `release/index/ release_index` and `package_manifest` were updated to carry the
  new workspace lock reference.

## Merge / Push Status

- `universal-launcher` and `universal-setup` were locally merged into `main`.
- `factorio-launcher` remains in task branch for final closeout commit and requires
  auth-allowed push to publish.
