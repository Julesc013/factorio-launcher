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

## 2026-09-15 — provider-backed managed uninstall apply slice

- Advanced `installs.uninstall.apply` from its acceptance stub on the current
  successor based on integrated `dev@81fe4d671fb0e132f8995a2b27c58d3a65206d65`.
  The request carries the exact public plan handoff plus caller-selected stable
  transaction and apply-time identities; it never regenerates those identities
  during provider entry or retry.
- Admission revalidates the retained managed record, reconstructs the exact USK
  plan request, persists a coordinator journal before provider entry, invokes
  USK uninstall apply, validates the canonical provider report and re-inspects
  terminal provider state before replacing the FacMan install reference.
- Provider refusals that are known to precede effects close the coordinator as
  refused. An exception after provider entry retains a recovery-required journal
  and the old FacMan reference so later recovery can distinguish unknown effects
  without falsely reporting success.
- The install-reference replace path now uses the expected preimage digest and
  a stable per-record lock, verifies the preimage immediately before replacement,
  and removes owned temporary and lock files on handled exits.
- Current-source Windows Debug gateway and M1 system proofs pass. The M1 fixture
  covers clean owned removal, stale plan, retained foreign content, restart-visible
  transaction context, stale-record replacement refusal and interruption after
  provider effects. Full strict validation passes with 421 schemas and 257
  refusal codes.
- This is private synthetic fixture evidence. Automated projection recovery for
  a target-absent interrupted uninstall, physical Linux/macOS qualification,
  genuine managed Factorio acceptance, the remaining managed lifecycle routes
  and release gates remain open. The WorkUnit stays active.

## 2026-09-15 — managed uninstall apply postimage assurance

- Independent postimage review found six correctness gaps in the first apply
  successor: generic recovery could misclassify an interrupted uninstall,
  supported install writers did not share one stable repository lock, provider
  refusal data could escape its phase, terminal inspection retained too little
  immutable state, transaction identifiers disagreed across contracts, and the
  advertised capability was broader than configured mutation authority.
- The corrected successor makes generic recovery refuse operation-specific
  uninstall journals without changing bytes, serializes supported install
  writers on `installs/.repository.lock`, validates provider refusals exactly,
  binds the full immutable terminal state, gives transaction identifiers one
  generated request-field contract, and advertises only
  `install.managed.uninstall.apply` when setup mutation is configured.
- A second review found one residual post-effect phase bug: a provider
  `unknown_install`, `stale_plan`, or `invalid_argument` returned by terminal
  inspection could enter the pre-effect refusal whitelist. Terminal inspection
  now always reports the phase-specific
  `setup_uninstall_terminal_state_inspection_refused` recovery outcome and
  retains the raw provider envelope. The M1 proof exercises exact
  `unknown_install` after target removal and proves that the target remains
  absent, the old install reference and recovery journal remain, and generic
  recovery makes no mutation.
- Current-source focused native and Python validation passes after the final
  correction. The full strict and portable AIDE gates are rerun at the commit
  boundary, with hosted checks required before normal integration.
- Operation-specific automated recovery, physical host and packaged product
  qualification, genuine managed Factorio evidence and the remaining lifecycle
  leaves remain open. This WorkUnit remains active.

## 2026-09-15 — provider-backed managed repair plan/apply slice

- Advanced `installs.repair.plan` from the read-only reconciliation alias to an
  exact provider-backed plan over the reviewed archive and managed-record
  preimage. The FacMan outer digest binds the complete USK request and provider
  plan so separate CLI invocations can replay the reviewed identity.
- Implemented `installs.repair.apply` with the full plan/preimage/transaction
  handoff. Apply replans before any coordinator write, persists the exact
  provider plan and a provider-entry checkpoint before mutation, validates the
  strict provider report and terminal installed state, and replaces the
  existing FacMan record through its exact preimage CAS while preserving all
  unrelated record members and unknown target content.
- Known pre-effect provider refusals close the coordinator as refused. Any
  other failure after provider entry retains a recovery-required journal and
  the old FacMan reference. A durable `terminal_projection_prepared` checkpoint
  makes post-provider/pre-CAS interruption inspectable. Exact apply retry and
  generic recovery refuse with `operation_specific_recovery_required` until a
  repair-specific recovery successor exists; no USK finalize or rollback path
  is called.
- Updated command/request/response/coordinator schemas, refusal and admission
  policy, CLI parsing, frontend metadata, generated catalogs, goldens and
  focused native/Python proofs. Strict report decoding rejects extra members,
  invalid enums/timestamps/digests, unsafe or duplicate paths, identity drift,
  and changed reviewed unknown-content sets.
- Current-source Windows Debug build and focused native proofs, focused
  command/refusal/frontend/CLI checks, the 426-schema strict suite and portable
  AIDE Lite suite pass. This is synthetic owned-fixture evidence and does not
  qualify a genuine Factorio install or additional hosts.
