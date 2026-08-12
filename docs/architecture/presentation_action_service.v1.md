# FacMan callable presentation/action service v1

`presentation.query` and `presentation.action` are an engineering-only backend
foundation for one product-semantic frontend boundary. They do not activate a
production frontend migration.

## Query law

`presentation.query` returns one immutable
`facman.presentation_snapshot.v1`. The backend joins the authoritative
JSON/TOML workspace repositories and computes readiness, recovery, specific
blockers, semantic-action availability, provider/package identity, dependency
identity, and a deterministic SHA-256 revision. Selection and search are
request-local context and never mutate the workspace. A normal refresh reads
repositories only and never performs discovery.

The supported scopes are `launch_deck`, `instances`, `installations`, and
`activity_recovery`. Unknown scopes fail before effects.

## Action law

`presentation.action` requires a request ID and expected snapshot revision.
Stale revisions return a typed refusal with a replacement snapshot. Optional
idempotency keys replay byte-identical results for identical input and refuse
reuse with different input. Durable operation IDs remain caller-supplied
correlation identities; this foundation does not invent a second session
store.

The admitted actions are deliberately narrow:

- `presentation.refresh` returns a replacement repository-read snapshot;
- `installations.scan` performs an explicit read-only discovery scan and
  returns an invalidation signal rather than silently changing the snapshot.

Launch remains explicitly unavailable because execution authority is false.

## Last Run seam and stop law

The `LastRunProvider` seam represents six states without collapsing them:
authoritative record, no record, provider unavailable, corrupt/incompatible
record, outcome unknown, and recovery required. Production currently installs
the unavailable provider. The fixture provider exists only for conformance
tests. Frontend-local caches remain non-authoritative view copies.

Production cutover requires an accepted canonical ULK session provider and one
coherent adapter migration across WinForms, AppKit, and GTK. Until then, no
frontend switches and no stable provider lock changes.
