# Technical Preview semantic-spine characterization

Status: characterization-only contract and engineering fixture. Production
frontends, persistence, and command dispatch are unchanged.

The existing `facman.presentation.v0` already names `LaunchDeckView`,
`OperationView`, `RecoveryView`, `LastRunView`, root and readiness revisions,
and backend-owned operation semantics. The missing boundary is not vocabulary;
it is one callable backend presentation/action service and one durable Last Run
authority.

## Observed production state

WinForms projects command responses and retains a workspace-bound JSON Last Run
view copy. AppKit retains a workspace-bound `NSUserDefaults` copy. GTK retains a
workspace-bound key-file copy. Each labels the copy non-authoritative, but the
three frontends still independently decide how readiness, operation, recovery,
and Last Run become presentation. Switching only one frontend would therefore
create mixed product policy and violate the stop law.

This phase does not add a backend presentation command, does not migrate a
cache, and does not change any frontend. It records the exact debt and provides
a fixture-only walking skeleton with semantic actions carrying expected
presentation revisions, request IDs, idempotency keys for effectful requests,
and durable operation IDs where applicable.

## Walking skeleton

The engineering fixture covers:

```text
open workspace
-> discover and register a fixture installation read-only
-> create/select a fixture isolated instance
-> compute fixture readiness
-> render Launch Deck semantics
-> start and observe a fake session
-> inspect fixture Last Run
-> request fixture relaunch
-> expose recovery inspection
```

Every action records `production_command_dispatched=false`. The fixture is not
real Factorio evidence, route qualification, or release evidence. The real
`run.execute` command remains unavailable until its independent isolation and
operator gates close.

## Atomic migration gate

The next production WorkUnit must move all preview-path frontends together to
one backend presentation/action service and one durable Last Run store. It must
preserve the existing JSON/TOML workspace authority, introduce expected
revision and idempotency enforcement, characterize legacy cache reads, migrate
or invalidate them atomically, and remove frontend policy only after parity
passes. If that complete cut cannot be made, the production path stays exactly
as characterized here.

No SQLite authority, daemon, ULK/USK source change, Setup mutation, Factorio
execution, qualification, route promotion, signing, publication, or support
authority is introduced.
