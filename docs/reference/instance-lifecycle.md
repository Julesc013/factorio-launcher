# Instance lifecycle

R3.7 provides a typed, reversible lifecycle for managed Factorio instances:

- `instances.inspect <id>` reports identity, install/profile/template selection,
  effective paths and configuration state, modset/save/snapshot summaries,
  pending transactions, size, last-modification evidence, and the explicit
  `not_granted` run-authority state;
- `instances.verify <id>` checks the manifest and immutable ID/path binding,
  install reference, regenerated effective configuration, link-free managed
  roots, modset state, bounded save archives, unexpected top-level content,
  run lock, ownership, and transaction state without repairing anything;
- `instances.diff <left> <right>` compares selected settings and file hashes
  while omitting locks, caches, logs, crash files, and transaction material;
- `instances.clone <source> <destination>` performs stable, singly-linked file
  reads, cross-volume copy/hash verification, regenerated destination config,
  owned staging, and a no-clobber transaction commit;
- `instances.rename <id> --name <display-name>` changes only the display name.
  The immutable instance ID and managed directory do not change;
- `instances.archive <id>` refuses unresolved run locks and transactions, then
  atomically moves all content to
  `workspace/trash/instances/<transaction-id>-<instance-id>/` and adds a
  verified archive metadata/hash record;
- `instances.restore <archive-id>` verifies the complete owned trash record,
  copies it through destination-owned staging, regenerates environment-specific
  paths, and commits without clobbering an existing instance. `--new-id` may be
  used for an explicit alternate immutable ID.

There is no `instances.purge` command and lifecycle results contractually report
`hard_delete_available: false`. Restore preserves the owned trash record. Only
recognized operation-owned staging may be removed during pre-commit cleanup.

The `FACMAN_INSTANCE_LIFECYCLE_FAULT` variable is a proof hook used by tests at
validation, copy, verification, pre-commit, post-commit, and archive-metadata
boundaries. Post-commit faults are reported as recovery-required and retain a
recognizable committed target; they never authorize automatic repair.

Snapshot comparison is intentionally unavailable until the separate snapshot
work unit establishes its portable manifest and hash contract.

## Gate 2 read-only player projections

Two additive commands provide the instance-centric player model without
changing the R3.7 lifecycle record or granting lifecycle authority:

- `instances.describe <id> [--intent menu]` returns
  `factorio.instance_view.v1`, which composes a portable `InstanceSpec`, local
  `InstanceBinding`, evidence-derived `InstanceReadiness`, and player summary;
- `instances.readiness <id> [--intent menu]` returns the canonical readiness
  component directly.

The default and only accepted Gate 2 intent is `menu`. Other registered launch
intents receive `unsupported_launch_intent`; no save is inferred. Both commands
are deterministic `workspace_read` operations. They do not rewrite
`factorio.instance.v1`, prepare content, issue a permit, access credentials or
the network, invoke Setup, or execute Factorio. See
[`../architecture/instance_model_and_readiness.md`](../architecture/instance_model_and_readiness.md)
for the component, digest, evidence, and readiness contracts.
