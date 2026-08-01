# FacMan C1 presentation minimum closeout

Date: 1 August 2026

WorkUnit: `INSTANCE-VIEW-MINIMUM-01`

Branch: `task/instance-view-minimum-01`

Base: `4620ebe8a382960d48e82a0a5ff90230a8f70588`

## Result

The experimental FacMan-local `facman.presentation.v0` minimum is frozen for
the C1 fixture journey. Its closed JSON Schema defines the four-page shell,
persistent selected-instance Launch Deck, instance list and summary,
readiness, semantic actions, Activity operations, structured refusal, last
run, and recovery state.

Five generated snapshots cover positive, stale-readiness refusal, running,
ordinary exit, and interruption/recovery states. Fixed timestamps, IDs,
revisions, values, canonical JSON encoding, and a SHA-256 manifest make the
corpus deterministic.

## Ownership and authority boundary

Every snapshot preserves `bounded_process_rpc`. The FacMan backend owns the
process session, operation record, and journal. Frontend disconnection leaves
the operation to continue, complete, or become recoverable according to
backend truth.

The positive path is explicitly `fixture_only`; live process execution remains
a structured unavailable action. The contract records route authority as
unchanged. This closeout grants no observer, permit, execution, route,
publication, or product authority.

No toolkit type or shell implementation was added. No WinForms, AppKit, GTK,
daemon, direct-client, runtime-route, process-host, backend, or Universal
Launcher ABI work is present.

## Evidence

```text
contracts/schema/ui/facman.presentation.v0.schema.json
docs/product/facman_presentation_v0.md
tools/generate_presentation_fixtures.py
tools/facman_presentation_check.py
tests/fixtures/presentation/manifest.v0.json
tests/test_facman_presentation.py
```

## Validation

```text
presentation contract/fixture check  PASS (5 deterministic states)
focused presentation unit tests      PASS (5)
JSON Schema validation               PASS (307 schemas)
plan generation/check                PASS
source format and structure checks   PASS
```

The AIDE Lite `task inspect`, `task noop-check`, and `task recover` helpers
reported `blocked_missing_task_surfaces` because the portable target correctly
does not contain source `.aide/queue/` state. This is an environment/portable
pack limitation, not product evidence and not a reason to broaden the task.

Integration into `dev`, hosted exact-head checks, and the fixture vertical
slice remain separate follow-on work.
