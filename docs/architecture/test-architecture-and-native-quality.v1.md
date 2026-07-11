# Test architecture and native quality v1

`contracts/policy/test_impact.v1.json` is the machine-readable map from changed
modules to native targets, Python tests, strict validators, and package lanes.
`python tools/dev.py test --affected` uses that map. Fast and full validation
remain explicit through `--fast` and `--full`; `verify-all` adds strict policy
validation. Promotion still requires the full matrix even when affected tests
are green.

CTest labels and matching Python category suites cover fast unit, contract,
integration, filesystem, archive, transaction, package, platform, and fuzz
work. The operator category intentionally exits without a pass: human
acceptance is an operator verdict, not an automated test result.

The native policy applies curated warnings to first-party targets and CI turns
warnings into errors. Linux CI runs changed-translation-unit clang-tidy, a
full-core ASan/UBSan CTest lane, a bounded Clang libFuzzer target, and a
critical-module gcovr report. Windows builds and tests Debug and Release.
macOS builds and tests the full Release native core. ABI proof combines compile
time layout constraints with runtime shared-library export/version checks.

`docs/quality/benchmarks/baseline.v1.json` records host-identified advisory medians for
startup, command dispatch, archive inspection, mod inspection, diagnostic
traversal, and package hashing. Shared CI reports regressions but does not fail
on noisy microbenchmarks; dedicated stable runners may opt into `--enforce`.
The Windows baseline in this revision is evidence for this host only, not a
cross-platform performance claim.
