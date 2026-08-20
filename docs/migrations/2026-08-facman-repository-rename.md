# FacMan repository rename migration

Status: implementation candidate; the GitHub repository has not been renamed.

This migration separates the stable repository role `facman` and GitHub repository ID
`1293124404` from mutable slugs, remotes, and local directory names. The canonical target
is `Julesc013/facman`; `Julesc013/factorio-launcher` is retained only as the pre-rename
live remote and future GitHub redirect. The authoritative records are
`release/index/repository_identity.v1.toml` and this migration plan.

## Preconditions

The rename must not start until this WorkUnit is independently reviewed and present on
both protected `dev` and protected `main`. Immediately before the rename, record the
exact numeric repository ID, `main` and `dev` refs and trees, rulesets, open pull requests,
workflow runs, environments, variables, secrets by name only, webhooks, GitHub Apps,
deploy keys, pages settings, releases, tags, and external callers. Create and verify an
all-refs Git bundle and a separate remote-ref snapshot. Stop if the numeric repository ID
does not remain `1293124404`.

The rename itself requires an operator-approved GitHub action packet. It does not grant
tagging, signing, release, publication, Factorio execution, Setup mutation, credential,
or network authority.

## Current consumers

Current locks, the release compiler, source observations, the successor v2 source-closure
envelope, the v2 reproducible-workspace discovery tool, component ownership, branch
policy, generated command metadata, provenance, project setup, and preview-obligation
construction use stable roles or values derived from the identity manifest. Both `facman`
and `factorio-launcher` remain valid local FacMan directory names. Universal Launcher and
Universal Setup roots stay explicit and are never guessed from the FacMan directory name.

The immutable v1 proof engine and schema retain the old locator. The v2 envelope
deliberately recognizes that remote as `legacy_redirect`: it is usable for pre-rename
observation and compatibility tests, but it cannot satisfy final canonical FacMan source
closure. A fresh v2 proof after the rename must observe
`https://github.com/Julesc013/facman.git` and the unchanged numeric repository ID.

## Retained old-name classifications

Occurrences of `factorio-launcher`, `factorio_launcher`, or the old URL are retained only
when they are one of these classes:

- `workspace_alias`: supported pre-existing local directory layout;
- `redirect_compatibility`: GitHub redirect input or negative-control fixture;
- `versioned_contract_namespace`: published JSON Schema `$id` or another versioned
  contract locator whose in-place rewrite would change a contract identity;
- `immutable_evidence_or_checkpoint`: historical run, pull request, SBOM, attestation,
  source-closure proof, changelog, or accepted checkpoint;
- `abi_cmake_or_runtime_compatibility_identity`: a stable programmatic field, target,
  cache key, CMake project, or ABI symbol that is not a repository slug.

New current-policy uses of the legacy slug are prohibited. Historical artifacts are not
rewritten; a successor schema or proof version is required when canonical locators become
part of the evidence identity. Current SBOM generation therefore uses
`spdx_document.v2.3.repository_identity.v1.schema.json`, while the published SPDX schema
with the old namespace remains unchanged.

## Rename sequence

1. Freeze integrations and verify the protected `dev` and `main` tips match the accepted
   pre-rename receipts.
2. Capture and verify the all-refs bundle, ref snapshot, and external-integration inventory.
3. Rename the GitHub repository from `factorio-launcher` to `facman` without deleting the
   redirect or changing repository visibility.
4. Re-read the repository through the GitHub API and require numeric ID `1293124404`,
   canonical slug `Julesc013/facman`, unchanged refs, unchanged rulesets, and unchanged
   integration inventory.
5. Update local origin URLs to the canonical remote, preserving either supported local
   directory name. Do not rename unrelated worktrees or sibling provider directories.
6. Run the canonical three-repository source closure from a fresh checkout under both
   FacMan directory layouts. The legacy remote must fail the final-canonical check.
7. Re-run all required workflows and exact Windows Technical Preview qualification on the
   post-rename accepted source. Pre-rename green evidence cannot promote the new locator.

## Rollback and recovery

If the numeric ID, refs, rulesets, integrations, or canonical clone proof differ, stop
publication and restore the previous repository name through an operator-approved GitHub
action. Restore local origin URLs from the captured snapshot, verify the all-refs bundle,
and record the failed attempt without rewriting it. A redirect resolving successfully is
compatibility evidence only; it is not proof that the rename completed correctly.

No release may be tagged or published during rollback. Resume candidate qualification
only after the repository identity and protected refs are independently reconciled.
