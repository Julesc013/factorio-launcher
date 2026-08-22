# FacMan repository rename migration

Status: deferred capability; inactive during the 0.1 release train.

The current canonical repository is `Julesc013/factorio-launcher`, numeric GitHub
repository ID `1293124404`. `FacMan` remains the product name, executable name, and
stable repository role. `Julesc013/facman` is only a preferred future slug pending beta
brand validation; it is not a current remote, legacy redirect, or release source.

The authoritative current record is `release/index/repository_identity.v1.toml`. This
document preserves a bounded migration capability without authorizing or scheduling the
rename.

## Decision gate

Do not activate this migration before `0.1.0-beta.1`. Activation requires:

- a small user naming and discoverability test;
- basic legal and name-clearance review;
- an explicit decision to rename;
- a reviewed WorkUnit and operator-approved GitHub action packet;
- exact protected-ref, ruleset, integration, and all-refs backup receipts.

Until that gate passes, current source closure, provenance, branch policy, support links,
and release metadata must use `Julesc013/factorio-launcher`. A clone or observation of
`Julesc013/facman` is classified `deferred_future` and cannot satisfy current canonical
source closure.

The migration never grants tagging, signing, release, publication, Factorio execution,
Setup mutation, credential, or unrelated network authority.

## Already-complete preparation

Current tooling separates stable role `facman` and numeric repository ID `1293124404`
from slugs, remotes, and local directory names. Both `factorio-launcher` and `facman`
remain supported local workspace names. Universal Launcher and Universal Setup roots
remain explicit and are never inferred from the FacMan directory name.

The immutable v1 source-closure engine, schemas, evidence, and historical checkpoints
retain their original locators. They must not be rewritten to simulate a future rename.
A later accepted rename must introduce successor current-policy records where locator
identity changes.

## Future activation sequence

1. Freeze integrations and capture the exact numeric repository ID, `main` and `dev`
   refs and trees, rulesets, open pull requests, workflows, environments, variables,
   secrets by name only, webhooks, GitHub Apps, deploy keys, Pages settings, releases,
   tags, and external callers.
2. Create and verify an all-refs Git bundle and a separate remote-ref snapshot.
3. Rename `Julesc013/factorio-launcher` to `Julesc013/facman` without changing repository
   visibility or numeric identity.
4. Re-read GitHub state and require repository ID `1293124404`, the intended new slug,
   unchanged protected refs and rulesets, and a complete integration inventory.
5. Update current identity, policy, support, provenance, and source-closure records in a
   reviewed successor WorkUnit. Preserve historical artifacts unchanged.
6. Verify the GitHub redirect and both supported local workspace layouts.
7. Re-run fresh three-repository source closure and the exact Windows candidate
   qualification against the accepted post-rename source. Pre-rename green evidence
   cannot qualify the new locator.

## Rollback and recovery

If numeric identity, refs, rulesets, integrations, or clone proof differ, stop
publication and restore the previous repository name through a separately approved
GitHub action. Restore local remotes from the captured snapshot, verify the all-refs
bundle, and retain the failed attempt as historical evidence.

A working redirect is compatibility evidence only. It is never sufficient proof that a
rename completed correctly.
