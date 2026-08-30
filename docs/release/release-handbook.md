# Release handbook

This handbook operationalizes the machine-readable train and ledger contracts.
It cannot grant authority that those contracts, repository policy, and the
required human receipt do not grant.

Use `.github/RELEASE_TEMPLATE.md` for the review packet and the closed schemas
under `contracts/schema/release/` for machine evidence. The template is a view;
the immutable candidate, receipt, ledger, and withdrawal records are truth.

## Candidate construction

1. Select one exact milestone and freeze its admitted capability/frontend
   matrix. Missing admitted rows block; explicitly excluded rows do not.
2. Bind an exact clean source commit and tree, provider source/package/ABI/
   contract identities, toolchain, target profile, and release-resolution root.
3. Require empty-clone source closure and clean worktrees. Local package
   preflight refuses mismatched provider identities before creating or cleaning
   any package output.
4. Run Debug and Release native tests, the full Python and AIDE suites, strict
   checks, required sanitizer/fuzz/coverage/ABI lanes, negative controls, and
   every admitted target package proof with zero required skips.
5. Build only through the canonical resolution, verified stage, CMake install
   components, and profile-driven package pipeline. Rebuild independently and
   compare normalized artifacts and final digests.
6. Verify layout, relocation, read-only root, integrity manifest, SBOM,
   licenses, provenance, runtime closure, accessibility, recovery, migration,
   rollback, and clean-machine journeys.
7. Produce the candidate and assurance records. Sol/control accepts scope and
   policy, Terra/implementation supplies the exact change and evidence, and
   Luna/assurance independently attempts to falsify the claims. A red required
   gate has no automatic waiver.
8. Preserve untagged snapshot candidate evidence out of tree. Write an
   append-only ledger entry only for a tagged alpha, beta, RC, or stable
   identity. Alpha entries need no experiential receipt; beta, RC, and stable
   entries require the exact current human receipt defined by the train.

## Authority boundaries

Autonomy may perform read-only observation, bounded task implementation,
tests, and draft review state. The active three-key alpha policy additionally
permits only exact protected-`dev` alpha allocation and immutable annotated tag
creation. Normal protected `dev` integration remains separately inactive.

Humans retain public beta/stable acceptance, production credentials, signing,
publication, legal acceptance, real player verdicts, route capability, route
promotion, and non-disposable external effects. Human validation occurs at the
end of each release train, not after the entire programme.

## Publication and withdrawal

Hashes prove integrity, not publisher authenticity. Provenance records build
inputs, not a trusted publisher. Alpha tags require the exact bounded tag gate.
Signing, notarization, GitHub releases, uploads, support activation, and
publication remain separate and require the authority declared for that
release class.

Tags and published assets are immutable. A defective release is superseded,
withdrawn, or revoked through a new append-only ledger record; it is never
retagged or silently replaced. See the withdrawal law in
`release/index/version_train.v1.toml` and `release/ledger/README.md`.

Current repository state remains unsigned, unpublished, unsupported as a
stable release, and unauthorized for Factorio execution or Setup mutation.
