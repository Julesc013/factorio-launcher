# AIDE Target Truth

AIDE Lite is repository-local development governance, not FacMan runtime code.
Its target profile and memory must describe the implementation that exists at
the current revision; bootstrap-era plans are not allowed to outrank live
contracts, tests, or package evidence.

The executable root grammar is defined by `tools/structure_policy_check.py`.
`.aide/policies/facman-root-authority.yaml` mirrors that grammar and is checked
by `tools/aide_target_truth_check.py`. Retired roots are rejected in both
places, so a future task packet cannot legitimately recreate `source/`,
`data/`, `schemas/`, or `packaging/` at repository root.

The AIDE profile records four evidence authorities:

- `docs/architecture/threat_model.md` for trust zones and protected assets.
- `docs/quality/safety_claim_ledger.md` for bounded claim levels.
- `docs/quality/safety_proof_gates.md` for completed gates and stop rules.
- `release/index/workspace_lock.v1.toml` for reproducible sibling revisions.

If these authorities disagree, checks fail. Documentation alone does not
promote a capability: tests and revision-pinned evidence decide the claim.

## Reviewed checkpoint and live checkout truth

`release/index/project_status.v2.toml`, `release/index/current_state.v1.toml`,
and `.aide/memory/project-state.v2.json` are tracked reviewed-checkpoint truth.
Their compatibility revision fields describe the checkpoint accepted by that
review; they cannot self-referentially claim the hash of the commit that
contains them.

Live source truth is generated after checkout by
`tools/current_checkout_observation.py`. The versioned JSON and Markdown
artifacts derive the FacMan HEAD, branch, and dirty state from Git, compare an
optional expected CI SHA, and inspect passed Universal sibling roots against
the exact workspace-lock pins and canonical `origin/main` refs. Public provider
ABI versions are read from the locked pins' Git trees, not mutable worktree
files. No observed live SHA is maintained by hand in tracked project state.

The next breaking project-state schema revision should replace the live-sounding
compatibility field names. They remain in v1/v2 only to avoid changing existing
candidate consumers during the active operator gate.
