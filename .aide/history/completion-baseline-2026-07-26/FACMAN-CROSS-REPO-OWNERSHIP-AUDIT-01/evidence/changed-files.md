# Ownership audit changed-file intent

- `release/index/component_ownership.v1.toml` is the machine-readable
  repository, component, authority, branch-model, and incubator inventory.
- `tools/component_ownership_check.py` enforces coverage and extraction
  obligations.
- `tools/cross_repo_check.py` and `tools/strict_check.py` include the semantic
  ownership check.
- `docs/architecture/component_ownership.md` explains the permanent boundary,
  branch models, and non-goals.
- Focused tests reject missing ownership, ambiguous authority, and incomplete
  incubator metadata.
- Project truth records the post-candidate ownership checkpoint without
  promoting runtime authority.

No runtime implementation moved during this audit.
