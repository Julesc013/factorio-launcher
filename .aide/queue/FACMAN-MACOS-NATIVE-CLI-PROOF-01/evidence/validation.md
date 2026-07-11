# Validation

Result: LOCAL IMPLEMENTATION GATES PASS; EXACT-SHA MACOS TARGET CI PENDING.

- Fresh Windows native configure/build: PASS.
- Native CTest: PASS (9/9).
- Complete portable Python suite: PASS (226/226, zero skips).
- Focused macOS profile/schema/CI/package contract suite: PASS (27/27).
- Strict checks: PASS with 65 schemas, 23 package manifests, 13 bundle
  manifests, 8 release profiles, and 8 package skeletons.
- Source format and `git diff --check`: PASS.

The implementation is intentionally not runnable as a macOS package proof on
this Windows host. Promotion requires a clean exact revision on
`macos-15-intel` to build the complete native core, pass all CTests and the
portable Python/strict suites, execute the package matrix with zero required
skips, and upload the tarball, adjacent provenance, and evidence report.

The independent AppKit lane remains compile-only. Local checks do not promote
Apple Silicon, universal binaries, broader macOS compatibility, app-bundle
runtime, signing, notarization, authenticity, release, or publication.
