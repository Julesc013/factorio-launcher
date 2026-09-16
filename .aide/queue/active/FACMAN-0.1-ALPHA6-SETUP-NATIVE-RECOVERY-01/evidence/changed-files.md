# Changed source scope

Base: `412ab5aef55ecb771ee868ee46d1555d625de733`

This checkpoint changes only the active WorkUnit's admitted paths:

- `runtime/self_setup/` owns the durable composite setup journal, root-global
  admission, recovery review, and restart reconciliation.
- `apps/setup/` passes provider and native effects through the coordinator and
  supplies the ownership-bound Windows shortcut and registry implementation.
- `contracts/schema/facman/` and `contracts/policy/test_impact.v1.json` register
  and constrain the setup operation journal and its affected tests.
- `tests/native/` and `tests/test_self_setup_recovery_contract.py` cover the
  state machine, interruptions, recovery consent, concurrency, ownership,
  uninstall refusal, and portable behavior.
- The canonical release plan, queue state, generated project state, roadmap,
  README, TODO, and command/version catalogs record the active Alpha.6 scope.

The old `next` queue files are removed because the same WorkUnit is now present
under `active`; this is a queue-state move, not deletion of its plan.

## 2026-09-15 managed uninstall recovery slice

Base: `57a1745bac987a79658cfa825789ff48ec393329`

- `runtime/factorio/application/handlers/setup.cpp` adds strict coordinator
  decoding, deterministic inspect/apply planning, durable terminal postimage
  checkpoints, transaction leases, CAS projection, retry, and closure.
- `runtime/factorio/application/setup_gateway.{h,cpp}` adds read-only Universal
  Setup uninstall recovery inspection and exact provider journal, prior state,
  terminal state, audit, and target classification.
- `runtime/transaction/fl_transaction.{h,cpp}` adds a durable same-state
  checkpoint used before managed install-reference projection.
- CLI, command/request/refusal/capability contracts, the recovery response
  schema, goldens, and generated catalogs expose the transaction-bound route.
- Setup workflow, frontend parity, generated project-state, and Technical
  Preview views record the implemented recovery routes without changing
  release authority.
- `tests/native/m1_three_repository_system_proof.cpp` covers retired,
  retained-content blocked, no-effect, incomplete, corrupt/mismatched, drift,
  post-CAS retry, repeat, and live/orphaned lease behavior.

Independent review remediation is confined to command admission, the Setup
gateway recovery decoder/refusal adapter, and their two existing native proof
targets. No public request or response schema changed in that remediation.

## 2026-09-15 external maintenance and packaged recovery slice

Base: `0129f7ec6fa5864c40c6c6f4a3d3aab98b41f7ba`

- `apps/setup/` and `runtime/self_setup/` retain the raw provider package and
  maintenance launcher outside the managed install root, publish an exact
  digest receipt, validate every cache object through stable no-follow
  single-link reads, and bind install/repair/uninstall restart semantics to the
  durable journal.
- `runtime/platform/fl_file_io.{h,cpp}` adds Windows pinned stable inputs with
  pathname revalidation plus handle-owned no-replace publication and discard;
  `tests/native/fl_platform_io_smoke.cpp` exercises their substitution and
  foreign-destination boundaries.
- Windows integration registers exact external repair and uninstall command
  lines, migrates only the exact prior FacMan command shape as stale-owned, and
  keeps every other registration or shortcut classification foreign.
- The setup journal schema records installed-source and repair-source state and
  rejects incomplete completed installed-mode operations.
- The Windows installer manifest and product-candidate workflow exercise the
  produced self-contained setup, offline registered repair, registered
  uninstall, interruption/resume, paths containing spaces, and exact current
  user Start Menu and registry observations.
- Focused native, integration and Python tests cover cache substitution,
  provider source mismatch, retryable source inputs, registered-command
  quoting, legacy migration, terminal state, and clean successor uninstall
  after a definitive foreign-content refusal.
- Product documentation and generated command/version catalogs reflect the
  current contract identity. Hosted current-user package qualification remains
  required before this active WorkUnit can close.

## 2026-09-16 integrated source

PR #292 source `6ef1a9d3c95523b4e2b36aa5277ef498f555d523` and source/merge
tree `6fdbda15fd22db01c4de0794efed790a22b837ff` integrated to dev as
`c65c66ade1d4ca2c0c03b6b9aa78bfea2b977ae6`. The durable partial integration
receipt is `evidence/integration-checkpoint.json`; prior evidence remains
preserved and the WorkUnit remains active for update recovery.
