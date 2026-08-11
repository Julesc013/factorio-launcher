# FacMan source-closure admission and real-archive synthesis 01

Date: 12 August 2026

State: `validated_task_branch_synthesis`

## Outcome

The source-closure admission line and current FacMan development line now have
one history-preserving task-branch head:

```text
branch
task/facman-successor-play-source-closure-admission-01

synthesis merge
7f71c9179943036564674fde29b93dd834bfc793

first parent
68642575b23613c1ce6716546e4d0616196ac95c

second parent
2e790d518b6a37d1456e99aad363dc617909f424

validated head
13f9d2b5db1adf733ae80d3f6ab41682041edbcc
```

The branch and its remote-tracking ref were equal at the validated head. Local
`dev` remained at `2e790d518b6a37d1456e99aad363dc617909f424` and
`origin/dev` remained at `4da0bf2c4c1df92d8e3a4d2d7eae39ebf65cba2f`.
Canonical `main` and `origin/main` remained equal at
`b70be10696855628c6d2948eb016c8424912e14e`.

The merge does not rewrite either parent history and does not land admission
on `dev`.

## Preserved work

The admission parent contributes:

- the exact three-field route-v2 source-closure admission;
- the active admission WorkUnit, queue projections, canonical plan updates,
  validator, adversarial tests, checkpoint, and retained evidence;
- the blocked underlying source-closure WorkUnit and clean-host proof law; and
- removal of proof-host incident material and committed local-state examples.

The development parent contributes:

- the official Windows Space Age 2.1.14 real-archive checkpoint;
- the aggregate extraction deadline repair and owned-staging cleanup;
- extraction-probe limit parsing and Deflate regression coverage; and
- root-local temporary/local-state ignore hygiene.

The intermediate guest-credential and proof-host incident scripts do not exist
in the synthesized tree. Their historical commits remain visible because this
checkpoint does not rewrite published history.

## Exact validation

A fresh detached checkout of validated head
`13f9d2b5db1adf733ae80d3f6ab41682041edbcc` used Visual Studio 2022 x64 and
the exact preserved providers:

```text
Universal Launcher
1cafe4054297cc11e02458b83d230db0cd064471

Universal Setup
32488fc13bd2439f9f6e52e83a97f6da345a7650
```

Results:

```text
merge conflicts                         0
schema validation                       337 schemas, PASS
focused synthesis matrix                91/91 PASS
archive regression matrix               8/8 PASS
native CTest                            38/38 PASS
Python local obligation profile         973 tests, PASS
Python failures/errors                  0/0
classified skips                        13
unknown skips                           0
strict validation                       PASS
AIDE Lite validation                    PASS
```

The 13 classified skips comprise seven optional lanes, five tests requiring
unavailable Windows symlink privilege, and one required-blocked shared
WinForms package lane not built by this local source-mode configuration.

The first clean full run exposed a test-routing defect: 23 archive cases were
classified as required-blocked even though the external build contained the
probes. Follow-up commit `13f9d2b` makes archive discovery honor
`FACMAN_NATIVE_BUILD_ROOT` and `FACMAN_NATIVE_CONFIGURATION`. The exact-head
rerun has zero archive required-blocked skips.

## Project and queue state

The canonical active release remains FACMAN-C1. Managed installation, repair,
move, update, and uninstall remain explicit C1 non-goals.

```text
FACMAN-SUCCESSOR-PLAY-SOURCE-CLOSURE-ADMISSION-01
active; task-ref proof pending

FACMAN-SUCCESSOR-PLAY-SOURCE-CLOSURE-01
blocked_external; qualified clean-host proof absent

FACMAN-SUCCESSOR-PLAY-QUALIFICATION-01
planned; depends on completed source closure

FACMAN-MANAGED-INSTALL-RECONCILIATION-01
planned; not activated and owner unassigned
```

The retained Space Age archive supplies the real consumer corpus named by the
future USK production-lifecycle plan. It does not itself activate that work,
change repository ownership, or move managed installation into C1.

## Remaining blockers

Source closure still requires:

1. exact-head hosted CI, schema, security, CodeQL, and TCK acceptance;
2. a qualified clean Windows x64 host with empty clone/build/evidence roots;
3. the currently specified private read-only Factorio 2.0.77 archive, or a
   separately reviewed immutable-input transition rather than silently
   substituting the retained 2.1.14 archive;
4. one schema-valid task-ref source-closure report and independent review;
5. a separate decision to integrate admission into `dev`;
6. one fresh canonical-`dev` closure run after integration; and
7. immediate reviewed revocation of all three admission fields before
   qualification begins.

Official Space Age installation still requires a separately owned USK/FacMan
lifecycle tranche for:

1. bounded streaming ZIP64/Deflate materialization without whole-payload
   buffering;
2. entry-level durable recovery and cleanup;
3. authenticated source evidence and manifest binding;
4. explicit side-by-side creation or reviewed adoption authority; and
5. real-package fault, rollback, throughput, and clean-machine qualification.

## Authority boundary

This checkpoint grants no Factorio execution, source-closure proof, candidate
qualification, observer, prepare, permit, Setup mutation, installation
adoption, signing, publication, human verdict, route capability, route
promotion, `dev` landing, or `main` promotion authority. It changes no IR4
state and does not mutate the live Factorio installation.
