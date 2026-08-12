# FacMan D1 integration closeout 01

Date: 13 August 2026 (AEST)

Status: complete. All required exact-head hosted workflows passed.

## Exact integrated state

FacMan protected `dev` is
`da7c825f0695b401d367d9bd3aab990690d8573e`, tree
`65f15bb879ac42c61c6f39754b25882d1339ab8d`. It is a
topology-preserving merge whose parents are the prior canonical `dev`
revision `4da0bf2c4c1df92d8e3a4d2d7eae39ebf65cba2f` and D1 head
`5e92b8602ab00c0842a3c191cbe8ea2cb07b288f`.

The integrated stack is:

| Tranche | Pull request | Exact head |
| --- | ---: | --- |
| reconciliation | #133 | `51047053760557b52a9bf06cff1b79bf6614dafb` |
| Technical Preview census | #134 | `909e9c62f447f72707cffb9ca9dbcb1b1bf5e274` |
| semantic-spine characterization | #135 | `731f1d8024c2846e8cb1710ccbcc29c7efff8dfb` |
| D1 contract and presentation foundation | #136 | `5e92b8602ab00c0842a3c191cbe8ea2cb07b288f` |

Universal Launcher protected `dev` is
`85df03b292c09a004352b5e66cc6fc4d9fabae51`, containing the experimental
session and Last Run journal. Canonical ULK `main` and FacMan's consumed ULK
pin both remain `1cafe4054297cc11e02458b83d230db0cd064471`. The new journal is
available for promotion qualification but is not yet an adopted FacMan
provider.

Universal Setup is unchanged: `main` and consumed pin remain `32488fc13bd2439f9f6e52e83a97f6da345a7650`; `dev` remains `6dc48673d54fb27ac4e8949da6f43275d36c9622`.

## Hosted validation

The exact FacMan merge-head push created the following required runs:

| Workflow | Run | Result at closeout review |
| --- | ---: | --- |
| CI | 31615374693 | success |
| bounded provider-input conformance | 31615374761 | success |
| provider SDK consumption | 31615374699 | success on Windows, macOS, and Ubuntu |
| schema check | 31615374686 | success |
| security policy | 31615374527 | success |
| code security | 31615374554 | success |
| synthetic product TCK | 31615374716 | success |

Inspection of run 31615374699 established that it was neither an orphaned
record nor a deadlocked pre-start job. All three platforms completed setup,
the production-capable non-adopted SDK proof, the tracked reconciled-provider
proof, and the non-authorizing observation. Windows completed at 16:52:11 UTC;
the workflow reached a successful terminal conclusion at 16:52:12 UTC.

ULK merge-head run 31615374501 completed successfully.

## Pull-request topology and authority

Pull requests #134 and #135 were closed as integrated through #136 after their
exact heads became ancestors of `da7c825f`. Pull request #136 records the
corresponding explanation for #131 and #132: GitHub's merged state is
ancestry-derived. Historical admission commits became ancestors of the
reconciled integration, but their temporary state was superseded by the final
merged tree and was not accepted as current evidence, execution, or release
authority.

No branch was rewritten. No protected-branch direct commit, force push, tag, release, signing, or publication occurred in this closeout.

## Canonical programme transition

Reconciliation, the 37-outcome Technical Preview census and separate
125-command/API ledger, semantic characterization, CLI machine-envelope
normalization, reduced 1.0 frontend scope, dormant presentation service, v2
WinForms package target, and provider-neutral ULK session substrate are
complete as integrated foundations.

The dependency-ordered FacMan programme is now:

1. external `ULK-SESSION-LAST-RUN-PROMOTION-01`;
2. `FACMAN-ULK-SESSION-PIN-ADOPTION-01` and the global Last Run authority cutover;
3. `FACMAN-WINDOWS-EXISTING-INSTALL-JOURNEY-01` using fake processes;
4. `FACMAN-WINDOWS-TECHNICAL-PREVIEW-CANDIDATE-01`;
5. `FACMAN-FIRST-ROUTE-VERSION-DECISION-01`;
6. `FACMAN-CLEAN-WINDOWS-PROOF-HOST-01`.

The authority atomicity rule is one authoritative backend Last Run state, not
simultaneous product completion of every toolkit. CLI JSON and WinForms form
the Windows presentation cut. AppKit and GTK may read the authoritative backend
value or show it unavailable; neither may use a local cache as fallback
authority.

## Closed authority and deferrals

This checkpoint grants none of the following: provider-pin adoption, Factorio
execution, Setup mutation, managed installation, network or credential access,
daemon work, TUI redesign, Qt, selected-save launch, self-update, Steam
mutation, tags, releases, signing, publication, or public support status.

The Windows Technical Preview remains unsigned, internal, unpublished, unsupported, and real-Play unqualified.
