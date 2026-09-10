# Validation

Result: PASS for the report-only WorkUnit scope.

- Fresh GitHub observation under `BLACKGLASS-WIN1\Jules` and account
  `Julesc013`: repository ID, repository merge settings, and rulesets
  `20445007` and `21787868` captured exactly.
- Focused governance/current-truth suite: 95 tests passed.
- `tools/project_state.py --validate`: PASS.
- `tools/generate_plan_views.py --check`: PASS.
- `tools/dev.py test --affected`: PASS.
  - native selection: 1 of 1 passed;
  - Python selection: 73 tests passed;
  - strict validators: all selected validators passed;
  - two package-runtime fixtures skipped: one optional install-stage fixture and
    one required-blocked WinForms artifact fixture not built by the affected
    target selection. Neither skip is promoted as full release qualification.

The exact protected-head and merge-head hosted matrices remain required before
canonical integration. This report does not inherit or extend Alpha.5 product
candidate qualification.
