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
Stale revisions return a typed refusal with a replacement snapshot. CLI and
TUI callers propagate the same request, operation, and attempt identities
through the frontend/transport boundary and the semantic result.

Effectful actions additionally require an idempotency key, durable operation
ID, attempt ID, explicit confirmation, and non-dry-run dispatch. Before the
domain handler runs, FacMan establishes workspace ownership and atomically
claims a bounded receipt under `.facman/action-receipts-v1`. The accepted
receipt is `outcome_unknown` until it is durably replaced by the terminal
result. A fresh process therefore returns the byte-identical result for the
same request and refuses an idempotency key reused with different input.
Missing, corrupt, incompatible, or unfinalizable receipts fail closed into an
explicit recovery/unknown result; they never cause an automatic retry.

Read-only actions retain process-local replay only. In particular, a later
installation scan receives a fresh intent identity even when the snapshot
revision did not change, so an external filesystem change can be observed.
The action ledger is FacMan application authority, not another ULK session
store: it answers whether FacMan accepted a semantic request, while ULK owns
the resulting runnable/session lifecycle and Last Run.

The admitted actions are deliberately narrow:

- `presentation.refresh` returns a replacement repository-read snapshot;
- `installations.scan` performs an explicit read-only discovery scan and
  returns an invalidation signal rather than silently changing the snapshot;
- `installation.register_read_only` delegates to the existing installation
  reference handler without mutating the external installation;
- `instance.create_isolated` delegates to the existing instance handler and
  returns the backend replacement snapshot;
- `instance.select_context` and `readiness.refresh` return a new scoped
  snapshot without persisting frontend selection;
- `recovery.inspect` returns the current recovery projection;
- `recovery.apply_supported` delegates only the currently supported FacMan
  recovery transaction;
- `launch.play` dispatches only when a separately injected executor admits the
  exact snapshot and preserves all six ULK terminal classifications.

The production application module supplies no launch executor, so real Play
remains explicitly unavailable and Factorio execution authority remains false.

The generated command catalogue conservatively marks `presentation.action`
as a possible workspace writer. Generic dry-run rejection is delegated to the
typed service for this one dynamic dispatcher, allowing read-only actions to
remain read-only while effectful actions still require the stronger law above.

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
