# Validation

Result: PASS, including exact-SHA macOS target CI and artifact inspection.

- Fresh Windows native configure/build: PASS.
- Native CTest: PASS (9/9).
- Complete portable Python suite: PASS (226/226, zero skips).
- Focused macOS profile/schema/CI/package contract suite: PASS (27/27).
- Strict checks: PASS with 65 schemas, 23 package manifests, 13 bundle
  manifests, 8 release profiles, and 8 package skeletons.
- Source format and `git diff --check`: PASS.

The local Windows host did not promote the macOS claim. Clean exact revision
`6dcdf74f69decde44a5883e961081dd15f9977cc` supplied the target proof on
`macos-15-intel` in CI `29159257155`.

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

Revision `745f17767fb5f0f36d97c0dddcf3a1c6878cb4e9`, CI
`29159110943`, passed the complete macOS native, CTest, Python, strict, package,
and artifact-upload sequence. Inspection of artifact `8250313374` found that
the `file` tool's identity string retained an absolute ephemeral runner path in
the packaged linkage metadata. The pre-freeze repair strips the executable
prefix and makes the schema require exactly `Mach-O 64-bit executable x86_64`;
the artifact must be regenerated and re-proven before checkpoint promotion.

Final run `29159257155` passed all five jobs, including macOS CTest 9/9,
portable Python 226/226, strict, 15 required package checks with zero skips,
and artifact upload. The regenerated tarball SHA-256 is
`c930045e460aabcbd121e992ef79f37b2739e937a2bff1c58499263cecaa849d`;
provenance SHA-256 is
`f85152c8c5d66db0e7e4527670ba66f503bbff4255ad2579adb00f9ee9627ce1`.
Downloaded extraction re-verification passed for all 127 files, provenance,
path-free Mach-O identity, exact deployment target, dependencies, and absence
of the runner workspace path.
