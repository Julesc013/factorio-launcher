# FacMan C1 cut-line closeout

Date: 1 August 2026

WorkUnit: `FACMAN-C1-CUTLINE-01`

Base: `239f9c04822f83bdab6b9c3dd191cfaa337f7b23`

## Result

The C1 release contract is accepted. Windows 10/11 x64 WinForms is the
supported reference target; macOS 10.13+ x86_64 AppKit and a frozen Linux x64
GTK 3/X11 baseline are preview targets until independently qualified.

The product cut contains Instances, Installations, Activity, Settings/About,
and a persistent Launch Deck. The generated command explorer remains under
Advanced. C1 retains bounded process RPC and introduces only the FacMan-local
experimental `facman.presentation.v0` contract.

The qualified runtime identities remain unchanged:

```text
FacMan source       8f495d63b412a3af5a22305d9d8b424efd4303d2
Universal Launcher  7fc25340623131ba86c08dca4fb8a43b18a4520d
Universal Setup     3048128963dc718a7c38c1cfcdda9e813a23b0db
```

## Gate scope

Revalidation-04 is `authority_only` and blocks exactly:

```text
FACMAN-EXACT-PLAY-ROUTE-CAPABILITY-01
FACMAN-WINDOWS-INSTANCE-ISOLATED-PLAY-ROUTE-PROMOTION-01
C1-LIVE-PLAY-ACCEPTANCE-01
```

Fixture journeys, presentation work, WinForms, AppKit, GTK 3, packaging,
accessibility, refusal/recovery UI, and support documentation remain
independent. The next ready product units are `FACMAN-JOURNEYS-01` and
`INSTANCE-VIEW-MINIMUM-01`.

Jules's operator designation is recorded against qualification digest
`eaea8e2bbc03268f49f0fa8c077e329edae317c3757ef42a628a05da06cf1788`
and staged-candidate digest
`060bbeaea354bc39a9601208e89b8a2fe066cdeef0ffffb2e0174514838e4249`.
Observer capture, `prepare`, baseline, permit, Factorio execution, verdict, and
route authority remain false or not started.

## Repository safeguard correction

Repository policy now classifies mechanically guarded task-branch creation,
task worktrees, in-scope edits/checks, ordinary commits, non-protected task
pushes, and draft pull requests as routine reversible development. Protected
ref updates, merges, history rewrites, release tags, signing, and publication
remain repository authority. Product credentials, Setup/foreign mutation,
permits, execution, observer capture, verdicts, and route promotion remain a
separate authority class.

## Validation

```text
focused Python                       PASS 42
Q29 Git helper policy tests          PASS 15
schema validation                    PASS 306
AIDE Lite portable suite             PASS
plan generation/check                PASS
project-state generation/validation  PASS
queue and release structure          PASS
source format                        PASS
strict affected checks               PASS
```

The aggregate local strict runner also scanned pre-existing ignored
`out/worktrees/**` trees and refused the sibling Universal Setup checkout at
`3f848927...` because it differs from the frozen `30481289...` pin. Those local
environment conditions are not changes in this WorkUnit; clean CI remains the
required aggregate proof.
