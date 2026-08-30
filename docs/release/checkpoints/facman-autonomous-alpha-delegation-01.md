# FacMan bounded alpha-tag delegation

Date: 2026-08-27 (Australia/Sydney)

Status: review candidate. The policy and implementation are locally present on
`task/facman-autonomous-alpha-delegation-01`; they are not effective from
protected `dev`, no alpha tag was created, and no public release was published.

## Outcome

This WorkUnit activates one narrowly bounded machine effect after protected
integration: allocate the next never-used `0.1.0-alpha.N` version and create one
unsigned annotated `v0.1.0-alpha.N` tag on the exact current protected `dev`
commit. It does not authorize protected-branch integration, self-merge,
credentials, signing, publication, beta/RC/stable tags, route effects, support
activation, or a human verdict.

The gate binds all of the following before any tag API call:

- exact clean source commit and tree equal to current protected `dev`;
- tracked version/build identity and an exact qualified, reproducible,
  unpublished, unsigned candidate record;
- canonical-main-reachable Universal Launcher and Universal Setup identities;
- three distinct passing implementation, assurance, and control attestations;
- the exact required GitHub check set, successful on the source commit through
  GitHub Actions app ID `15368`, no unknown required skips, and a maximum
  observation age of 24 hours;
- authenticated current GitHub dev-ref, check-run, and effective branch-rule
  observations;
- the next never-used number across existing tags and append-only ledger
  directories; and
- an active GitHub tag ruleset with no bypass actors, no exclusions, the exact
  include `refs/tags/v0.1.0-alpha.*`, and both `update` and `deletion` rules.

The workflow reobserves mutable GitHub inputs, refetches tags, reruns the gate,
and compares the two plans immediately before it creates the annotated tag. A
closed schema-validated receipt then binds the source, tree, candidate and
eligibility digests, GitHub run, tag object, and protecting ruleset IDs. Public
publication remains a separate fail-closed operation.

## Authority matrix

| Authority | After protected integration and every gate passing |
| --- | --- |
| next never-used alpha allocation | true |
| one immutable annotated alpha tag | true |
| alpha supersession by a new number | true |
| protected `dev` merge or self-merge | false |
| credentials or signing | false |
| GitHub prerelease/public publication | false |
| beta, RC, stable, route, or support effects | false |
| human acceptance verdict | false |

## Live GitHub prerequisite observation

At `2026-08-26T22:38:53Z`, read-only authenticated observation ran under
Windows identity `BLACKGLASS-WIN1\Jules` and GitHub account `Julesc013`. The
repository exposed one active repository ruleset, ID `20445007`, named
`main and dev repository governance`, with target `branch`. It exposed no
tag-target ruleset.

Therefore this implementation is intentionally inoperative for tag creation
until a repository owner independently reviews and configures the required
tag ruleset. This WorkUnit does not mutate GitHub settings. GitHub's
[ruleset guide](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/available-rules-for-rulesets)
explains tag update/deletion restrictions, and its
[repository rules REST schema](https://docs.github.com/en/rest/repos/rules)
defines `tag` as a target and `update` and `deletion` as rule types. The FacMan
gate is stricter than a generic ruleset and permits no bypass actor.

## Validation

Final local validation is recorded in
`.aide/queue/active/FACMAN-AUTONOMOUS-ALPHA-DELEGATION-01/evidence/validation.md`.
The required closeout matrix includes focused positive and adversarial tag
tests, all schemas and strict validators, generated state and metadata, full
Python discovery, a clean exact-provider native build and CTest, packaged
runtime proof, AIDE portable validation, and whitespace/path-scope checks.

## Explicit non-results

- No tag, GitHub release, signature, asset upload, branch merge, branch move,
  route effect, Factorio execution, Setup mutation, or support claim occurred.
- No historic commit was retroactively tagged.
- A green task branch cannot tag itself; the policy must first be reachable
  from protected `dev` and every runtime gate must pass again there.
- The repository is not thereby complete for a public `0.1.0` release. Product
  census, human acceptance, protected integration, signing/authenticity,
  publication, support, and higher-class promotion remain separately governed.
