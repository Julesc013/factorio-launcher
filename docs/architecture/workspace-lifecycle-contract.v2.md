# Workspace lifecycle contract v2

Status: normative Alpha.6 implementation contract.

## Records

The lifecycle uses five versioned records and the existing FacMan operation,
attempt, request, idempotency, refusal, and recovery vocabulary:

- `facman.workspace_observation.v1` binds the admitted root object, authority,
  current format, workspace revision, inventory digest, health, compatibility,
  and available semantic actions.
- `facman.workspace_migration_plan.v2` binds a deterministic ordered effect set
  to an exact root identity and workspace revision. Its `plan_digest` covers all
  effect inputs and dispositions.
- `facman.workspace_migration_operation.v1` correlates one durable operation,
  attempt, request, idempotency key, plan, phase, terminal classification, and
  recovery boundary.
- `facman.workspace_migration_journal.v2` durably records bound inputs, staged
  and committed outputs, verification, completed steps, and rollback retention.
- `facman.workspace_recovery_projection.v1` is the sole frontend-facing law for
  safe and unavailable recovery actions. Frontends never inspect journals.

## State law

The admitted lifecycle states are:

```text
uninitialized -> healthy
healthy -> migration_available -> plan_ready -> confirmation_required
confirmation_required -> applying -> verifying -> completed

any pre-effect refusal -> refused_before_effects
interruption -> interrupted_recoverable
interrupted_recoverable -> resume_available | rollback_available | recovery_required
resume_available -> applying
rollback_available -> rolled_back
unprovable effect boundary -> outcome_unknown
```

`outcome_unknown` is exceptional. A valid local journal classifies effects as
`no_effects`, `staged_only`, `partially_committed_recoverable`,
`fully_committed`, or `rolled_back`.

## Admission invariants

Apply is refused before effects unless the request supplies the exact plan
digest, expected workspace revision, expected root identity, explicit
confirmation, request ID, operation ID, attempt ID, and idempotency key. The
implementation reacquires and revalidates the root and inputs under its
exclusive mutation lock. A changed root, revision, input, or idempotency
binding is a conflict. Unknown content is preserved. Future formats are never
downgraded. Startup, help, version, observation, and plan operations do not
create a workspace or run migration effects.

The journal uses only registered migration effect kinds. It does not execute
scripts or infer filesystem-wide atomicity. A rollback is advertised only
while its bound backup, root identity, workspace revision, and target inputs
remain verified. Corrupt evidence disables mutation and keeps support export
available.
