# macOS Native CLI Package Proof v1

`macos_portable_cli_x64` is a target-specific package-preview lane. It proves
one CLI-only FacMan package on GitHub's explicit `macos-15-intel` runner with
`CMAKE_OSX_DEPLOYMENT_TARGET=13.0`. It is not an Apple Silicon, universal
binary, broader macOS-version, or AppKit runtime claim.

## Package identity

- Artifact: `facman-<version>-macos-cli-x64-portable.tar.gz`.
- Entrypoint: `bin/facman`.
- Product payload: CLI, contracts, Factorio content, manifests, licenses, and
  minimal package documentation.
- Excluded breadth: `.app` bundle, TUI, daemon, GUI, shared project libraries,
  Factorio binaries, Python runtime, AIDE state, credentials, and setup
  mutation.

The package records exact FacMan, Universal Launcher, and Universal Setup
revisions; the CMake generator; compiler, linker, SDK, runner, architecture,
operating-system identity; and the exact deployment target. SPDX and adjacent
unsigned provenance bind the same source, dependency, manifest, artifact, and
CI identities without claiming publisher authenticity.

## Mach-O and integrity proof

The target build requires exactly one `x86_64` Mach-O architecture. `otool`
records the build-version deployment target and system dynamic dependencies.
The proof refuses `LC_RPATH`, deployment-target drift, an unexpected
architecture, and any dependency outside `/usr/lib` or
`/System/Library/Frameworks`.

Hash and component closure rejects missing, changed, extra, linked,
wrong-target, wrong-architecture, and incomplete payloads. Runtime smoke covers
spaces, Unicode, arbitrary working directories, empty `PATH`, renamed roots,
an external workspace, a read-only package tree, safe archive extraction, and
post-extraction execution with zero required skips.

## CI and authority boundary

The `macos-native-cli` job builds the complete native core, runs all CTests,
the portable Python suite, strict policy checks, and
`tools/macos_package_proof.py`. It uploads the unsigned tarball, adjacent
provenance, and schema-validated evidence. The independent `appkit-compile`
job remains compile-only and does not execute a `.app` bundle.

This proof does not execute Factorio and does not enable `run.execute`, Safe
beta, setup mutation, networking, credentials, dynamic plugins, signing,
notarization, tagging, release creation, or publication.
