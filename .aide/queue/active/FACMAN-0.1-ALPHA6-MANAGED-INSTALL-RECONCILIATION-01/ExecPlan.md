# Finish bounded managed install update repair and removal

1. Inspect the exact current source and relevant prior evidence; classify
   remaining gaps against this task's acceptance criteria.
2. Check actual start prerequisites and claim a WIP slot in the canonical
   plan. Complete the AIDE task and Git helper checks and record an exact-base
   branch plan before branch mutations.
3. Implement the bounded scope from task.yaml with focused regression tests.
   If it exceeds one reviewable work unit, split it before further changes.
4. Run affected native/Python/strict/package checks and retain failures.
   Remediate findings and obtain independent review of the resulting source.
5. Commit and normally integrate with required current checks; record exact
   integration evidence. Recheck close_after prerequisites before closing.

Current user authority includes necessary source changes, tests, docs, sync,
commits and normal checked merges. Publication and genuine experience remain
separate. Unavailable host/input cells block their own qualification only.

## 2026-09-15 — managed repair planning slice

- Activated this WorkUnit from the current integrated `dev` revision
  `17df4e68959e4d7a5ba2c77f9e28c0f5fa67fd28`.
- Routed `installs.repair.plan` for registered managed installs through the
  existing read-only reconciliation model. Optional archive input is retained
  as selected, unverified source evidence and produces an inspection blocker.
- Kept repair apply, SetupGateway mutation, live-target mutation and release
  authority closed. Invalid, unknown and non-managed install references retain
  explicit refusals.
- Updated the command contract, response schema, generated catalogs, CLI truth,
  refusal/success goldens, focused tests and narrow truth checkers.
- Passed the current-source Windows Debug build and native install-model smoke,
  focused native-CLI tests, 419-schema strict validation, portable AIDE Lite
  validation, generated metadata/plan validation and `git diff --check`.
- Independent model review found three medium defects before commit: ordinary
  reconcile source-only behavior had changed, terminal lifecycle records were
  admitted, and CLI/structured grammar validation was incomplete. The bounded
  successor adds an explicit repair intent, lifecycle admission/evidence, and
  strict repair option parsing with generated grammar coverage. A controlled
  rebuild and focused regressions pass.
- Re-review confirmed those runtime findings closed and found one scope-record
  omission for the narrowly changed metadata generator. The exact generator
  path was added to `task.yaml`; no broader tools scope was granted.
- Final independent re-review passed with no residual findings. Full strict
  validation also passed at the unchanged source budget.
- This is one bounded slice. Update, repair apply, removal, transition leases,
  crash recovery and genuine managed-install product evidence remain open, so
  the WorkUnit stays active and no Alpha/Beta release claim is made.

## 2026-09-15 — provider-backed managed uninstall planning slice

- Advanced `installs.uninstall.plan` on the current task branch source
  `f4fcd1fbb76cb444aee269095e75fa438b73dd3f`. The route remains an always
  dry-run USK `uninstall.plan` request; `installs.uninstall.apply` and every
  live mutation route remain closed.
- Admission requires a registered managed record in lifecycle `active`,
  `verification_failed`, or `recovery_required`, with target, setup-state,
  verification and state-revision evidence. Foreign, unknown, terminal and
  incomplete records refuse before provider entry.
- The gateway sends `usk.uninstall_plan_request.v1` and admits only a strict
  `usk.operation_plan.v1` uninstall response bound to request identity,
  target, installed-state/ownership/policy/provider evidence, owned effects
  and immediate revalidation. It preserves the raw provider plan and creates
  no FacMan state or target writes.
- Current-source focused checks, Windows Debug gateway build/smoke, generated
  metadata, project-state, Technical Preview outputs and full strict validation
  pass. This is source and native negative-path evidence only; it does not
  qualify a real managed uninstall or any release gate.

## 2026-09-15 — strengthened provider-backed managed uninstall planning

- Tightened the read-only route to inspect the current USK installed state before
  requesting a plan. The retained FacMan record must bind the exact Universal
  Setup provider/source, target, canonical setup-state reference, verification
  digest, transaction-plus-ownership state revision and compatible lifecycle.
- The runtime decoder now accepts only exact response/envelope, root, effect,
  revalidation and path forms from the promoted USK plan contract. It rejects
  extras, duplicate identities, non-owned effects and unsafe paths. Apply and
  every mutation remain closed.
- Added current-source M1 proof against an actual private USK installed-state
  fixture. It proves the real handler emits a valid raw plan and makes no bytes
  change in the target, FacMan workspace, USK state/audit, or public USK root;
  stale record evidence and provider/source mismatches fail closed.
- Final remediation also recomputes the provider's canonical installed-state
  digest from the inspected state and requires the later plan to bind that
  exact digest. The mirrored response schema now expresses the exact four-root,
  uninstall-effect and five-invalidator shapes admitted by the runtime.
- WorkUnit remains active: this proof advances plan admission only and does not
  establish uninstall execution, recovery, product acceptance or release
  eligibility.
- Independent postimage review confirmed the runtime binding and no-write proof,
  then found the mirrored response schema still admitted unsafe relative paths
  and incomplete or duplicate state effects. The schema now requires normalized
  absolute roots, safe component-only effect paths, and exactly one journal,
  state and audit effect; focused negative schema regressions cover the reviewed
  counterexamples. The corrected source and contract checks pass.
