# FacMan canonical plan and truth closeout

Date: 29 July 2026

WorkUnit: `FACMAN-CANONICAL-PLAN-AND-TRUTH-CLOSEOUT-01`

Result: `PASS`

## Purpose

This checkpoint reconciles the canonical planning graph and generated project
truth with the published repository topology after the planning and native
interface-design programme reached `main` and was synchronized back into
`dev`.

It is a truth-only closeout. It does not prepare or execute the staged
revalidation, assign its operator, change its candidate, promote a Play route,
or grant Setup, credential, network, signing, or publication authority.

## Reviewed handoff inputs

The operator supplied four 29 July handoff artifacts. They were read in full
and treated as historical inputs that require live verification:

| Artifact | SHA-256 |
| --- | --- |
| `FACMAN_CHATGPT_HANDOFF_2026-07-29.md` | `EFF9D17046A2D431BD191D89636A9E63AA7D52E3863D00289B73B4EBF24B5C2B` |
| `FACMAN_CURRENT_STATE_SNAPSHOT_2026-07-29.json` | `AE4C64FECE58E610D94943FBFAE9FD387298067137204D600E7997DE60AE911E` |
| `FACMAN_NEW_THREAD_STARTER_2026-07-29.md` | `CCB1D76A475F9FFE9A4AE6D6789570B4F45C6BB605BA7C3CC4FCFCDB744A1A8E` |
| `FACMAN_ULTIMATE_COMPLETION_PLAN_2026-07-29.md` | `6499F64941F7F43CFA23E67C37D2C2C58D066DFA0F1BB345D3523E822FBF0446` |

The strategic C0-C5 sequence, release-claim discipline, platform tiers,
contract maturity, WIP limits, and narrow C1 journey remain compatible with
the canonical plan. Snapshot claims about open PR #95, unpublished planning
work, and the old protected tips are superseded by the live observations
below.

## Published branch truth

| Role | Exact revision |
| --- | --- |
| Promotion source | `29f1a97410cb999f7691d5daa1f4b2afa82f0149` |
| Canonical `main` | `133da925af13d475c959a336e0b0eec0427a0381` |
| Planning promotion | `133da925af13d475c959a336e0b0eec0427a0381` |
| Observed `dev` | `f0b9bac022e428fb19db27a2e320941c9e193899` |
| Dev synchronization | `f0b9bac022e428fb19db27a2e320941c9e193899` |
| Truth-closeout source | `f0b9bac022e428fb19db27a2e320941c9e193899` |
| Shared tree | `431181449a4284ef93f0eaf9a2d5328fee7c9ab8` |

`main` is an ancestor of `dev`. The only commit in `main..dev` is the
no-content synchronization merge, and both refs resolve to the same tree.

PR #95 is merged. Its stale body metadata is historical GitHub presentation
debt, not a source-integration blocker or authority record.

## Exact-tip hosted acceptance

Current `main` has successful push workflows at its exact SHA:

| Workflow | Run |
| --- | --- |
| `ci` | `30380264099` |
| `schema-check` | `30380263776` |
| `security-policy` | `30380263423` |
| `code-security` | `30380263435` |

Current `dev` has successful push workflows at its exact SHA:

| Workflow | Run |
| --- | --- |
| `ci` | `30380262249` |
| `security-policy` | `30380262287` |
| `code-security` | `30380262498` |

No exact-tip `schema-check` run exists for the no-content `dev`
synchronization commit. This checkpoint records that absence rather than
inventing acceptance evidence; the identical canonical tree has a successful
exact-main schema check.

## Provider truth

| Provider | FacMan pin | Live `main` | Relationship |
| --- | --- | --- | --- |
| Universal Launcher | `7fc25340623131ba86c08dca4fb8a43b18a4520d` | `7f4312faf2f1ac2856a51393fef0ec49fc276a78` | pin is reachable; live main is one no-content commit ahead |
| Universal Setup | `3048128963dc718a7c38c1cfcdda9e813a23b0db` | `3048128963dc718a7c38c1cfcdda9e813a23b0db` | identical |

FacMan continues to consume the exact reviewed pins. This closeout does not
silently repin either provider.

## Preserved candidate and evidence identities

Current branch truth is deliberately separate from the historical runtime and
qualification roles:

| Role | Exact revision |
| --- | --- |
| Runtime candidate | `d03b42e8d6b22459fd9a9b8feff05523f942577a` |
| Qualification source | `2c393acf838dd432d37f8acce50d01f91bfd28ca` |
| Qualification evidence | `dbaba5976e13c8e9c6d02aba137f884e30ab152f` |
| Qualification integration | `2c393acf838dd432d37f8acce50d01f91bfd28ca` |

The accepted qualification digest remains:

```text
99aee276b2968e493f7830ee0cf949efbcd4b0d843e0e93abe8729f13454d210
```

The staged candidate digest remains:

```text
f7ef4783dd153b1445ec3cd9882134fc0ccb14a19fe3494186b7fe95b721de9d
```

## Active authority gate

The canonical planning graph now observes:

```text
FACMAN-WINDOWS-INSTANCE-ISOLATED-PLAY-REVALIDATION-02
```

Its exact repository state remains:

```text
stage                staged_not_prepared
operator             unassigned
prepare authorized   false
Factorio execution   false
observer capture     false
permit issuance      false
human verdict        unset
route promotion      false
```

Qualification-03 is closed and is no longer reported as the active external
gate.

## Validation

The bounded closeout passed:

```text
python tools/generate_plan_views.py --check
python tools/project_state.py --validate
python -m unittest \
  tests.test_current_truth_roles \
  tests.test_plan_views \
  tests.test_aide_compaction \
  tests.test_aide_target_truth \
  tests.test_release_structure
python .aide/scripts/aide_lite.py test
python tools/strict_check.py
python tools/verify_dependency_revisions.py --remote
git diff --check
```

The focused suite ran 37 tests. Strict validation passed with clean disposable
worktrees checked out at both exact provider pins. Remote dependency
verification independently fetched each declared canonical provider ref and
proved that its pin is reachable.

## What this checkpoint does not prove

Git and GitHub cannot prove that retained machine-local staged bytes are still
present or unchanged. Before any separately authorized prepare operation, the
operator must recheck the exact stage root, qualification and candidate
digests, artifacts, Factorio executable/source, process and WPR state, pending
restart state, disk capacity, machine identity, principal, session, integrity
level, and workspace/instance binding.

No such machine-local revalidation and no authority-bearing operation occurred
in this closeout.

## Next safe sequence

```text
recheck the retained machine-local stage
-> assign the explicit operator
-> obtain separate prepare authorization bound to the exact stage and route
-> conduct two fresh launches with fresh evidence and one-use permits
-> record reviewed Pass, Fail, or Inconclusive
-> after Pass only, create and promote one exact route capability
-> then begin the smallest Windows x64 WinForms + CLI C1 vertical slice
```

`FACMAN-C1-CUTLINE-01` remains planning-ready but must not start while the
external evidence gate consumes the programme boundary.
