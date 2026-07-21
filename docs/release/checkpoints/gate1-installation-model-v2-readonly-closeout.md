# Gate 1 installation model v2 read-only closeout

## Disposition

Gate 1 is accepted as a reviewed, deterministic, zero-write `dev` integration.
PR #37 merged the exact reviewed head
`c9ae60405d0b221faaba364be5f47e524649bb97` into `dev` at
`6ec47046d1b1f4ab8bddfcc27bcec76a774ff305`.

This checkpoint closes only
`FACMAN-INSTALLATION-MODEL-V2-READONLY-CLOSEOUT-01`. It does not claim that the
broader `FACMAN-MULTI-VERSION-INSTALL-LIFECYCLE-01` objective is complete.
Authenticated source and mutation work is transferred to the planned
`FACMAN-MANAGED-INSTALL-RECONCILIATION-01` WorkUnit.

## Accepted product behavior

Every supported registered installation class can be projected into a
schema-valid model-v2 view without rewriting the compatible v1 record. Desired
state is decoded into strong internal types and reconciled into a deterministic
plan whose identity binds:

- the canonicalization version;
- current installation evidence;
- desired state;
- ordered steps, blockers, risks, and rollback disposition;
- provider and policy revisions; and
- explicit revalidation requirements.

Plan effects use the closed `common.effects.v1` vocabulary. A caller-selected
source is a candidate, not authenticated evidence, and remains blocked pending
source inspection. Missing evidence never creates authority.

## Zero-write boundary

`installs describe` and `installs reconcile plan` are proven not to change:

- installation or selected source bytes;
- registry state;
- the compatible v1 installation reference;
- workspace, journal, or temporary operation state;
- candidate target roots; or
- source-root retention.

The response truth remains:

```text
mutation_executed = false
apply_available = false
mutation_authority_inferred = false
source_deletion_allowed = false
```

No reconciliation apply route was added.

## Exact-head validation

| Evidence | Result |
| --- | --- |
| PR CI `29799245632` | Pass |
| PR code-security `29799245642` | Pass |
| PR schema-check `29799245604` | Pass |
| PR security-policy `29799245629` | Pass |
| Canonical local full matrix | Pass |
| Portable AIDE Lite | Pass |

The local matrix passed 43/43 native tests and 359 Python tests with seven
declared optional skips. Strict validation passed with 250 schemas, 123 command
contracts, 121 registered routes, and 217 refusal codes.

## Exact merged-dev validation

| Evidence | Result |
| --- | --- |
| `dev` CI `29799938954` | Pass |
| `dev` code-security `29799939008` | Pass |
| `dev` schema-check `29799938962` | Pass |
| `dev` security-policy `29799938996` | Pass |
| Clean pinned three-repository reproduction | Pass |

The clean reproduction pinned Universal Launcher at
`7bd4425f0c35414f738159b45d8bec42edf70235`, Universal Setup at
`3f8489275077347c2918f3bb03614ec6431362ff`, and FacMan at the exact merged
`dev` revision. All repositories were detached and clean; provider and FacMan
configure, build, test, strict, and AIDE checks passed in 362.9 seconds. The
isolated source and build roots were removed.

## Continuing boundary

The active product WorkUnit is now
`FACMAN-INSTANCE-SPEC-AND-READINESS-01`: a minimal read-only vertical slice for
portable `InstanceSpec`, machine-local `InstanceBinding`, evidence-derived
`InstanceReadiness`, player-facing `InstanceView`, and explicit `menu` launch
intent by default.

Installation apply, instance preparation, permit issuance, real Factorio
execution, credentials, network access, host mutation, canonical `main`,
signing, publication, and Safe beta remain unpromoted.
