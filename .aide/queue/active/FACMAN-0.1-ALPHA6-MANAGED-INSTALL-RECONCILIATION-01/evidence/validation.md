# Managed repair planning slice — validation

Validated on 2026-09-15 against the working source based on
`17df4e68959e4d7a5ba2c77f9e28c0f5fa67fd28`.

- Current-source Windows Debug `facman.exe` built under the owned external root
  `D:/Development/FacMan/repositories/factorio-launcher-5db2844e2f29/tasks/managed-install-repair-01/native-developer`.
- `flb_factorio_install_model_smoke.exe`: PASS after the controlled final
  current-source rebuild.
- Focused native CLI tests for existing reconciliation and the managed repair
  alias: 2 tests, PASS.
- Corrective focused CLI repair regression, native reconciliation intent and
  lifecycle smoke, and 9 generated-metadata tests: PASS.
- Request-schema/runtime conformance and focused metadata/frontend/source-truth
  checks: PASS during implementation validation.
- `tools/codegen/generate_metadata.py --check`: PASS.
- `tools/generate_plan_views.py --check`: PASS.
- `tools/strict_check.py`: final PASS, including 419 schemas, 251 refusal
  codes, the unchanged source budget, and all command, setup-workflow, frontend
  and generated-state checks.
- `.aide/scripts/aide_lite.py test`: PASS.
- `git diff --check`: PASS.

One root-level `unittest` invocation failed during final verification because
`tests/native_cli.py` was not importable without the repository test path. The
same two exact tests were rerun with `tests/` on `PYTHONPATH` and passed. This
was a test-invocation error before test execution, not a product failure.

Independent Sol review initially returned FAIL with three medium findings:
shared reconcile source-only regression, terminal lifecycle admission, and
incomplete CLI/grammar validation. All three received bounded corrections and
focused passing regressions. Re-review found one allowed-path omission for the
metadata generator; the exact path was added without broadening tool scope.
Final independent re-review: PASS with no residual findings.

## Provider-backed managed uninstall planning slice — validation

Validated on 2026-09-15 against
`task/facman-managed-install-reconciliation-01@f4fcd1fbb76cb444aee269095e75fa438b73dd3f`.

- `tools/codegen/generate_metadata.py --write` and `--check`: PASS.
- `tools/technical_preview_census.py` and `--check`: PASS.
- `tools/project_state.py --write` then `--validate`: PASS.
- `tools/command_contract_check.py`, `tools/refusal_contract_check.py` and
  `tools/setup_workflow_check.py`: PASS (131 commands, 253 refusals, 4 plans,
  5 guarded applies and 2 reads).
- Focused Python suite: 4 tests PASS, with 2 native-CLI tests skipped because
  this invocation had no `FACMAN_CLI_EXE`; metadata and Technical Preview tests
  executed and passed. The skipped tests are not native behavior evidence.
- Windows Debug `flb_setup_gateway_smoke` rebuilt and executed under the owned
  external task root: PASS, including the new unregistered uninstall no-write
  refusal assertion.
- `tools/strict_check.py`: PASS, including 420 schemas, setup workflow,
  contracts, generated state and source format. `git diff --check`: PASS.

No valid USK installed-state fixture was created for this slice, so no positive
managed-uninstall plan was exercised. The native result proves build linkage
and refusal/no-write behavior only.

## Provider-backed managed uninstall planning — strengthened validation

Validated on 2026-09-15 against the current dirty successor of
`task/facman-managed-install-reconciliation-01@f4fcd1fbb76cb444aee269095e75fa438b73dd3f`.

- Current-source Windows Debug `m1_three_repository_system_proof` rebuilt and
  passed in the owned cache
  `D:/Development/FacMan/repositories/factorio-launcher-5db2844e2f29/tasks/managed-install-repair-01/native-developer`,
  with the pinned `universal-setup-279ad4876dc3` provider.
- The proof creates an actual private USK installed state, registers its FacMan
  managed record, invokes the real `installs.uninstall.plan` handler and accepts
  the returned raw `usk.operation_plan.v1` only after exact identity checks.
  Content-backed snapshots show no change to target, workspace, state, audit or
  the full public USK setup root.
- Stale verification digest, setup-state reference, ownership-bound state
  revision, FacMan/USK lifecycle mismatch and provider/source mismatch all
  refuse with no target or provider-state writes.
- The older `r11` cache cannot regenerate because it references a missing old
  provider object; it is stale-cache evidence only and did not qualify this
  slice. The verified owned cache above configured and built successfully.

Final generator, strict, AIDE Lite and diff checks are recorded after this
append-only evidence update.

- Final `tools/strict_check.py`: PASS (420 schemas, 254 refusal codes and all
  contract, generated-state, source-format and workflow checks).
- Final `.aide/scripts/aide_lite.py test`: PASS.
- Final command/refusal/setup-workflow checks, metadata and Technical Preview
  `--check` modes, project-state validation and `git diff --check`: PASS.
- Final Windows Debug `flb_setup_gateway_smoke`: rebuilt and passed in the same
  verified cache.
- After final review, the gateway added an exact inspected-state digest binding
  and the response schema narrowed to the runtime's uninstall-specific roots,
  effects and invalidator set. Both native targets rebuilt and passed again;
  response-golden/schema validation passed and generated metadata was refreshed.
- Independent final postimage review reproduced one residual contract mismatch:
  the response schema accepted relative roots, traversal/absolute/malformed
  effect paths, and missing or duplicate state effects that the runtime rejects.
  The schema was narrowed and `tests.test_command_contracts` now validates the
  success golden plus nine negative mutations. The focused suite passes 2 tests;
  command-contract and schema checks pass with 131 commands and 420 schemas.
