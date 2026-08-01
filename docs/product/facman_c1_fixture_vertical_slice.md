# FacMan C1 deterministic fixture vertical slice

This slice executes the complete player-facing C1 state machine against
deterministic `facman.presentation.v0` records. It is product-integration
evidence for FacMan only. It starts fixture processes in the transcript model,
starts no Factorio process, and grants no live Play, route, permit, observer,
verdict, promotion, or publication authority.

## Executable journeys

`tools/generate_facman_fixture_journeys.py` replays three fixed journeys and
writes their semantic transcripts under
`tests/fixtures/presentation/journeys/`.

| Evidence | Player-facing path | Required terminal truth |
| --- | --- | --- |
| `J01-FIXTURE-POSITIVE-01` | Select/create → readiness → Play → running → close/reconnect → exit → last run → relaunch → exit | Two distinct backend-owned fixture operations exit normally. |
| `J01-FIXTURE-STALE-01` | Select instance → readiness → dependency drift → Play refusal → rescan | Exact `stale_readiness`, zero process starts, and readiness revision 8 without auto-launch. |
| `J01-FIXTURE-INTERRUPTED-01` | Play → close → response loss → restart → inspect → recover → relaunch → exit | `outcome_unknown` is not cancellation; recovery and relaunch retain distinct operation IDs. |

Every step records the selected instance, presentation revision, readiness,
Play availability/effect class, operation identity and status, last-run
outcome, recovery identity, fixture/live process counters, client outcome, and
the invariant proved by that transition.

## Transition law

The positive path begins with one selected instance and the semantic Create
action visible. Current readiness precedes Play. Fixture Play moves to a
backend-owned running operation. Closing and reconnecting the frontend leaves
that same operation running. Backend exit supplies Activity and Last Run truth;
relaunch creates a different operation identity and reaches its own exit.

The negative path invalidates readiness revision 7 before Play. The presentation
record and journey contract now use the same exact refusal code,
`stale_readiness`. The refusal includes observed revision 7, current revision 8,
and the safe read-only rescan action. Both fixture and live process counters
remain zero. Rescan publishes revision 8 and does not start Play.

The interruption path keeps bounded process RPC and backend session/journal
ownership. Frontend closure preserves the running operation. Lost response is
reported as `outcome_unknown`; it is not success, failure, or cancellation and
does not retry. Restart shows the backend's interrupted record and exact
recovery identity. Inspect and recover stay bound to those identities. Recovery
clears the record without auto-launch; a fresh-readiness relaunch creates a new
operation.

## Executable safeguards

`tools/facman_fixture_journey_check.py` rejects:

- missing, reordered, or non-deterministic journey steps;
- live execution or any non-zero live-process count;
- a stale refusal that differs from the presentation fixture;
- any process start on the refused path;
- rescan or recovery that auto-launches;
- frontend closure becoming cancellation or changing operation identity;
- response loss becoming anything other than `outcome_unknown` without retry;
- recovery inspection losing its exact operation/recovery binding; or
- relaunch reusing the original operation identity.

The checker also validates every canonical and derived replay frame against the
closed `facman.presentation.v0` JSON Schema and semantic invariants, then checks
the generated transcript bytes and SHA-256 manifest.

## Bounded claim evidence

This slice advances only deterministic fixture evidence:

- `FACMAN-CLAIM-001`, `002`, and `003`: the positive transcript supplies the
  selected-instance, current-readiness, fixture Play, exit, last-run, and
  relaunch state proof. It does not prove live filesystem integrity, menu
  intent, or mutable-root isolation.
- `FACMAN-CLAIM-004` and `005`: the interruption transcript proves honest
  `outcome_unknown`, exact recovery identities, no synthetic cancellation, and
  fresh relaunch semantics.
- `FACMAN-CLAIM-010`: the stale transcript proves one exact blocker, the safe
  rescan action, zero execution, and a newer readiness revision.

Fixture evidence never substitutes for Windows live acceptance, packaging,
accessibility qualification, support evidence, or protected/writable-state
observation. It does not promote AppKit or GTK preview support.

## Exclusions

This slice adds no native shell, toolkit type, daemon, direct-client binding,
transport rewrite, live route, process host, package, Universal Launcher ABI,
installation mutation, networking, account flow, update path, marketplace,
theme system, or revalidation authority. The next consumers are the WinForms
C1 shell and native AppKit/GTK preview shells.
