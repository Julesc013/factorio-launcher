# FACMAN-COMPLIANCE-AND-SUPPLY-CHAIN-01 validation

Result: PASS on Windows x64 with provider-license uncertainty preserved.

## Implemented evidence

- Controlled SPDX formatter verified 341 tracked first-party source files.
- REUSE metadata and license texts identify MIT first-party code, Miniz MIT,
  and PicoJSON BSD-2-Clause ownership.
- Dependency lock verifies exact Miniz source, header, and license SHA-256.
- Built packages reproduce the exact vendored Miniz and PicoJSON notices.
- SPDX package SBOMs cover every installed bundle component with `CONTAINS`
  relationships; independent provenance verification reconstructs the expected
  set from the installed bundle manifest.
- Universal Launcher and Universal Setup remain `NOASSERTION`. The separate
  operator decision is planned and no provider repository was patched.
- Vulnerability reporting and supported-version policy are documented.
- Integrity and provenance remain unsigned and do not claim publisher
  authenticity.

## Validation

- Release build with warnings as errors: PASS.
- Selected Release CTests: 4/4 PASS.
- Affected Python validation: 76/76 PASS.
- Focused compliance/package suite: 37/37 PASS.
- Strict repository checks, including compliance: PASS.
- Portable AIDE Lite suite: PASS.
- Windows portable CLI package runtime, relocation, hash, SBOM, provenance,
  and notice verification: PASS through the affected package suite.
- Package/profile/schema validators: PASS for all declared profiles.
- `git diff --check`: PASS.

Linux and macOS runtime package execution remain target-runner obligations for
the R3.4 closeout matrix. This work unit does not convert local structural
validation into a target-platform claim.
