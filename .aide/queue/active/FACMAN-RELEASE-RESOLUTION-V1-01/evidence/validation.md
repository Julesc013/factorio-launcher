# Validation evidence

## Passing evidence

- Structured implementation commit `bb2553f` was created locally after both the message policy and exact staged scope passed offline validation.
- `python -m unittest tests.test_release_compiler tests.test_release_staging tests.test_package_pipeline_architecture tests.test_generated_metadata tests.test_generated_frontend_catalogs -v`: PASS, 38 tests; one classified Windows symlink-privilege skip.
- `python tools/release_resolution_check.py`: PASS, 3 targets and 10 resolved records per target.
- `python tools/schema_validate.py`: PASS, 323 schemas.
- `python tools/version_truth_check.py`: PASS.
- `python tools/source_format_check.py`: PASS.
- `python .aide/scripts/aide_lite.py test`: PASS.
- `python tools/strict_check.py`: every in-repository check passed, including release resolution; the aggregate exit was nonzero only for the external workspace-lock observation described below.
- focused ownership regression: `BuiltPackageOutputOwnershipTests.test_builder_refuses_unowned_output_root_before_build`: PASS.
- resolution, staging, directory inspection, and exact package projection smoke: PASS for `windows_portable_cli_x64` using the existing Release CLI binary.
- `ctest --test-dir build/native-smoke -C Release --output-on-failure`: 56 of 60 tests passed.
- `git diff --check`: PASS.

## Environment-limited evidence

- The full Python discovery run stops when Windows built-package setup checks exact sibling Universal repository revisions. This sandbox can read sibling files but not their `.git` metadata, so both revisions are reported as `unknown`.
- The strict aggregate has the same sole failure: `release-contract` -> `workspace-lock` for `../universal-launcher` and `../universal-setup`.
- The native Release build compiled FacMan core, CLI, TUI, and most smoke targets, then MSBuild was denied permission to spawn `cmd.exe` for three custom-build/export steps.
- Of 60 CTests, `fl_workspace_root_authority_smoke` was not built because of that denial and `facman_installed_sdk_smoke` explicitly failed on the same denial. The existing `m1_three_repository_system_proof` and `facman_preferences_smoke` filesystem integration tests also fail in this restricted execution environment.

These limitations are not converted into passing claims. An unrestricted promotion runner must repeat the exact workspace-lock, full Python discovery, native build, and CTest gates.
