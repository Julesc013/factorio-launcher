# M2 Public Integration Proof

Status: canonical M2 promotion proven; public record and `dev` synchronization
pending.

## Accepted Chain

The bounded M2-WU10 result remains a technical `MachinePass`, never a human
`Pass`. PR #28 merged that result into `dev` at
`5250db1d17ac330f5ae0b672ccc7466431a1e4a2`. PR #29 then merged the independent
M2 closeout candidate at
`4afab65448831b05ab790957abf0e1798074ad1a`.

That exact closeout integration revision passed:

| Gate | Run | Result |
| --- | --- | --- |
| CI | `29567550655` | success |
| code-security | `29567550714` | success |
| security-policy | `29567550663` | success |

## Canonical Promotion

The guarded promotion dry-run reported ready with no blockers. Reviewed PR #30
bound and promoted exact `dev` head
`4afab65448831b05ab790957abf0e1798074ad1a`. Its exact-head workflows passed:

| Gate | Run | Result |
| --- | --- | --- |
| CI | `29568218139` | success |
| code-security | `29568218162` | success |
| schema-check | `29568218137` | success |
| security-policy | `29568218125` | success |

PR #30 merged to canonical `main` at
`bd0642951a4a3abfb2cc1916c8b9c2c4e81d880f`. The promoted `dev` head and
canonical merge share tree identity
`ee54dc220ed5fd80a9f450988033c5e29599a326`.

Canonical exact-head proof is complete:

| Gate | Run | Result |
| --- | --- | --- |
| CI | `29569007275` | success |
| code-security | `29569007270` | success |
| schema-check | `29569007323` | success |
| security-policy | `29569007290` | success |

## Authority Boundary

Canonical M2 promotes only bounded local managed portable setup candidacy for
newly created, explicitly selected, policy-approved targets. It does not accept
a real Factorio archive and does not authorize existing-install mutation or
adoption, Steam or Steam Cloud mutation, network, credentials, registry,
shortcuts, elevation, system-wide installation, execution, `run.execute`, H1,
signing, publication, Safe beta, or any broader authority.

M3 remains authorized-next and limited to read-only existing-portable
inspection and plan generation. Adoption apply, deletion, existing-install
mutation, and Steam adoption remain false. The active M2 closeout WorkUnit is
not closed by this candidate record; this record must first merge into `dev`,
then canonical `main` must be synchronized into `dev` and verified at the exact
sync revision.
