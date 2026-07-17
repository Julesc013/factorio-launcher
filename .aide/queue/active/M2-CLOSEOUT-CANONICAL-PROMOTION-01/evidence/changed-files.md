# Changed Files

- `docs/release/checkpoints/m2-public-integration-proof.md` binds the accepted
  MachinePass chain, exact-`dev`, promotion PR, canonical merge, identical tree,
  and exact-`main` workflow identities.
- `release/index/project_status.v2.toml` and generated project-state surfaces
  advance M2 to canonical promotion while keeping public-record merge and
  post-promotion `dev` synchronization pending.
- `tools/project_state.py` and its compaction tests recognize only the defined
  monotonic closeout phases and keep every higher-risk authority excluded.
- M3 remains authorized-next only, read-only, and plan-only until `dev`
  synchronization is independently merged and verified.