- Cross-operation FacMan repair/uninstall lease unification and automated
  repair recovery remain bounded successors. The provider transaction layer
  still excludes competing provider mutation, while this slice explicitly
  refuses ambiguous retry/recovery rather than claiming completion. The
  WorkUnit remains active.

## 2026-09-15 — repair terminal-inspection phase remediation

- Independent review found that a provider refusal returned by the terminal
  `installed.inspect` after a successful repair could retain a pre-effect code
  and be misclassified as a no-effect refusal by the coordinator.
- Terminal repair inspection refusals now always use
  `setup_repair_terminal_state_inspection_refused`; terminal response decoding
  failures always use `setup_repair_terminal_state_response_invalid`. Both carry
  recovery-required phase provenance while preserving nested provider detail.
- The owned M1 fixture now injects provider `unknown_install` only at the
  terminal inspection after the repair effect and proves repaired provider
  state, unchanged FacMan preimage, a recovery-required coordinator, no refused
  closure, and idempotent operation-specific recovery refusal.

## 2026-09-15 — final repair apply review remediation

- Replaced the repair-apply CLI's first-match option lookup with an exact scan
  from argv index 5. Every published value option must occur exactly once,
  `--json` may occur at most once, and duplicate, unknown, stray or missing
  tokens refuse locally before dispatch.
- Added a coordinator proof in which FacMan durably records provider entry and
  Universal Setup returns exact `stale_plan` before mutation. The coordinator
  closes refused while target bytes, provider state and the FacMan record remain
  byte-identical.
- Added independent FacMan outer-digest perturbations for the nested provider
  plan, archive-bearing plan request and raw record preimage. Each changes the
  digest and the tampered identity refuses before journal/provider entry.
- Expanded strict repair report negatives for invalid status enums, malformed
  verification digests, wrong verification references, recipe/source binding
  drift and repaired-file digest drift.

## 2026-09-16 — operation-specific managed repair recovery

- Advanced the existing `installs.recovery.inspect/apply` commands to interpret
  retained `facman.managed_repair_coordinator.v1` journals. Inspection produces
  an exact deterministic recovery plan and classifies only a proved absence of
  provider effects, an exactly completed repair, or an indeterminate state.
- Apply revalidates the plan, journal and current install-reference preimage
  under the shared managed-install recovery lease. It either closes a proved
  no-effect operation or projects the exact repaired provider terminal state by
  compare-and-swap; indeterminate evidence remains blocked.
- The provider gateway loads the canonical no-follow pre-repair snapshot and
  binds its recorded installed-state, ownership, recipe and source identities.
  A completed terminal state must preserve product/version, setup ABI, provider
  revision, components, entrypoints, target and audit identity before FacMan can
  classify or project it.
- The M1 system proof covers interruption before provider entry, stale recovery
  plans, completed provider repair, interruption after FacMan projection,
  idempotent retry, and one-family-at-a-time terminal identity drift. The shared
  response schema now rejects impossible operation/journal/target combinations.
- Independent Sol postimage review found the initial terminal binding and shared
  schema too weak. Both were corrected; the exact corrected postimage received
  a PASS with no remaining blocker. Full Windows Debug CTest passes 45/45 and
  the strict repository gate passes with 428 schemas and 290 refusal codes.
- The WorkUnit remains active. Cross-operation coordination, the remaining
  install/move/verify/adoption lifecycle, genuine Factorio and physical host
  qualification, packaging, signing and release acceptance remain open.

## 2026-10-13 — read-only managed installation verification

- Implemented registered installs.verify using pinned Universal Setup read-only inspection/verification with exact provider, record, ownership and report bindings. The default unconfigured capability remains unavailable.
- Verified healthy, damaged and absent targets, archive independence, preserved foreign data, and record/provider/link refusals. Ordinary CLI, JSON and declared v2 stdio RPC report actual observations without mutation.
- Accepted 27 real public CLI calls including 8 human-format calls, one RPC call, native decoder smoke, strict gate and AIDE. See evidence/managed-verification-native.v1.json and its hash-closed custody for exact source/images, independent review, failures and owned execution receipts.
- Scoped source-native synthetic engineering acceptance only. Produced packages, genuine host/game/human acceptance, remaining lifecycle transitions and complete F11/Beta remain open; the WorkUnit stays active.

## 2026-10-13 — PR408 census assertion correction

- Required macOS complete-suite execution found the old fixed implemented-unqualified count (14). Registered verification correctly adds one unqualified implementation, making the exact count15. Corrected only that expectation after independent non-authoring review; unknown81 and every scope/release assertion stay unchanged.
- Focused census tests pass. Runtime/native/provider sources and earlier scoped native proof are retained; fresh required checks remain necessary. See evidence/pr408-census-correction.v1.json. No WorkUnit or Beta gate is closed.

