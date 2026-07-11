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

Exact-SHA attempt `ad51cc3f13bea002f6a8433f3faa9c05728a3510`, CI
`29158844890`, built the complete macOS native core but CTest exposed that the
runner's default `/var/folders/...` temporary root crosses the `/var` symlink.
The lock, diagnostics, and Universal Setup package-verification tests correctly
refused that linked root; downstream proof steps were skipped. The repair does
not weaken traversal policy: it gives the macOS job an explicit resolved
runner-owned `TMPDIR` and verifies that its real path is identical before any
native test runs.

Repair attempt `ce54b6f6db9235c5bbba275f87348414dc96d3ed`, workflow
run `29158980502`, was rejected before jobs because GitHub does not expose the
`runner` expression context in job-level `env`. The corrected workflow derives
the same path from the documented `RUNNER_TEMP` process environment during the
setup step and persists it with `GITHUB_ENV`; no native policy or test is
changed or skipped.

Replacement revision `ee882405c002f15e71d3e2c188823d2a89ededdd`, CI
`29159016898`, passed the complete macOS native build, CTest 9/9, portable
Python 226/226, and strict checks. The package builder then failed closed
because `built_package.v1` had not yet admitted `macos` in its target enum.
The schema-only repair adds that already indexed target and a regression
assertion; it does not relax identity, architecture, linkage, integrity, or
provenance checks.
