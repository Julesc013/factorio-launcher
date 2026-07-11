# Changed Files

- `.github/workflows/ci.yml`: adds the explicit `macos-15-intel` full native,
  CTest, Python, strict, zero-skip package-proof, and artifact-preservation job.
- `release/profiles/macos_portable_cli_x64/`, the macOS bundle manifest, and
  release indexes: add one CLI-only Intel tarball package-preview lane.
- `tools/package_build.py` and `tools/macos_package_proof.py`: record and
  enforce Mach-O x86_64 identity, deployment target 13.0, SDK/toolchain,
  system dependencies, no `LC_RPATH`, integrity, relocation, extraction,
  SPDX, and adjacent provenance.
- Runtime package verification and CLI setup routing: recognize the canonical
  macOS profile and continue routing `package.verify` through Universal Setup.
- Strict schemas, package/component validators, skeleton logic, and tests:
  distinguish a macOS CLI root from the independently planned `.app` layout.
- Architecture, CI, roadmap, release, safety-claim, and AIDE evidence docs:
  preserve the Intel-only, AppKit compile-only, unsigned, unpublished bounds.

No Factorio process execution, AppKit runtime, Apple Silicon or universal
binary claim, setup mutation, network behavior, signing, notarization,
tagging, release creation, or publication was added.
