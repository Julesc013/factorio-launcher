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
