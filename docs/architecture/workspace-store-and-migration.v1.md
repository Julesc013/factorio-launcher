# Workspace store and migration seam

Status: bounded migration apply implemented and machine-qualified for the 0.1
alpha.5 foundation; public recovery acceptance remains open.

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
- `workspace.migration.apply` — journaled, no-clobber canonicalization for the
  two admitted legacy record shapes.

Apply currently admits only `canonicalize_legacy_install_ref` and
`canonicalize_legacy_instance_manifest`. It validates the complete plan before
effects, snapshots bounded source/target bytes, writes a durable operation
journal, publishes canonical records without clobbering an existing target,
preserves legacy sources, rolls an incomplete journal forward when it is safe,
and exposes conflict or recovery-required outcomes without guessing. Unknown
actions, identity migrations, future schemas, unsafe paths, corrupt journals,
and divergent targets fail closed. Inspect and plan never initialize or modify
a workspace.

## Proof boundary

The native and Python proofs cover UUID stability, Unicode paths, durable
creation, canonical and legacy reads, future-schema rejection, root
consistency, path escape refusal, repository paths, migration discovery,
non-mutation, journaled/idempotent canonicalization, restart recovery,
divergent-target conflicts, and fail-closed unsupported actions. The strict
`workspace-store-check` prevents legacy fallback paths or the literal local
identity from escaping the central store again.
