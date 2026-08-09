# Validation evidence

State: exact-head implementation and exact merged-dev validation passed;
bounded mutable-truth closeout prepared with no product authority.

## Passed locally

- Route v1 SHA-256 remains
  `98561d1c956435d0d57fd7f184545c0fdfa3bf2586ec944c59b9ee75bdde8632`.
- Route v2 definition digest is
  `0b6f6a3596285275a3b9dc0ff1e82ffd228d9b18d8a2f929de6e2112adb55128`.
- Route v2 file SHA-256 is
  `765545f0325b649a29c0dd175be52b879d7ada8db6b7ac2423da54c498d9bff8`.
- Reviewed route index digest was
  `fbe77b15b635123173dd32f30cae5506612ca89d1c89eb01558a157d9d208d63`.
- Post-integration mutable route index digest is
  `91c6e85c36a8dfbcf7fd029cf5016e0ee87f62ba664f02f3973fff47332b4a35`.
- `python tools/successor_play_route_definition_check.py`: PASS.
- Focused route/planning/current-truth suite: PASS, 84 tests.
- Route-specific suite: PASS, 18 tests.
- `python tools/project_state.py --validate`: PASS.
- `python tools/generate_plan_views.py --check`: PASS.
- `python tools/universal_delivery_programme_check.py`: PASS.
- `python tools/ci_proof_check.py`: PASS after adding the route-definition
  surfaces and validator to the dedicated schema workflow.
- `python tools/schema_validate.py`: PASS, 333 schemas.
- `python tools/package_check.py`: PASS, 26 manifests.
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

## Exact-head and merged-dev hosted proof

PR #129 exact head `b9d4f38c4be2aa0782deeed331bce9120472bd54`
and tree `312c4d2383b60f8780bc320b005fca997d615dd6` passed:

- General CI push `31294572348` and PR `31294574718`;
- schema check `31294574734`;
- security policy `31294574698`;
- CodeQL `31294574715`;
- synthetic-product TCK `31294574695`.

PR #129 merged normally as `c197b5c977bbc442adfba454f12103b8f93f5e39`
with exact parents `72e4548f5072f01f8f59657ffa5d1b609fae5411`
and `b9d4f38c4be2aa0782deeed331bce9120472bd54`; the merge tree remains
`312c4d2383b60f8780bc320b005fca997d615dd6`. Exact merged-dev runs passed:

- General CI `31298019537`;
- schema check `31298019544`;
- security policy `31298019553`;
- CodeQL `31298019518`;
- synthetic-product TCK `31298019551`.

Provider locks, workspace locks, and immutable route v1/v2 bytes are unchanged.

## Closeout validation

- Focused route/planning/AIDE/current-truth suite: PASS, 86 tests.
- Route-specific suite: PASS, 20 tests including exact integration identity
  and stale-integration refusal.
- route-definition, project-state, generated-plan, universal-delivery,
  CI-proof, schema, package, Ruff, AIDE Lite, and diff checks: PASS.
- `python tools/strict_check.py` passed every repository validator and the
  closeout regressions before reporting only the already-classified local
  `.vscode/` and historical sibling-provider checkout conditions above.
