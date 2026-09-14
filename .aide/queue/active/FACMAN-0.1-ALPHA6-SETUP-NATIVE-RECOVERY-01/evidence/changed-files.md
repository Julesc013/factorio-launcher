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
