# R3 Safety Package Proof Integration Checkpoint

Date: July 11, 2026 AEST.

Purpose: preserve the historical R3 proof while recording the later public
integration of its sibling dependencies, exact workspace lock, FacMan dev
landing, and remote clean-clone evidence.

## Merged and Locked Revisions

| Repository | Branch | Revision |
| --- | --- | --- |
| `universal-launcher` | `main` | `eeac9ee2e6b90c393b8a18a562526c27889a1510` |
| `universal-setup` | `main` | `a777af1f930bded3e00ec27c769b841d3bf344b5` |
| `factorio-launcher` | `dev` integration landing | `84269f9fcfddceee4e57daa5563e922ecf6a5e6c` |

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
- Pin the AppKit compile lane to the current x64 `macos-15-intel` runner so its
  macOS 10.13 deployment-target compile remains architecture-honest.

## Evidence Notes

- `workspace_lock.v1` currently points to:
  - `factorio-launcher` at `2c2cce644b674d12227a194a77bce5a667fed721`
  - `universal-launcher` at `eeac9ee2e6b90c393b8a18a562526c27889a1510`
  - `universal-setup` at `a777af1f930bded3e00ec27c769b841d3bf344b5`
- Build tooling and smoke evidence now treat these pins as authoritative and
  will fail fast on drift.
- `release/index/release_index.v1.toml` and the package manifest were updated to
  carry the new workspace lock reference.

## Public Merge / Push Status

- `universal-launcher/main` is public at
  `eeac9ee2e6b90c393b8a18a562526c27889a1510`; local and remote divergence is
  `0 0` after independent strict, Python, native-build, and CTest validation.
- `universal-setup/main` is public at
  `a777af1f930bded3e00ec27c769b841d3bf344b5`; local and remote divergence is
  `0 0` after independent strict, Python, native-build, and CTest validation.
- The R3 truth-hardening series is public on `factorio-launcher/dev` through
  integration commit `84269f9fcfddceee4e57daa5563e922ecf6a5e6c`.
- `factorio-launcher/main` remains the R2 local-alpha checkpoint and was not
  promoted by this closeout.

## Remote CI Sequence

The first FacMan run for integration commit `84269f9` started before the sibling
repositories were published:

- `schema-check` run `29122796064`: passed.
- `security-policy` run `29122796074`: passed.
- `ci` run `29122796099`, attempt 1: Linux and Windows failed at dependency
  alignment because clean clones still resolved Universal Launcher `99d0699`
  and Universal Setup `ef4da02`; no native or package step ran.

That failure is retained as evidence of the original public-ordering defect. It
must not be described as a product, native-build, or package-test failure. This
checkpoint correction is the first FacMan push after both locked sibling SHAs
became reachable from their public default branches. Its triggered CI run is the
authoritative clean-clone closeout; promotion remains blocked until that run is
terminal and green.

The next clean-clone run, `29123212167`, passed dependency alignment on Linux
and Windows. Its Linux job then exposed a separate native portability defect:
static C++ application objects linked into `libflb_factorio.so` had not been
compiled as position-independent code. GNU `ld` refused the shared link before
CTest, Python, or package steps. The repository now requires PIC for the common
native object model and the strict CI-proof validator prevents that setting from
silently disappearing.

The same run's Windows job passed dependency alignment, native configuration and
build, four CTests, WinForms build and command-client smoke, and 164 Python
tests. Its one failure compared the same temporary directory in Windows 8.3 and
long-name forms. The workspace configuration regression now compares the
canonical CMake path emitted by the implementation, retaining path-resolution
coverage without assuming one textual spelling for a Windows directory.

AppKit jobs in runs `29122796099`, `29123212167`, and `29123429975` remained
queued because GitHub retired the `macos-13` hosted image on December 4, 2025.
The compile-only legacy shell lane now uses the supported x64
`macos-15-intel` label; the CI-proof validator rejects reintroduction of the
retired label.

## Final Remote Clean-Clone Evidence

FacMan `dev` source revision
`c8357b237d3a7a12d42b5ac3c72b63e36848f1d9` completed its target matrix in
GitHub Actions run
[`29123649440`](https://github.com/Julesc013/factorio-launcher/actions/runs/29123649440):

- [`linux-native`](https://github.com/Julesc013/factorio-launcher/actions/runs/29123649440/job/86464253017):
  passed pinned dependency alignment, native build/CTest, Python/strict checks,
  and portable compatibility package smoke.
- [`windows-native-package`](https://github.com/Julesc013/factorio-launcher/actions/runs/29123649440/job/86464253095):
  passed pinned dependency alignment, native build/CTest, the 165-test suite,
  WinForms smoke, the zero-skip required package proof, and selected/legacy
  package smoke.
- [`appkit-compile`](https://github.com/Julesc013/factorio-launcher/actions/runs/29123649440/job/86464253142):
  passed the AppKit and command-client source compile on the supported Intel
  runner; the claim remains compile-only.

Security-policy run
[`29123649397`](https://github.com/Julesc013/factorio-launcher/actions/runs/29123649397)
also passed for the exact source revision.
The path-filtered schema workflow did not run for the final CI-only change;
schema validation remained part of the successful strict checks in the Linux
and Windows jobs.

## Selected Package Artifact

The clean synchronized source revision above produced:

```text
profile: windows_portable_cli_x64
archive: facman-0.1.0-dev.contract-windows-cli-x64-portable.zip
archive bytes: 590278
archive SHA-256: 8a60f66c5ff95663d1b604dd621ec70de104011e031849b63cb60f4be71fb9c3
files verified: 143
integrity: sha256_consistent
authenticity: not_proven_unsigned
published: false
```

The package build metadata records the same FacMan source revision plus
Universal Launcher `eeac9ee2e6b90c393b8a18a562526c27889a1510` and Universal
Setup `a777af1f930bded3e00ec27c769b841d3bf344b5`.

## Promotion Decision

- R3 public dependency integration and the selected-package reproducibility
  closeout pass on `dev`.
- `dev -> main` was not performed by this task. `main` remains the R2 comparison
  checkpoint pending a separate operator promotion decision.
- No tag, release, signature, publication, or Safe-beta status is created.

## Remaining Claims Blocked

- This is an integration checkpoint, not Safe-beta promotion.
- Real Factorio write isolation and execution remain unavailable.
- Setup mutation and general diagnostic export remain unavailable.
- The selected Windows package remains unsigned and unpublished; integrity does
  not prove publisher authenticity.
- macOS and Linux package artifacts remain outside the selected package claim.
