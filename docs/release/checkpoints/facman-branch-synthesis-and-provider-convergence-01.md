# FacMan branch synthesis and provider-convergence checkpoint

Date: 2026-08-05

Status: implementation candidate; no repository or product authority

## Decision

FacMan already has one coherent integrated baseline:

```text
main@b70be10696855628c6d2948eb016c8424912e14e
  -> dev@22a70c0280cc410083d5d9b093f0b05245d691e1
```

`main` is an ancestor of `dev`; `dev` is twelve commits ahead and zero
behind. The release-resolution task tip
`9ccfc86ef9991e842aa3d05b607c22b5541caa53` has the same tree as `dev`.
The successor route definition `d31a9925fd168f6fc23f2c2b1d4b4c2d7dbfc237`
and every other reviewed remote task branch except the active source-closure
line are already contained by `dev`.

Branch synthesis therefore means classification and forward integration, not
merging every surviving ref.

## Ref disposition

| Ref | Exact head | Disposition |
| --- | --- | --- |
| `main` | `b70be10696855628c6d2948eb016c8424912e14e` | Canonical history; do not promote yet. |
| `dev` | `22a70c0280cc410083d5d9b093f0b05245d691e1` | Latest accepted complete integration base. |
| `task/facman-successor-play-source-closure-01` | `bcc0233ccda9b7d29467d4ba5da613a2e016a36f` | Active draft PR #123; six commits above dev; preserve and update only by merging accepted dev forward. |
| `evidence/facman-overnight-2026-08-05` | `9a6d6783c6f99876d8be8770ae5908d0566ba11b` | Immutable evidence custody; never merge as product source. |
| Retrospective and retained task refs | contained by `dev` | Review history only; do not reland. |
| `task/package-smoke-01` | obsolete prototype, 705 commits behind `dev` | Quarantine for a separate archaeology/discard decision. |

No rebase, squash, amendment, force push, cherry-pick reconstruction, evidence
merge, or indiscriminate branch deletion is part of this checkpoint.

## Accepted provider topology

| Provider | Canonical `main` | Synchronized `dev` | Canonical tree |
| --- | --- | --- | --- |
| Universal Launcher | `1cafe4054297cc11e02458b83d230db0cd064471` | `7d4fd8e25a8d529279c4ad18d983e9cd51839eb7` | `47018102de4b9fd20af9f77acd4e1e35e51590f3` |
| Universal Setup | `32488fc13bd2439f9f6e52e83a97f6da345a7650` | `6dc48673d54fb27ac4e8949da6f43275d36c9622` | `12fe757b1fc2ae78768a8cf912d03835f46ca65b` |

Provider repository acceptance, promotion, and dev synchronization are
complete. FacMan has not yet adopted those identities. Its active workspace
pins remain:

```text
Universal Launcher  7fc25340623131ba86c08dca4fb8a43b18a4520d
Universal Setup     3048128963dc718a7c38c1cfcdda9e813a23b0db
```

The authored pre-SDK release-provider identities remain
`719a3ec240831547071d69098e1fe8c76f327fb7` and
`7f8f2baa14e78b0329db8eef8ac872818c4cf30d`. These three provider sets are
distinct historical roles, not interchangeable truths.

## Required convergence line

```text
dev@22a70c0
  -> canonical source-versus-SDK conformance
  -> explicit source / installed-static / installed-shared consumption
  -> one atomic provider-pin reconciliation
  -> non-authorizing successor route-definition v2
  -> reviewed task-to-dev integration
  -> merge updated dev into PR #123 without rewriting its six commits
  -> exact-head CI
  -> task-ref closure on a capable Windows host
  -> source-closure review and integration
  -> canonical-ref closure before main promotion
```

The convergence candidate is rooted at exact `origin/dev@22a70c0`. Each
logical step remains a separate structured commit and a normal revert
boundary even when reviewed as one ordered candidate.

## Immutable route conflict and repair law

`release/index/successor_play_route.v1.toml` is accepted, immutable, and
binds the old workspace pins with `provider_repin = false`. Its validator
correctly rejects any lock drift. It must not be edited to make new provider
heads appear compatible.

If canonical conformance selects the accepted provider-main heads, adoption
must create a separately reviewed route definition v2 that:

- preserves v1 as historical policy and evidence;
- identifies v1 as its superseded definition, without inheriting authority;
- binds the exact selected provider commits, trees, ABI identities, contract
  identities, SDK/package evidence, and provider-consumption mode;
- retains the frozen Factorio selector, process/observer criteria, human
  verdict law, and every false authority;
- remains definition-only and non-executing.

Choosing to retain the old provider set is also structurally valid, but must be
an explicit conformance decision. Chronological recency alone never selects a
release input.

## Conformance acceptance

The canonical provider heads must be exercised through:

```text
exact source
installed static SDK
installed shared SDK
relocated static SDK
relocated shared SDK
private product-local runtime closure
```

Normalize only declared address, loader, path, toolchain, and packaging
differences. Compare ABI and contract identity, composition, command and
refusal behavior, operation outcomes, package/runtime metadata, and
release-resolution identity. Negative controls include wrong provider,
architecture, package, ABI, or contract identity; partial SDK; missing runtime;
stale relocation metadata; injected source/build paths; and undeclared runtime
dependencies.

Conformance evidence is non-authorizing. It performs no Setup mutation and
starts no Factorio process.

## Current product boundary

```text
source closure             required_but_blocked
Factorio execution         false
accepted Play routes       0
human verdict              absent
signing                    false
publication                false
observed player journeys   0
```

The current managed Windows host is not a final native closure host because it
cannot launch the required MSBuild `cmd.exe` child process. A clean capable
Windows VM or runner remains required. That environment limitation must not be
reclassified as a source defect or bypassed by weakening validation.

## Authority ceiling

This checkpoint and its implementation branch may create ordinary commits,
non-protected task refs, tests, out-of-tree observations, and a reviewed
task-to-dev candidate. They grant none of:

```text
Factorio execution
observer capture
prepare or permit
Setup mutation
credentials or authenticated product access
human verdict
route capability or promotion
signing
publication
stable support
```

Canonical `main` remains unchanged until provider identity is coherent,
source closure is accepted and repeated from canonical refs, and a separate
dev-to-main promotion gate passes.
