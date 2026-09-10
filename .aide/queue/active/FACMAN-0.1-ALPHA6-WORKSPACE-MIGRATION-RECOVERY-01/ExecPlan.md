# Workspace package recovery remediation

Continue the already-active workspace WorkUnit at exact dev base
37f7c542d18d27af7daa03c505e1574260fa52cc on the helper-owned branch
task/facman-workspace-package-recovery-01. Preserve the primary GTK worktree.
The current user instruction authorizes implementation, remediation, tests,
documentation, scoped commits and checked normal integration.

## Observed failure and correction

Product-candidate run 34042284090 at source eeb65fe365f9120ec884f9bd88a4a3a92b72f6a3
failed damaged-backup rollback qualification on Linux and macOS. A native WSL
ext4 reproduction returns workspace_migration_apply_unproven from the staging
binding check before rollback's recovery-required check. The Windows job is
reported green but its complete log shows BOTH portable and installed lifecycle
commands failed identically; later successful commands masked their exit codes.
The earlier external branch-plan statement that Windows qualification passed is
superseded by this complete-log evidence. No platform lifecycle pass is claimed.

## Scope and intended changes

1. Preserve the existing damaged-backup and staging-corruption public oracles.
   Classify divergent staging according to rollback or forward recovery while
   preserving journal/source/plan/root proof, no-follow reads and refusal before
   any target or journal mutation. Forged bindings remain apply_unproven.
2. Add behavioral regressions for corrupt and missing retained backup/staging
   evidence; verify original, target and journal bytes survive refusals.
3. Include bounded full-error diagnostics when the package oracle fails.
4. Extend this WorkUnit's exact allowed scope to the existing
   .github/workflows/product-candidate.yml and its regression tests to make every
   Windows native command failure terminate its step. This repairs the observed
   qualification gate; it does not install a workflow or change permissions,
   triggers, signing, publishing, provider pins or release authority. Run the
   AIDE GitHub report-only planning checks and independent source review.
5. Run affected Python/native/strict validation, review the exact source and
   commit/push a scoped task checkpoint. Sync with dev through a normal merge,
   obtain hosted checks, integrate normally and rerun the exact three-platform
   candidate workflow. Retain the failed run and all source/artifact bindings.

## Resources and remaining gates

Use the existing marker-owned facman-0.1-al-230b4b08ab qualification root.
Independent no-hardlink diagnostic clones bind exact FacMan/provider sources.
The Windows mount is correctly refused for workspace locks; synthetic Linux
workspaces use newly created /tmp ext4 directories with explicit ownership
receipts retained in the controller root. No user workspace or game is used.
Keep at most two secondary worktrees. Retain prior diagnostics; perform no
unplanned cleanup. This intermediate proof uses the tracked alpha.5 version;
full Beta1 qualification and human acceptance remain separate gates.

## Validation refinement

Independent review reproduced four combined corrupt-staging plus forged
root/plan cases. Defer the first staging error until all semantic journal
bindings and the remaining live plan have been verified; retain no additional
payload copies. The behavioral regression now covers 24 combinations, including
missing/corrupt source/target staging and valid/forged root/forged plan bindings.

The first broader WSL run passed 25/26 tests; its read-only permission test ran
as root and correctly exposed an unsuitable test identity. The final run uses
existing uid/gid 65534 with no supplementary groups in a fresh owned temporary
root: all 26 tests, native workspace smoke and all 11 lifecycle cases pass.
No account creation or machine configuration change was needed. Diagnostic
binaries bind exact tracked provider pins but do not constitute package proof.

The Windows command-propagation regression fails in both old workflow steps
and passes with the explicit native-error preferences. 35 affected Windows
contract/workflow tests pass. The first strict check caught an unclassified
platform skip; the Windows-only test now uses the existing obligation classes.
Final source review, commit/integration and fresh package qualification remain
required before closing this WorkUnit.

## Completed source and package acceptance — 2026-09-07 AEST

The final source review and12 hosted checks passed at87aa7dc0662acff7fce5ee7368a3e16e077cbc6c. Candidate run34048385176 qualified all six portable/installed assets and66 lifecycle cases across Windows, Linux and macOS before normal PR252 integration atcd2936e79af79df0ddb11f758e149ac38745beea. The integrated tree exactly equals the qualified tree06071b5b2d1285aeee874b5e8772ced3811e5f14. This fresh result supersedes the earlier failed run, whose logs and local failures remain retained. No failed historical check is reclassified.

See evidence/package-integration-closeout.json and its raw custody ZIP, including the exact reviewed source patch, complete candidate logs and original package manifests. The merged owned worktree was retired; the task remote branch is absent. The candidate retainsalpha.5 identity, existing provider pins and no release/human/game authority.
