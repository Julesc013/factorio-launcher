# AIDE Target Truth

AIDE Lite is repository-local development governance, not FacMan runtime code.
Its target profile and memory must describe the implementation that exists at
the current revision; bootstrap-era plans are not allowed to outrank live
contracts, tests, or package evidence.

The executable root grammar is defined by `tools/structure_policy_check.py`.
`.aide/policies/flaunch-root-authority.yaml` mirrors that grammar and is checked
by `tools/aide_target_truth_check.py`. Retired roots are rejected in both
places, so a future task packet cannot legitimately recreate `source/`,
`data/`, `schemas/`, or `packaging/` at repository root.

The AIDE profile records four evidence authorities:

- `docs/architecture/threat_model.md` for trust zones and protected assets.
- `docs/architecture/safety_claim_ledger.md` for bounded claim levels.
- `docs/architecture/five_gate_proof_plan.md` for completed gates and stop rules.
- `release/index/workspace_lock.v1.toml` for reproducible sibling revisions.

If these authorities disagree, checks fail. Documentation alone does not
promote a capability: tests and revision-pinned evidence decide the claim.
