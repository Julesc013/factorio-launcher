# FacMan callable presentation/action service v1

`presentation.query` and `presentation.action` are the backend boundary for
shared product semantics. The same-binary ordinary TUI consumes this boundary;
other frontends adopt it only through their separately qualified product cuts.

## Query law

`presentation.query` returns one immutable
`facman.presentation_snapshot.v1`. The backend joins the authoritative
JSON/TOML workspace repositories and computes readiness, recovery, specific
blockers, semantic-action availability, provider/package identity, dependency
identity, and a deterministic SHA-256 revision. Selection and search are
request-local context and never mutate the workspace. A normal refresh reads
repositories only and never performs discovery.

The supported scopes are `launch_deck`, `instances`, `installations`,
`content`, `saves`, `activity_recovery`, and `settings_support`. Content,
saves, preferences, support, and identity are backend projections; a frontend
does not join command results or retain descriptive records as authority.
Unknown scopes fail before effects.

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
record, outcome unknown, and recovery required. Production installs the exact
canonical ULK session-journal provider. The fixture provider exists only for
conformance tests. Frontend-local caches are non-authoritative view copies and
cannot be fallback inputs.

`UlkSessionJournalLastRunProvider` reads only the public C ABI from a
caller-rooted, bounded journal below the FacMan workspace and maps missing,
corrupt/incompatible, running, completed, uncertain, and recovery records
without manufacturing terminal outcomes. Provider adoption grants no process
execution authority.
