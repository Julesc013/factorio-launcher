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

Every projection also carries explicit freshness dependencies. A dependency is
either an observed identity or an honest `not_observed` /
`must_be_probed_per_operation` marker; an absent probe is never presented as
positive evidence. `captured_at` remains null in this deterministic read-only
projection because no durable observation event is created merely by
describing an installation.

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

JSON-facing enum strings are decoded before comparison into the closed runtime
types `ManagementMode`, `DeploymentStyle`, `DataPolicy`, `IntegrationMode`,
and `UpdatePolicy`. An unknown value is an `invalid_request` compatibility
refusal; it cannot silently become `preserve` or another default.

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

The command emits `factorio.install_reconciliation_plan.v1`. It records:

- `current_evidence_digest`, the canonical digest of the complete evidence
  projection;
- `desired_state_digest`, the canonical digest of the decoded desired state;
- `plan_digest`, which binds both digests, ordered steps, blockers, risks,
  provider revisions, policy revision, and revalidation requirements;
- `plan_id`, the opaque identity derived from the plan digest;
- the canonicalization and effect-vocabulary versions.

Canonical JSON v1 uses recursively sorted object keys, compact separators,
UTF-8 encoding, and escaped solidus representation. This matches the parsed
transport representation rather than an internal builder's insertion order.
Independent tests reconstruct those exact bytes before hashing rather than
trusting the digest fields emitted by the planner.

Repeating the same request against the same evidence produces the same three
digests. Changing either evidence or desired state changes the plan digest.
The plan-only projection has no issuance event, so `created_at` is explicitly
null and is excluded from canonical identity.

Plan steps use a closed `step_kind` vocabulary and effect arrays drawn only
from `common.effects.v1`. Purpose is not encoded as an invented effect:
verification and rollback are step kinds, while `workspace_read`,
`workspace_write`, and `setup_preview` describe their relevant effect class.

The current command is deliberately plan-only:

- `mutation_executed` is always false;
- `apply_available` is always false;
- managed materialisation needs authenticated source evidence;
- an external root needs a distinct managed target;
- in-place ownership conversion is refused;
- FacMan-owned integration requires managed desired state;
- original roots are retained until reviewed acceptance;
- source deletion is never part of the generated plan.

## Source trust boundary

A source requirement, a caller-selected candidate, and authenticated source
evidence are independent facts. A raw `--source-ref` value produces
`selected_unverified`; it does not produce a verified source or remove the
materialisation blocker. Gate 1 recognizes the closed trust states
`unselected`, `selected_unverified`, `inspection_required`, `verified`, and
`unavailable`, but it deliberately provides no caller-controlled route to
assert `verified`.

Authenticated provider inspection belongs to the later managed-install
lifecycle. Until that provider exists, a dependent application step is
`blocked_pending_source_inspection`.

## Read-only proof boundary

`installs describe` and `installs reconcile plan` load an existing v1 record
and call pure projection/planning code. They have no Universal Setup gateway,
registry provider, transaction session, workspace `ensure`, or persistence
call in their handler path. Their result contracts state every applicable
no-write outcome explicitly, including no installation/source/registry
change, no Setup apply, no v1 rewrite, no workspace or journal creation, no
temporary state, and no source deletion.

Native tests prove digest determinism, evidence invalidation, desired-state
invalidation, typed compatibility refusal, canonical effects, and conservative
source trust. CLI tests snapshot the full installation and workspace before
and after repeated calls and prove that a missing workspace is not created by
either read-only command. These tests are portable product evidence; a local
installation library is only an additional canary.

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

1. Close the read-only projection and evidence-bound reconciliation-plan slice
   with schemas, command contracts, native tests, CLI tests, and live read-only
   evidence.
2. Transfer authenticated local source providers and source inspection results
   to `FACMAN-MANAGED-INSTALL-RECONCILIATION-01`.
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
