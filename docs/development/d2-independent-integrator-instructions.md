# D2 independent integrator instructions

## Status

These instructions are **ready for owner ratification**. They do not activate
delegated merging. `delegated_dev_merge`, protected-branch write, self-approval,
self-merge, tagging, credentials, signing, publication, route promotion, and
human-verdict authority remain false.

## Required records

Each proposed protected `dev` integration must have three immutable JSON
records validated against:

- `d2_implementation_attestation.v1.schema.json` from the implementation author;
- `d2_independent_assurance.v1.schema.json` from a logically independent reviewer;
- `d2_policy_admission.v1.schema.json` from a third control identity.

The three identities must be distinct. Every record must bind the same WorkUnit,
base revision/tree, head revision/tree, and sorted changed-path digest. The
assurance and policy records must bind their inputs by SHA-256. Records with
missing, duplicate, pending, cancelled, skipped, stale, or red required checks
are refused.

## Pre-merge procedure

1. Fetch without rewriting history and check out the exact proposed head in a
   clean worktree.
2. Recompute the base tree, head tree, ancestry, and changed-path digest.
3. Confirm that the exact head has not moved since review and that all required
   checks are successful on that head.
4. Confirm that all review threads and assurance findings are resolved or carry
   an explicit owner acceptance permitted by policy.
5. Confirm that high-risk surfaces received independent high-risk review.
6. Run the report-only validator:

   ```text
   py -3 tools/d2_integration_admission.py \
     --repo-root <clean-exact-head-worktree> \
     --output <premerge-report.json> \
     premerge \
     --implementation <implementation.json> \
     --assurance <assurance.json> \
     --policy <policy.json>
   ```

7. Refuse integration unless the report says `result = pass` and the repository
   contains an applicable owner-ratification record.
8. Use only the repository-approved, history-preserving ordinary merge path.
   Never squash, rebase, force-push, bypass protections, self-approve, or merge
   as the implementation author.

## Post-merge procedure

1. Record the exact merge revision and verify its ordered parents are the
   admitted base and head revisions.
2. Verify both admitted revisions remain ancestors of the merge revision.
3. Wait for every required post-merge check to finish on that exact merge
   revision. Red, pending, missing, duplicate, or stale evidence is a refusal.
4. Materialize a JSON check observation with `revision` and a nonempty `checks`
   array; each check has `name`, `state = success`, and the exact `revision`.
5. Run:

   ```text
   py -3 tools/d2_integration_admission.py \
     --repo-root <clean-post-merge-worktree> \
     --output <postmerge-report.json> \
     postmerge \
     --policy <policy.json> \
     --merge-revision <merge-sha> \
     --integration-ref refs/heads/dev \
     --checks <post-merge-checks.json>
   ```

6. If verification refuses, freeze further delegated integrations, preserve all
   evidence, and escalate to the owner. Do not rewrite the merge.

## D4 exclusion

D2 integration authority, if later ratified, is limited to exact-green protected
engineering integration. It cannot grant or exercise production credentials,
production signing, publication, route promotion, stable promotion, or a human
experience verdict.
