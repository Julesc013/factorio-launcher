# Validation evidence

Implementation commit: `15796aa` (`feat(release): bind exact source and resolution custody`)

## Passing evidence

- `python -m unittest tests.test_release_compiler tests.test_release_staging tests.test_package_pipeline_architecture tests.test_release_resolution_integration tests.test_universal_delivery_programme -q`: PASS, 46 tests with one classified Windows symbolic-link privilege skip.
- Final post-closeout focused suite covering release, staging, packages,
  programme, plan, current truth, and AIDE truth: PASS, 81 tests with the same
  one classified Windows symbolic-link privilege skip.
- `python tools/release_resolution_integration_check.py`: PASS for source custody, runtime boundary, all eleven package profiles, seven exact historical exceptions, and plan state.
- `python tools/schema_validate.py`: PASS, 326 schemas.
- `python tools/source_format_check.py`: PASS.
- `python tools/codegen/generate_metadata.py --check`: PASS.
- `python tools/generate_plan_views.py --check`: PASS.
- `python tools/project_state.py --validate`: PASS.
- `python .aide/scripts/aide_lite.py test`: PASS.
- `python .aide/scripts/aide_lite.py commit check --latest`: PASS.
- `git diff --check`: PASS.
- Release rebuild compiled the updated `facman.exe`, `facman_client_smoke.exe`, generated identity, compiler-dependent native libraries, and nearly all native proof targets.
- `ctest --test-dir build/native-smoke -C Release --output-on-failure`: 57 of 60 tests passed, including `facman_client_smoke`, `facman_runtime_package_identity_smoke`, archive/JSON/path/security tests, and release-related native contracts.
- `python tools/strict_check.py`: every in-repository check passed, including release resolution, integration policy, schemas, generated metadata, packages, provenance, security, AIDE truth, and programme constraints.

## Environment-limited evidence

- The strict aggregate remains nonzero only because `../universal-launcher` and `../universal-setup` are absent. Their exact workspace-lock revisions cannot be observed, fabricated, or fetched under this offline WorkUnit.
- Full Python discovery ran 744 tests. The new release and repository checks passed, but the aggregate reported 28 failures, 2 setup errors, and 6 skips. Two setup errors and the dependency/strict failures require the absent sibling repositories; the remaining failures are existing native temporary-workspace canonicalization refusals in this restricted Windows execution environment.
- The native Release build cannot launch `cmd.exe` from MSBuild without elevation for the ULK and USK shared-library export steps. The two shared targets therefore remain unbuilt here.
- The three CTest failures are `m1_three_repository_system_proof` and `facman_preferences_smoke` filesystem behavior under the restricted environment, plus `facman_installed_sdk_smoke`, whose nested MSBuild `cmd.exe` step requires elevation.

These limitations are not converted into passing, source-closure, security-review, package-convergence, qualification, signing, publication, Setup-mutation, or execution claims. They must be repeated on an unrestricted runner with both exact provider checkouts.
