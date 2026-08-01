# FacMan C1 presentation contract

`facman.presentation.v0` is experimental and FacMan-local. It freezes the
smallest semantic projection needed by the C1 fixture journey. It is not a Universal Launcher ABI and creates no compatibility promise outside FacMan.

The shell has exactly four top-level pages, in this order:

1. Instances
2. Installations
3. Activity
4. Settings / About

The selected-instance Launch Deck is persistent across all four pages.
Advanced remains a separate generated command explorer and is not part of this
primary snapshot.

## Frozen records

`ShellSnapshot` is the immutable transport root. Its C1 record family is:

```text
ShellSnapshot
NavigationNode
PageSummary
InstanceListItem
InstanceListView
InstanceSummaryView
ReadinessView
LastRunView
LaunchDeckView
ActionDescriptor
RefusalView
ActivityView
OperationView
RecoveryView
```

Identifiers, the four page IDs, and journey-state values are schema helpers,
not independently extensible records. C1 does not add general resource,
layout, form, notification, theme-package, or plug-in vocabularies.

The machine-readable definition is
`contracts/schema/ui/facman.presentation.v0.schema.json`. It closes every
record with `additionalProperties: false`; changes are experimental v0 changes
and must update schema, fixtures, validator, and this document together.

## Snapshot truth

The root carries a monotonic presentation revision, fixed timestamp, active
page, all four page payloads, selected instance, persistent Launch Deck,
optional structured refusal, and recovery state. It is a projection of backend
truth, not a second product state store.

Readiness always includes its revision, observation time, evidence digest,
summary, and structured blockers. A stale refusal preserves both the revision
observed by Play and the newer current revision. The frontend may display and
invoke the supplied recovery actions; it may not recompute authority or turn a
refusal into availability.

`ActionDescriptor` gives a stable semantic action identity, optional existing
backend command identity, visible and accessible labels, role, availability,
effects, confirmation, ownership, and a structured refusal. Layout, shortcut,
button order, native control selection, focus behavior, and visual styling stay
with each platform shell.

## Transport and operation ownership

C1 retains bounded process RPC. Every snapshot declares
`mode=bounded_process_rpc`; no direct client, daemon, bridge, or replacement
service is introduced by this contract.

The backend owns the process session, operation record, and journal. Closing or
losing a frontend leaves the operation running, completed, or interrupted as
recorded by the backend. A reconnected frontend can only observe the operation
or follow the supplied recovery action. It cannot translate disconnection into
ordinary cancellation or synthesize a successful exit.

The transport record fixes `route_authority=unchanged`: route authority remains unchanged. Presentation data does
not issue permits, promote a route, execute Factorio, or grant product
authority.

## Fixture and live authority

The positive, running, and exited examples use `authority_scope=fixture_only`
and `effects=[fixture_process]`. They prove presentation semantics without live
Play authority. The stale-readiness and interrupted examples use exact
unavailable/refusal or recovery states.

A live `process_execution` effect is valid in v0 only as a refused action while
authority is unavailable. If the separately governed route is later promoted,
the backend may project a newly authorized action, but this WorkUnit does not
add that runtime route or change its authority.

## Deterministic state corpus

`tools/generate_presentation_fixtures.py` renders five canonical snapshots and
a SHA-256 manifest under `tests/fixtures/presentation/`:

| Fixture | Required player-facing truth |
| --- | --- |
| `positive` | Selected instance is ready and fixture Play is available |
| `refused` | Stale readiness refuses Play and offers rescan |
| `running` | Backend-owned fixture operation is visible in Activity |
| `exited` | Ordinary exit and last run are visible; relaunch is available |
| `interrupted` | Interrupted operation binds Activity, Launch Deck, and Recovery |

`tools/facman_presentation_check.py` validates the JSON Schema, exact generated
bytes, manifest digests, page/selection consistency, action authority,
operation ownership, and state-specific invariants.

## Explicit exclusions

This v0 contains no toolkit types or toolkit code, daemon implementation,
direct-client implementation, runtime route, process host, backend behavior,
Universal Launcher extraction, public SDK promise, package layout, or live
acceptance claim. It is presentation data and fixture evidence only.
