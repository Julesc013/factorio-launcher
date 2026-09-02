# FACMAN-DEV-RECONCILIATION-01

Date: 12 August 2026

State: `local_validation_passed_sync_blocked_authentication`

This is a historical state label. Its authentication suffix came from a
sandbox-context check and is not an authoritative statement about the
interactive Windows user's credential store.

## Outcome

The reconciliation branch now provides one history-preserving,
authority-closed path from canonical `origin/dev` to the smaller Windows
Technical Preview planning phase.

```text
branch       task/facman-dev-reconciliation-01
base         4da0bf2c4c1df92d8e3a4d2d7eae39ebf65cba2f
activation   f92da63747324330a4e4a7718d3a0f9cbd7f2099
synthesis    85648ff0bf0bef30b71bfb25a805c4082f144f9b
merge        30082279453a12a80539c238dec2d5454ce39944
parent 1     f92da63747324330a4e4a7718d3a0f9cbd7f2099
parent 2     85648ff0bf0bef30b71bfb25a805c4082f144f9b
tree         db6213fb561261e23c500f1ed3a288aed00f1ded
```

Both canonical base and synthesized head are ancestors of the merge. No
rebase, squash, force push, protected-branch write, or history rewrite
occurred.

## Authority matrix

| Authority | Before synthesis | Reconciled state |
|---|---:|---:|
| New-evidence execution | true | false |
| Source-closure execution | true | false |
| Route-v2 source-closure evidence | true | false |
| Current valid source-closure evidence | none | none |
| Source-closure status/result | pending | deferred_external / not_run |
| Factorio execution | false | false |
| Setup mutation | false | false |
| Qualification | false | false |
| Route capability/promotion | false | false |
| Tags/signing/publication/release | false | false |

The route index refuses a real evidence run. Tests construct a synthetic
candidate to prove the exact three-field atomic admission contract without
changing canonical authority.

## Preserved implementation

- the useful synthesized admission validator and adversarial tests;
- ZIP64/Deflate archive-reader hardening and native probe changes;
- the factual Factorio Space Age 2.1.14 real-archive characterization;
- source-closure and route-definition lineage; and
- generated plan and truth projections.

The six unrelated `.aide.local.example` deletions from the synthesized branch
were not retained.

## Validation

- Python 3.11.9 full discovery: 976 tests passed, 13 skipped.
- CMake/CTest 4.2.3 with MSVC 19.51.36252.0: build passed; 38 of 38 native tests
  passed.
- The CMake configure-time Python observation was 3.14.7.
- Strict check: passed.
- Schema validation: 337 schemas passed.
- Package validation: 26 manifests passed.
- Source-closure deferred-state, integrated-admission, route, plan, project
  truth, archive, and refusal tests passed.

Disposable read-only provider inputs matched the workspace lock exactly and
remained clean:

- ULK `1cafe4054297cc11e02458b83d230db0cd064471`, tree
  `47018102de4b9fd20af9f77acd4e1e35e51590f3`;
- USK `32488fc13bd2439f9f6e52e83a97f6da345a7650`, tree
  `12fe757b1fc2ae78768a8cf912d03835f46ca65b`.

## Systems not modified

The run did not modify:

- IR4;
- `D:\Games\Factorio\2.1`;
- any private Factorio archive;
- ULK or USK source/history/remotes;
- `main`, local `dev`, or `origin/dev`;
- tags, releases, workflows, repository settings, secrets, or production
  credentials.

No Factorio process ran and no live Setup operation ran.

## Historical synchronization observation

At this checkpoint, fetch succeeded, but `gh auth status` ran under a
non-interactive sandbox identity. That result could not authoritatively verify
`BLACKGLASS-WIN1\Jules` or the `Julesc013` credential store and must be read as
credential isolation or inability to verify, not proof of an invalid token. No
branch push, draft PR, or hosted CI inspection occurred for this checkpoint at
that time. The former `gh auth login` advice is withdrawn; the later protected
promotion and `dev` synchronization recorded in
[`FacMan alpha.5 promotion and candidate closeout`](facman-0-1-alpha5-promotion-candidate-closeout-01.md)
and `release/index/project_status.v2.toml` supersede it.

## Remaining decisions

- Resolve the 2.0.77 route target versus 2.1.14 retained archive mismatch by a
  reviewed route/version decision; do not substitute silently.
- Keep managed installation deferred: current USK whole-payload/stored-only
  limits do not support the observed 4.6 GB ZIP64/Deflate corpus.
- Replace command-count parity planning with a factual user-outcome census.

## Next six WorkUnits

1. `FACMAN-TECHNICAL-PREVIEW-CENSUS-01`
2. `FACMAN-PREVIEW-SEMANTIC-SPINE-01` (bounded characterization-first slice)
3. `FACMAN-WINDOWS-EXISTING-INSTALL-JOURNEY-01`
4. `FACMAN-WINDOWS-TECHNICAL-PREVIEW-PACKAGE-01`
5. `FACMAN-WINDOWS-TECHNICAL-PREVIEW-CLEAN-QUALIFICATION-01`
6. `FACMAN-TECHNICAL-PREVIEW-0.1.0-CLOSEOUT-01`
