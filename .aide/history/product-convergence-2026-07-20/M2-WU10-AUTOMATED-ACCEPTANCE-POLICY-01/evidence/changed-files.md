# Changed Files

- `contracts/policy/m2_synthetic_portable_acceptance_policy.v1.json` freezes
  the non-executable synthetic lane, exact evidence criteria, revision
  separation, twelve negative controls, and bounded candidate authority.
- `contracts/schema/release/m2_synthetic_portable_acceptance_policy.v1.schema.json`,
  `m2_machine_acceptance_observation.v1.schema.json`, and
  `m2_machine_acceptance_result.v1.schema.json` distinguish policy,
  independently derived observation, and later recorded result.
- `tools/m2_wu10_machine_acceptance_check.py` adds the standard-library-only
  independent verifier and frozen-revision self-check.
- `tests/test_m2_wu10_machine_acceptance.py` builds a separate evidence fixture
  and proves all twelve required negative controls fail closed.
- `tools/strict_check.py` places policy validation on the strict floor while
  deliberately avoiding a live run or result during PR A.
- `release/index/project_status.v2.toml`, `tools/project_state.py`, generated
  project-state surfaces, and compaction tests record the policy-only state,
  pending fresh rerun, and unchanged unavailable apply boundary.
- `docs/release/checkpoints/m2-wu10-automated-acceptance-policy.md`, the
  checkpoint index, historical WU10 evidence note, and safety claim ledger
  document the separation-of-duties design without rewriting PR #25 history.
- `.aide/queue/active/M2-WU10-AUTOMATED-ACCEPTANCE-POLICY-01/` and queue/git
  reports record the bounded policy WorkUnit and task branch.

No current live-run result, `MachinePass`, human `Pass`, product mutation, or
authority promotion is included in this policy revision.
