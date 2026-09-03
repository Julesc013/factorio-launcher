# FacMan Beta ruleset and tag-protection report

Status: report complete; GitHub settings unchanged  
WorkUnit: `FACMAN-BETA-RULESET-AND-TAG-PROTECTION-01`  
Observation: `2026-09-03T02:42:44Z`  
Repository: `Julesc013/factorio-launcher` (ID `1293124404`)

## Executive decision

The repository is ready to begin Alpha.6, but its machine-enforced GitHub rules
do not yet express the complete Beta/RC/stable release-train policy. This
WorkUnit is deliberately report-only: it observed the live settings, reconciled
them with checked-in authority law, and made no repository-setting, protected
ref, tag, release, or publication change.

The exact observation is retained in
`release/receipts/facman-beta-ruleset-and-tag-protection-observation.v1.json`.
The Phase 0 branch, worktree, and marker-owned-root retirement is retained in
`release/receipts/facman-phase0-workspace-cleanup.v1.json`.

## Effective current enforcement

| Concern | Observed state | Assessment |
| --- | --- | --- |
| Repository merge methods | Merge commit enabled; squash and rebase disabled | Normal merge is the only effective repository merge method |
| Branch ruleset methods | Merge, squash, and rebase listed | Inconsistent with repository-level settings; narrow before Beta.1 |
| Protected branches | `main`, `dev` | `release/0.1` is not yet included |
| Required checks | 11 exact contexts; strict current checks | Enforced |
| Conversation resolution | Required | Enforced |
| Stale-review dismissal | Enabled | Enforced |
| Approving reviews | Zero | Machine enforcement does not encode independent programme review |
| Force push and deletion | Denied | Enforced |
| Bypass | No actors; current user can never bypass | Enforced |
| Alpha tags | `v0.1.0-alpha.*` immutable | Enforced |
| Beta, RC, stable tags | No matching immutable ruleset | Must be added before exact Beta.1 allocation |

The branch ruleset has `do_not_enforce_on_create = true`. This is recorded as
an operator decision item: retain it only if the release-branch creation flow
needs the exception and the first protected update is demonstrably gated.

## Authority reconciliation

GitHub does not require one approving review. The programme policy is stricter
in a different dimension: an implementation author may not self-approve,
self-merge is false, delegated `dev` integration is inactive, and D2
integration authority is false. Therefore a green, mergeable pull request is
not automatically authorized for protected integration.

The correct boundary is:

> Technically green and mergeable does not mean authorized. Protected
> integration requires exact evidence and an explicit authorized human
> integration decision.

No review was invented or backfilled by this WorkUnit. Raising GitHub's review
count to one is not recommended unless an eligible independent reviewer exists;
otherwise a solo repository can be placed into a permanent technical deadlock.
The recommended assurance chain is:

1. exact implementation attestation;
2. exact independent assurance attestation;
3. exact policy/integration receipt;
4. explicit human integration decision; and
5. a formal external review when an eligible reviewer is available.

## Operator-facing Beta.1 settings proposal

Before allocating an exact Beta.1 candidate, apply a separately reviewed and
operator-authorized settings change that:

- protects `main`, `dev`, and `release/0.1`;
- permits normal merge commits only;
- retains strict current required checks, resolved conversations, and stale
  review dismissal;
- denies force pushes and deletion;
- retains zero bypass actors;
- makes `v0.1.0-alpha.*`, `v0.1.0-beta.*`, `v0.1.0-rc.*`, `v0.*`, and `v1.*`
  immutable against update and deletion; and
- re-observes the effective settings after application and before Beta.1.

The broad `v0.*` and `v1.*` protections intentionally overlap the train-specific
patterns. Existing Alpha tags remain immutable and must never be moved.

## Closeout and handoff

Phase 0 protected integrations, repository identity freeze, and report-only
governance assessment are complete. GitHub settings remain unchanged. The next
dependency-ready WorkUnit is
`FACMAN-0.1-ALPHA6-WORKSPACE-MIGRATION-RECOVERY-01`.

This report grants no Factorio execution, setup mutation, protected-ref
mutation, tagging, signing, notarization, publication, support, or Beta
allocation authority.
