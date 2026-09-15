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
