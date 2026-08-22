# Changed files

## Canonical identity and policy

- `release/index/repository_identity.v1.toml`
- `release/index/branch_policy.v1.toml`
- `release/index/product.v2.toml`
- `REUSE.toml`
- `SECURITY.md`
- `contracts/schema/release/remote_source_closure.v2.schema.json`
- `contracts/schema/release/spdx_document.v2.3.repository_identity.v1.schema.json`

## Identity consumers and validation law

- `tools/repository_identity.py`
- `tools/release_compiler/source_observation.py`
- `tools/project_state.py`
- `tools/source_closure_admission_check.py`
- focused identity, checkout, release, provenance, branch-policy, and target-truth tests

## Current truth and planning

- `release/index/project_status.v2.toml`
- `release/index/plan.v1.toml`
- generated current-state, AIDE memory, README, roadmap, and checkpoint-index projections
- `docs/release/checkpoints/facman-technical-preview-checkpoint-01.md`
- `docs/migrations/2026-08-facman-repository-rename.md`
- AIDE queue records for this WorkUnit and the superseded identity target

Historical evidence under `.aide/history/`, versioned v1 source-closure code and schema,
and previously accepted evidence/checkpoint payloads were not rewritten.
