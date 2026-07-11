# Workspace store and migration seam

Status: implemented locally for R3.4 WorkUnit 6.

## Authority

`runtime/workspace` is the single persistence boundary for workspace metadata,
install references, instance manifests, modset locks, and transaction journal
locations. Domain modules receive decoded records; they no longer choose between
canonical and legacy persisted paths or decode those records independently.

`WorkspaceLayout` derives managed paths for:

- canonical and legacy install references;
- canonical and legacy instance manifests;
- instance and shared modset locks;
- transaction journals;
- diagnostic output names.

Every identifier-bearing path goes through the existing managed-path policy.
Persistent reads use a bounded no-follow stable handle, parse through the core
JSON adapter, revalidate object identity, enforce the known schema/version, and
reject unknown future versions. New records use exclusive durable output.

## Typed repositories

The store exposes `InstallRepository`, `InstanceRepository`,
`ModsetRepository`, `TransactionRepository`, and `WorkspaceRepository`.
Canonical formats remain unchanged:

- `factorio.install_ref.v1` under `installs/refs/`;
- `factorio.instance.v1` under `instances/<id>/instance.v1.json`;
- `facman.factorio.workspace.v1` with layout version 1.

Read compatibility remains centralized for `installs/installed_state/`,
`usk.installed_state.v1`, and `instance.manifest.json`. A legacy read does not
rewrite, remove, or canonicalize its source.

## Workspace identity

A newly initialized workspace receives an OS-random RFC 4122 version 4 UUID.
The former literal `local` identity is accepted only as legacy input and is
reported as a migration action. Transaction begin consumes the stored workspace
identity instead of supplying a process-local default.

## Migration commands

The command boundary exposes:

- `workspace.migration.inspect` — read-only discovery;
- `workspace.migration.plan` — read-only ordered actions with explicit backup
  and journal requirements;
- `workspace.migration.apply` — no-op success only when no actions exist.

When changes are required, apply fails closed with
`workspace_migration_apply_unproven`. This is intentional: no real persisted
format migration may execute until a later reviewed WorkUnit provides and tests
transaction-specific backup, journal, interruption, and recovery behavior.
Inspect and plan never initialize or modify a workspace.

## Proof boundary

The native smoke covers UUID stability, Unicode paths, durable creation,
canonical and legacy reads, future-schema rejection, root consistency, path
escape refusal, repository paths, migration discovery, non-mutation, and
fail-closed apply. The strict `workspace-store-check` prevents legacy fallback
paths or the literal local identity from escaping the central store again.
