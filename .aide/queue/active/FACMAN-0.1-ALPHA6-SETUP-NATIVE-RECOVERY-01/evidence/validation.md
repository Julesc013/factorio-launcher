# Validation

Source base: `412ab5aef55ecb771ee868ee46d1555d625de733`

Passed on 2026-09-13 against the current source and pinned Universal Setup and
Universal Launcher providers:

- MSVC Debug build of `facman_setup`,
  `facman_self_setup_recovery_smoke`, and
  `facman_windows_integration_ownership_smoke`.
- CTest selection
  `facman_self_setup_lifecycle|facman_self_setup_recovery_smoke|facman_windows_integration_ownership_smoke`:
  3/3 passed.
- Python selection `tests.test_self_setup_recovery_contract`,
  `tests.test_self_setup_package`, `tests.test_setup_package_routing`, and
  `tests.test_json_contract_subset`: 18/18 passed.
- `tools/codegen/generate_metadata.py --write` and
  `tools/project_state.py --write` completed.
- `tools/strict_check.py` passed with 418 registered schemas.
- `git diff --check` passed, apart from informational line-ending warnings.

The first strict run found one 345-character fixture line. It was reformatted
without changing behavior; the strict check then passed. The recovery smoke was
rebuilt and passed after adding real concurrent lock contention.

Independent model review first required changes for implicit rollback consent,
intent-scoped admission, canonical root aliases, unchecked durable writes,
timestamp bounds, provider-root persistence, terminal pre-apply retirement, and
schema/loader parity. Its final review then found that a portable journal could
inherit a later installed-mode adapter. Durable journal mode now controls native
reconciliation, the cross-mode restart regression passes, and the independent
review returned `PASS` on the corrected source.

PR #273 exposed a platform-specific defect in the contention fixture: the test
used the Windows case alias `INSTALL` for `install`, which names a different path
on case-sensitive Linux filesystems. The production root-lock implementation was
unchanged. The POSIX fixture now uses a directory-symlink alias to the same
existing parent. A local Ubuntu 24.04 GNU 13.3 build against the exact locked
providers passed `facman_self_setup_recovery_smoke` with 31 checks, and the
corresponding MSVC Debug CTest passed again on Windows. The failed hosted
observations remain run `34761848507`, jobs `103735973057` (`linux-native`) and
`103735973010` (`linux-coverage`); current hosted requalification is pending.

## 2026-09-15 managed uninstall recovery validation

Passed against combined base `57a1745bac987a79658cfa825789ff48ec393329`
with pinned Universal Setup `279ad4876dc325f8e1fcdc918c91b098a11bc616`:

- MSVC Debug build and execution of `m1_three_repository_system_proof`.
- MSVC Debug build of `facman_cli`; generated help exposes
  `installs recovery apply <transaction-id> <plan-id>`.
- Python command contract, frontend contract, generated metadata, generated
  frontend catalog, capability policy, request/runtime conformance, and refusal
  contract tests: 22 tests passed with 129 platform/fixture skips.
- `tools/codegen/generate_metadata.py`, command/frontend/capability/refusal
  standalone checks, and `git diff --check` passed.
- `tools/setup_workflow_check.py`, `tools/frontend_parity_check.py`,
  `tools/application_handler_check.py`, and `tools/source_format_check.py`
  passed after the recovery routes were added to their canonical policy views.
- `tools/strict_check.py` passed with 422 registered schemas, and
  `.aide/scripts/aide_lite.py test tiers` passed in report-only mode.
- The pinned protected-report restore verifier passed with 10 reports restored
  to exact bytes and mtimes and both originally absent reports still absent.

The M1 proof reopens the application context across interruption and checks
deterministic inspection, exact retry output, durable coordinator checkpoints,
install-reference CAS, retained foreign content, and absence of mutation for
corrupt, mismatched, drifted, or incomplete evidence.

Independent review remediation added configured, unconfigured, and incomplete
setup-admission checks; exact malformed provider-report checks; and wrapped
`unknown_install`, `lifecycle_refused`, and `stale_plan` provider-refusal checks.
The focused MSVC admission and M1 tests, four focused Python contract modules,
and the source-format, capability-policy, and command-contract checks pass.

The final authority review separated recovery preview admission from setup
mutation admission. Missing or incomplete accepted Setup configuration now
returns `setup_uninstall_recovery_authority_required` for both recovery routes;
the refusal has `setup_preview` effect semantics and both command contracts list
it. The rebuilt native admission test passed, four focused Python modules passed
with 129 fixture/platform skips, generated metadata checked current, and the
command, capability, and 273-code refusal checks passed.

## 2026-09-15 external maintenance source validation

Current source base:
`0129f7ec6fa5864c40c6c6f4a3d3aab98b41f7ba`.

- The pinned Python contract, package-manifest and candidate-workflow selection
  passed 35 tests.
- MSVC Debug rebuilt `facman_setup`, `facman_self_setup_recovery_smoke`, and
  `facman_windows_integration_ownership_smoke` from the current checkout.
- Focused CTest passed 4/4, including the platform I/O smoke; the recovery and
  ownership binaries reported 59 and 109 assertions respectively after the
  retained-source, provider-stage and legacy-migration regressions were added.
- Generated metadata was refreshed for the 426-schema contract set; the first
  strict run found only those two expected stale generated identities.
- The final full strict check passed all current source, schema, packaging,
  release-truth and AIDE project checks for the corrected postimage.
- Python syntax validation and `git diff --check` passed.
- A read-only mechanical review found no API, schema or command-shape mismatch.
- The first independent lifecycle/provenance review found six defects in cache
  custody, installed-source binding, retry classification, terminal schema,
  registered-command qualification and a stale test expectation. The corrected
  source now validates an exact receipt for the cached ZIP and launcher at every
  restart and mutation edge; strict-inspects the authoritative installed source;
  binds the uninstall plan to that source and provider revision; distinguishes
  retryable source input from uncertain destination effects; rejects incomplete
  terminal uninstall journals; and resumes interrupted uninstall through the
  captured registered command. The real provider returned the healthy
  `verified` state after repair, so the inspection admits exactly `installed`
  and `verified`; the current 3/3 CTest run exercises that path.
- The measured workspace-hygiene doctor reported 21,515,066,684 task-root
  bytes against the existing 20-GiB limit, an invalid old task-root marker, two
  unmanaged historical secondary worktrees and merged local task branches.
  This slice created no new worktree or heavy build root after that observation;
  hosted package qualification does not consume the shared local task store.
- Windows platform I/O now proves handle-owned no-replace publication, preserves
  a foreign destination on refusal, denies a deterministic rename while a cache
  input is pinned, checks that its pathname still names the pinned object, and
  rejects hard-linked ZIP and launcher inputs before setup mutation.
  Recovery tests prove invalid cached maintenance identity persists as
  recovery-required across restart, while malformed installed-state and
  mismatched no-effect plan responses are retired and allow a fresh request.

Hosted produced-package qualification remains pending. This source validation
does not close the WorkUnit or claim a real Start Menu/registry result.
