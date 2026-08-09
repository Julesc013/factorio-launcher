# Validation

Result: **PASS for doctrine and mechanical enforcement; activation remains
planned.**

- Canonical metadata generation and deterministic `--check`: PASS.
- Plan-view generation/check and project-state validation: PASS.
- Schema validation: PASS, 337 schemas.
- Release-programme, version-truth, branch-policy, component-ownership,
  release-resolution, release-integration, source-format, structure, security,
  compliance, and strict repository checks: PASS.
- Focused release, provider, source-closure, plan, package, frontend, and AIDE
  tests: PASS, 133 tests before final repairs and 46 repair-focused tests.
- Native Windows MSVC Debug build: PASS with warnings-as-errors and the explicit
  `/EHsc` toolchain input required by the local Visual Studio 2026 host.
- Native CTest: PASS, 39/39.
- Complete Python discovery with rebuilt native/package surfaces and exact
  provider-root bindings: PASS, 958 tests with 8 explicitly optional/platform
  skips.
- AIDE Lite portable validation: PASS.
- `git diff --check`: PASS.

Exact provider validation used clean detached worktrees at ULK
`1cafe4054297cc11e02458b83d230db0cd064471` and USK
`32488fc13bd2439f9f6e52e83a97f6da345a7650`.
