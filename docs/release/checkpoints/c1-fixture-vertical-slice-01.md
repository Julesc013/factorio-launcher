# FacMan C1 fixture vertical slice closeout

Date: 1 August 2026

WorkUnit: `C1-FIXTURE-VERTICAL-SLICE-01`

Branch: `task/c1-fixture-vertical-slice-01`

Base: `0cef638e407fd43b240d985ca9f3482238949c8c`

## Result

The deterministic fixture path now exercises select/create, readiness, Play,
running, frontend close/reconnect, ordinary exit, Last Run, relaunch,
stale-readiness refusal/rescan, response loss, interruption, inspection,
recovery, and fresh relaunch.

Three generated transcripts provide the exact evidence IDs promised by the C1
journey contract. They derive from the closed `facman.presentation.v0` records,
include fixed semantic observations at every transition, and are protected by a
SHA-256 manifest and executable negative tests.

The slice also resolved the only contract mismatch found during replay: the
presentation fixture now uses the accepted exact refusal code
`stale_readiness`, matching the journey contract.

## Authority and scope

The transcripts model fixture-process starts only. Live-process starts are
machine-checked as zero. Bounded process RPC, backend operation/session/journal
ownership, and unchanged route authority remain intact.

No toolkit, native shell, daemon, direct client, live process host, runtime
route, Universal Launcher ABI, package, or qualification claim was added. No
revalidation observer, prepare, permit, execution, verdict, or route authority
was consumed.

## Evidence

```text
docs/product/facman_c1_fixture_vertical_slice.md
tools/generate_facman_fixture_journeys.py
tools/facman_fixture_journey_check.py
tests/fixtures/presentation/journeys/manifest.v0.json
tests/test_facman_fixture_journey.py
tests/test_facman_presentation.py
```

## Validation

```text
fixture journey checker              PASS (3 journeys, 23 steps)
presentation contract/fixture check  PASS (5 deterministic states)
focused fixture/presentation tests   PASS
plan generation/check                PASS
project-state validation             PASS
source format and structure checks   PASS
```

The portable AIDE Lite `task inspect` and `task noop-check` helpers report
`blocked_missing_task_surfaces` because source `.aide/queue/` state is
intentionally absent from the target pack. That does not weaken product
evidence or broaden the WorkUnit.

Hosted exact-head checks and integration into `dev` remain separate repository
authority decisions.
