# Validation evidence

State: local implementation validation passed; exact-head hosted validation
pending.

## Passed locally

- Route v1 SHA-256 remains
  `98561d1c956435d0d57fd7f184545c0fdfa3bf2586ec944c59b9ee75bdde8632`.
- Route v2 definition digest is
  `0b6f6a3596285275a3b9dc0ff1e82ffd228d9b18d8a2f929de6e2112adb55128`.
- Route v2 file SHA-256 is
  `765545f0325b649a29c0dd175be52b879d7ada8db6b7ac2423da54c498d9bff8`.
- Route index digest is
  `fbe77b15b635123173dd32f30cae5506612ca89d1c89eb01558a157d9d208d63`.
- `python tools/successor_play_route_definition_check.py`: PASS.
- Focused route/planning/current-truth suite: PASS, 84 tests.
- Route-specific suite: PASS, 18 tests.
- `python tools/project_state.py --validate`: PASS.
- `python tools/generate_plan_views.py --check`: PASS.
- `python tools/universal_delivery_programme_check.py`: PASS.
- focused Ruff validation: PASS.
- `python .aide/scripts/aide_lite.py test`: PASS.
- `git diff --check`: PASS.

## Local strict classification

`python tools/strict_check.py` passed the route, schema, security, package,
release, and all 84 focused regression tests before reporting two known local
workspace-only findings:

- user-owned, untracked `.vscode/` is outside the repository structure policy;
- untouched sibling provider worktrees remain checked out at historical
  revisions rather than the reconciled workspace-lock pins.

Neither finding is a route implementation defect. The task does not mutate
either user-owned IDE state or provider repositories. Clean exact-head hosted
CI is the required acceptance environment.

## Hosted gate

Pending on the final pushed task head:

- General CI;
- schema check;
- security policy;
- CodeQL;
- synthetic-product TCK;
- route-definition and generated-plan checks;
- any repository-policy-triggered provider workflows.
