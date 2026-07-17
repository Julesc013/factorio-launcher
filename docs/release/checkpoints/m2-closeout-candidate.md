# M2 Closeout Candidate

Status: M2 technical wave complete; canonical promotion pending.

## Closeout Basis

PR #28 merged the bounded M2-WU10 `MachinePass` result into `dev` at
`5250db1d17ac330f5ae0b672ccc7466431a1e4a2`. The versioned result remains
SHA-256 `a4a00a3f77b394f988a71f9eaa86de3c9c9b74a4051d1c2e3ad38f60b9ad8efa`
and explicitly records no human `Pass`.

M2-WU1 through WU9 provide the policy, public lifecycle, immutable evidence,
synthetic lifecycle, recovery, launcher handoff, FacMan workflow, generated
review, and adversarial proof layers. WU10 supplies the separate frozen-policy,
fresh-evidence, independently validated technical result.

## Completed Technical Scope

M2 establishes candidate status for new local managed portable installations
inside explicitly selected, policy-approved roots, plus verified repair, move,
uninstall, recovery, and Universal Launcher setup-state handoff for Setup-owned
installations.

The proof is synthetic and non-executable. It does not accept a real Factorio
archive and does not infer product execution safety.

## Preserved Exclusions

The closeout keeps real Factorio archive acceptance, existing-installation
mutation or adoption, Steam and Steam Cloud, network, credentials, registry,
shortcuts, elevation, system-wide installation, execution, `run.execute`, H1,
signing, publication, and Safe beta unavailable.

## Promotion Sequence

This task-branch checkpoint must pass the complete local and hosted matrix,
merge independently to `dev`, and pass exact-`dev` workflows. Only then may a
guarded `dev` to `main` PR be merged. Exact-`main` workflows, a public
integration checkpoint, and `dev` synchronization remain mandatory.

## M3 Boundary

After canonical M2 promotion, M3 may open only as existing-portable-installation
inspection and adoption planning. It permits read-only inspection and plan
generation, but no adoption apply, deletion authority, existing-installation
mutation, Steam adoption, execution, or other excluded capability.
