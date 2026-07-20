# Changed files

This active work unit adds the first safe custom-library and local-data
conversion slice:

- `runtime/factorio/discovery/flb_factorio_discovery.*` discovers numeric
  version-library children and classifies installer layout, data routing,
  program/data separation, uninstall integration, and side-by-side risk.
- `runtime/factorio/instance/flb_factorio_local_data_import.*` implements a
  bounded, staged, no-follow, no-clobber import of program-local player data.
- Factorio application handlers and CLI contracts expose explicit-root scan,
  import-on-instance-create, and current layout classification during launch.
- `factorio.install_ref.v1`, the local-import schema, generated command
  metadata, CLI completions, and compatibility tests carry the new fields and
  command option without making additive install fields mandatory for readers.
- `runtime/factorio/installation/` projects compatible install references into
  independent installation-model-v2 evidence and generates deterministic,
  non-mutating desired-state reconciliation plans.
- The installation application module now owns install list, scan, import,
  inspect, describe, and reconcile routes rather than growing the central
  application switch.
- Versioned source, deployment, ownership/authority, data, integration,
  verification, provenance, filesystem, current-evidence, desired-state, and
  reconciliation-plan schemas define the additive contract boundary.
- `facman installs describe` and `facman installs reconcile plan` are generated
  across CLI metadata and frontend command catalogs with durable capability
  admission and conservative read-only defaults.
- Native and CLI tests prove management-class action decisions, missing-source
  blockers, deterministic plans, source/workspace invariance, and no target
  materialisation.
- Native discovery, Windows discovery, CLI, schema, architecture, project
  truth, product, workspace, and safety documentation cover the new behavior.
- `evidence/install-factorio-2.0.77.ps1` records the reviewed one-host
  conversion operation with fixed sources, hashes, targets, rollback, and the
  single allowed registry key.

The broader phase-0/phase-1 product convergence and execution-foundation
changes remain in the same uncommitted worktree and are not attributed to this
work unit alone.