### Shared managed installation coordination and requested-crash recovery

This continuation starts from integrated dev c089396b without another clone, worktree or task root. Install, repair, uninstall and operation-specific recovery now retain a shared OS-backed guard across FacMan workspaces using the same configured Setup installation namespace. A durable REQUESTED coordinator precedes guard creation; exact plan/reference preimages are revalidated under the guard before provider work and short repository projection. Physical termination reproduced a REQUESTED-to-AUDITED closure failure and missing early repair-state admission. Proved no-provider-effect recovery now follows the existing durable recovery-required/audit/complete transitions, preserving already-audited and terminal paths.

Independent source/custody review verified four native regressions and39 actual owned public commands, including three physical install/repair/uninstall deaths, ordinary exact-owner recovery, cross-workspace contention, case/8.3 aliases, terminal retry races and foreign/torn metadata preservation. The original build helper exited naturally; a reviewed external termination attempt aborted without handle access or mutation. Ordinary public primary exits use scoped Job cleanup, so no all-member natural-exit or process-lifetime qualification is claimed. The public result remains partial/exit1: Windows provider path policy refuses before the prospective8192-byte metadata limit can be exercised. The size-before-create and deterministic bounded read/serialization invariants are reviewed source evidence only.

The Setup-root leaf retains the documented portable ASCII identifier restriction; Unicode/spaces in existing parents are supported. Direct USK actors and distinct state roots targeting the same installation remain outside this guard. Default mutation authority and provider pins remain unchanged. Fresh required CI and delivered-package proof remain pending; complete maintenance, real game, human/other-host, WorkUnit, Beta and release acceptance remain open. Evidence: evidence/managed-install-coordination.v1.json and its hash-closed custody.

### Qualify ordinary owned GUI button notification

Required source1882 job115922317551 passed all four Windows native configurations but failed its first Make Ready input dialog. The retained24-file FAIL custody shows matching nonzero presentation revisions, visible/enabled control and ancestors, one successful native-click post, no dialog/domain refusal, and normal zero-job exit. Linux native3 configurations and macOS native1 also pass the affected shared-guard tests; those exact source logs remain preserved. No check bypass or duplicate optional campaign occurs.

The bounded test correction queues one ordinary WM_COMMAND/BN_CLICKED to the exact live owned button parent, binding native type, visible/enabled ancestors, root, full observed control ID and lParam. Registered UI handlers, dialogs and domain/readiness validation remain the outcome oracle. There is no focus takeover, retry, runtime/provider edit or deadline increase. Both historical native-click and current notification diagnostics remain truthful. The hosted internal cause was not observed; the old local baseline also passes, so no causal reproduction is claimed.

Independent review verifies the unchanged two-session GUI/effect oracle with68 actual historical packaged backends,8fixture calls, preserved inputs and598-file closure, normal exits,16 identity/refusal checks, and a controlled real FAIL with24 independently decoded files. The reused002824 package is source regression evidence, not fresh source421 factory acceptance. Current-head required checks and produced proof remain pending; the8192 Windows host gap, canonical installed Desktop owner gate, complete maintenance, real game/human, WorkUnit, Beta and release obligations remain open. Evidence: evidence/windows-current-dialog.v1.json and its hash-closed custody.

### PR421 integration and delivered coordination checkpoint

PR421 merged source32d68eb into dev361da48 after all twelve current required checks passed. Fresh Windows4/Linux3/macOS1 affected native configurations passed; current produced GUI proof retained two sessions,68 backend calls,8 fixture calls,2 effects and normal empty-job exits. Independent delivered coordination review47a6a5c2 verifies packet641cf7ee:713 artifacts,39 actual CLI commands,four bound controls,three intentional checkpoint deaths,repair suspend/revalidate/resume,empty Jobs and unchanged598-file portable closure. These facts supersede the historical pending421 wording above without rewriting its original receipts. Evidence: evidence/managed-install-coordination-integrated.v1.json and its metadata custody.

The delivered public result remains partial solely at the unreachable Windows8192-byte metadata boundary; the before-create invariant is reviewed source evidence. Canonical installed Desktop,complete maintenance,real game/human,WorkUnit,Beta and release gates remain open. The separate real-input inventory is read-only inspection,not game execution or route authorization.

### Reconciliation target alias authority preservation

Starting from dev361da48,the unchanged delivered CLI reproduced a root/. plan that omitted both external distinct-target and in-place conversion blockers while preserving all fixture bytes. This continuation changes only read-only target comparison and its focused regressions. Existing physical identity takes precedence over spelling; unavailable identity remains blocked and the caller's original target text remains in the desired state. Source trust,default authority and apply-unavailable semantics remain unchanged. Qualification and independent review for this successor are pending.
