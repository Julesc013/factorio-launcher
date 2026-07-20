# Installation model and reconciliation

FacMan manages a Factorio lifecycle, not a folder label. “Portable”,
“installed”, “managed”, and “integrated” are not mutually exclusive states and
must not be compressed into one enum.

## Independent axes

Every registered installation is projected into these records:

| Axis | Record | Question answered |
| --- | --- | --- |
| Source | `factorio.source_reference.v1` | Where can the application closure be reconstructed from? |
| Deployment | `factorio.deployment_record.v1` | What layout is present at which root? |
| Ownership and authority | `factorio.ownership_authority.v1` | Who owns it, and who may mutate it? |
| Data routing | `factorio.data_routing_policy.v1` | Where can mutable player data be written? |
| Integration | `factorio.integration_record.v1` | Which vendor, OS, or external-manager overlay exists? |
| Health | `factorio.verification_snapshot.v1` | What has actually been verified and what needs attention? |
| Provenance | `factorio.provenance_record.v1` | Which version, revision, and verification identity are bound? |
| Filesystem capability | `factorio.filesystem_capability.v1` | Which local filesystem assumptions must be re-probed? |

`factorio.install_current_evidence.v1` composes those axes. It is evidence,
not desired state and not mutation authority.

The existing `factorio.install_ref.v1` remains the stored compatibility
record. `facman installs describe <id> --json` projects it into
`factorio.installation_model.v2` without rewriting the workspace. Missing
authority fields default to read-only.

## Management classes

| Class | Meaning | Application mutation |
| --- | --- | --- |
| Managed | Materialised through reviewed Universal Setup state | Planable; apply remains separately gated |
| Adopted | Existing standalone tree with explicit ownership proof | Planable; apply remains separately gated |
| Reference | Registered foreign or operator-owned tree | No in-place mutation; clone or adopt first |
| External | Steam, package manager, or another lifecycle owner | Delegate repair, update, move, and uninstall |
| Unknown | Identity or ownership is incomplete | Inspect and diagnose only |

Registration never grants ownership. A legacy string saying `managed` is also
insufficient: FacMan requires both bound setup state and a verification
identity before it reports setup proof. Even then, Universal Setup remains the
mutation owner.

## Desired state

`factorio.install_desired_state.v1` keeps version, source, target,
management mode, deployment style, data policy, integration, and update policy
independent. Each field can be preserved or explicitly changed.

```powershell
facman installs reconcile plan factorio-2-0 `
  --management managed `
  --deployment-style standalone_directory `
  --data-policy instance_local `
  --integration facman_owned `
  --update-policy pinned `
  --source-ref vendor-installer:2.0.77 `
  --target D:\Games\Factorio\2.0-managed `
  --json
```

The command emits `factorio.install_reconciliation_plan.v1`. Its plan identity
is a SHA-256 of canonical desired state, steps, blockers, and risks. Repeating
the same request against the same evidence produces the same identity.

The current command is deliberately plan-only:

- `mutation_executed` is always false;
- `apply_available` is always false;
- managed materialisation needs a selected source;
- an external root needs a distinct managed target;
- in-place ownership conversion is refused;
- FacMan-owned integration requires managed desired state;
- original roots are retained until reviewed acceptance;
- source deletion is never part of the generated plan.

## Reconciliation boundary

The reconciler decides what differs and what must happen. It does not install,
copy, delete, invoke an uninstaller, edit the registry, or infer authority.

```text
current read-only evidence + desired state
  -> deterministic differences, blockers, risks, and ordered steps
  -> source provider inspection
  -> Universal Setup preview and transaction
  -> staged application closure
  -> Factorio-specific verification
  -> dependent-instance validation
  -> optional integration provider
  -> reviewed switch with retained rollback
```

Provider adapters perform mechanisms. Policy stays in FacMan and mutation
authority stays in Universal Setup. This separation allows an official
archive, vendor installer, existing tree, Steam reference, and future package
manager to share the model without pretending they support the same actions.

## Compatibility and migration

This is an additive transition:

1. Continue reading `factorio.install_ref.v1` and older optional-field records.
2. Project absent evidence conservatively rather than inventing facts.
3. Write no v2 persisted installation record until migration inspect/plan,
   backup, apply, journal, and recovery contracts exist.
4. Keep existing command spellings and machine-readable v1 responses stable.
5. Introduce a persisted v2 record only when source and setup identities can be
   durably bound and revalidated.

## Delivery path

1. Close the read-only projection and reconciliation-plan slice with schemas,
   command contracts, native tests, CLI tests, and live read-only evidence.
2. Add authenticated local source providers and source inspection results.
3. Add explicit clone/adoption plans with snapshots and dependent-instance
   impact analysis.
4. Add transaction-backed apply through narrow Universal Setup ports, first
   for new side-by-side managed roots.
5. Add repair, move, reinstall, update/downgrade, detach, and uninstall as
   desired-state transitions with recovery proofs.
6. Add optional integration providers without making integration a condition
   of application ownership.
7. Add GUI task flows after the contracts and recovery behavior are proven.

The local 2.0.77 conversion is evidence for these contracts. It is not a
shortcut granting general installer execution or lifecycle apply authority.
