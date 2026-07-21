# M2 Public Integration Proof

Status: accepted; M2 closed; M3 opened read-only and plan-only.

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

M3 is limited to read-only existing-portable inspection and plan generation.
Adoption apply, deletion, existing-install mutation, and Steam adoption remain
false.

## Public Record and Dev Synchronization

PR #31 bound this public-integration record at task revision
`44687765815174db8afc1da6fa768f7a655a6290` and merged it into `dev` at
`1678cb6d3c9545f09c4ae729054f68cf0fbc7bf2`. That exact merge passed CI
`29571806755`, code-security `29571806753`, and security-policy `29571806738`.

PR #32 then merged ancestry-only synchronization candidate
`6fb4a0c96503f32ad9070a5c557f2fa1a31209c8`. The pre/post synchronization tree
remained `8487c87a097395186cccbcd13d929dd88d3b16fa`, while canonical `main`
became an ancestor of `dev`. The reviewed candidate passed push runs
`29572580045`, `29572580070`, and `29572580032`, plus PR runs `29572594866`,
`29572594857`, and `29572594830`.

The synchronized `dev` merge is
`51977de8120202958fc35776d284077b1fc027d3`. Its exact CI `29573335555`,
code-security `29573335458`, and security-policy `29573335488` all succeeded.
This completes M2 closeout and permits M3 to begin only within its read-only and
plan-only boundary.
