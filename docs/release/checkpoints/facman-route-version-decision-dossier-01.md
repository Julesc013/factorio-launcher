# FacMan route/version decision dossier 01

Date: 15 August 2026

State: `engineering_route_selected_review_ready_no_activation`

## Decision

Select Factorio 2.1.14 build 87180 as the exact isolated engineering route.
The new identity is:

```text
facman.engineering.play.windows-x64.factorio-2.1.14.standalone.menu.task-isolated.v1
```

This supersedes the earlier recommendation to retain 2.1.14 only as an archive
materialization corpus. The evidence boundary changed materially: the exact
private archive has now been safely extracted into a task-owned root, launched
twice to the real main menu, closed cleanly, and checked against protected
source, live-installation, archive, and user-data inventories.

The active 2.0.77 route index remains unchanged. This decision does not rename
2.1.14 as 2.0.77, transfer 2.0.77 evidence, activate a release route, or modify
`release/index/successor_play_route.v2.toml`. A future release-route change
requires a new immutable 2.1.14 definition and policy with fresh identities.

The machine-readable decision is
`release/index/factorio_route_version_decision.v1.toml`. It grants no product
execution, Setup mutation, provider adoption, protected merge, route
capability, promotion, signing, publication, or support authority.

## Exact private input

```text
Product:        Factorio Space Age
Version/build:  2.1.14 / 87180
Platform:       Windows x64, standalone non-Steam
Archive bytes:  4,597,290,876
Archive SHA:    cd96202e93ef93e170c8f37dda0ebacb9031011ab81770a5eec075a067e3da30
Entries:        20,832 safe ZIP entries
Expanded:       5,350,965,797 bytes
Executable:     bin/x64/factorio.exe
Executable SHA: 2f5e2238a25c28bfbedf624bd49844f819971484abf24595e6fd27375b914999
```

Custody remains local: the archive may be read, hashed, copied, extracted into
a task-owned root, and tested locally. It may not be changed, deleted, bundled,
or uploaded.

## Direct engineering evidence

The first isolated launch reached `Factorio initialised` after 57.353 seconds;
the relaunch reached it after 24.353 seconds. Both displayed the real main menu
and terminated with `Quitting: window closed` and `Goodbye`.

Evidence digests:

```text
first main-menu screenshot
def49206bd2451c53c299725507ffbc343819cc4ff85f120527773214af6e78e

relaunch main-menu screenshot
1625c4f5d083298011a0a4b95590bc7b1c93543671f63496f1ba71b9d3c516bb

relaunch log
f29f611d4b9c4fa97f8c2633706e6dd903a715fbf0fa84ff84bf9f28775f4d85
```

The extracted source tree remained at inventory digest
`48d6a5b1e027fdbce093584d1002c5e08ee1a1543092e0da257d07c80c5521ed`.
The private archive digest remained unchanged. The live installation was not
executed or modified. `%APPDATA%\Factorio` remained at inventory digest
`8638aaeb91a3920b918e7df97fd46a90b31427eeea87ef02a67649f509bc2616`.

## FacMan engineering composition

The frozen noncanonical candidate at
`af5c560a8da30e6cd6f5245680b73eb63b44fa69` performed the product-owned
pre-dispatch journey against the isolated 2.1.14 copy:

1. registered installation `factorio-2-1-14-isolated` read-only;
2. created task-owned instance `factorio-2-1-14-engineering`;
3. matched the exact 2.1.14 installation and instance versions;
4. satisfied installation, version, content, root, configuration, profile,
   mod, save, and recovery readiness dimensions;
5. constructed the strict-isolated launch plan with FacMan-owned config, mod,
   save, log, and write roots; and
6. preserved the shipping boundary: preflight refused the unqualified
   installation lifecycle, and `run.execute` refused before effects with
   `isolation_not_proven`.

The route branch adds a separate default-off engineering harness. It binds this
record's bytes and exact executable SHA-256 at build time, requires every path
under one task root, rejects reparse/link paths and overlapping source/instance
roots, uses the FacMan-generated config, supervises without a shell, and writes
the ULK session/Last Run journal. It is excluded from the normal candidate and
does not enable shipping `run.execute`.

## FacMan-supervised real-Play evidence

The exact route harness completed three supervised Factorio processes against
the task-owned copy. The final durable relaunch is the binding evidence for
this decision:

```text
Session:       run-9486d224d9abf0ecc32bcec1ccce8df9
Operation:     operation-d2e876d4fbb70155fe0c38f7b8bcc220
Attempt:       attempt-ad4abf42fa56aa4939f2263376d41002
Process:       windows-process-v1:16024
Initialised:   25.005 seconds
Closed:        49.916 seconds
Exit:          0
Outcome:       completed
ULK running:   authoritative
ULK Last Run:  authoritative terminal record
```

The harness hashed the full extracted source before and after execution. Both
inventories contain 20,832 files and 5,350,965,797 bytes at digest
`bcb50e75dae6b7409db7d6c3e5f40e5d9ea5b459f50a3c7170e677b0f1138875`.
The unchanged private archive rehashed to its original
`cd96202e93ef93e170c8f37dda0ebacb9031011ab81770a5eec075a067e3da30`.

Durable local evidence identities:

```text
engineering result
65f6a85f3e4a07e37bd15f686533638f0af056adf4b524212345e09fd0d5997d

FacMan launch session
896e3a4bbc3bc3092367dd99c9bbbc08c698c7afc18d583305c8187519a5b125

ULK session record
bc67de9d9b5a1fc4d051426d3f4f2ac155d72fbb54d15c4dc88e371918457778

Factorio log
8c2e15851d00ab344c8160567adc86bbc57fdd9b92a70cf5a180c090f16f2871
```

Two independent frozen-candidate processes then queried the shared product
authority. Both projected presentation revision
`565ac76e02792e60692f74ee11c90696607c9c15c9ce3ddf53e6d58b60fc5996`,
rendered `Relaunch`, and returned the exact authoritative session, operation,
attempt, completed outcome, and exit code. The action itself remained refused
with `execution_authority_unavailable`, as required for the shipping binary.

The separate normal build used
`FACMAN_BUILD_PLAY_EVIDENCE_TOOLS=OFF`. It produced no engineering-harness
artifact and its `facman.exe` contained neither
`isolated_engineering_process` nor `engineering_route_binding_invalid`. Its
native execution-foundation regression passed. The evidence-enabled authority
therefore compiles out of the ordinary product graph instead of depending only
on a runtime flag.

## Transition and invalidation law

A release-route proposal for 2.1.14 must create a fresh immutable route
definition, version-specific policy, and evidence-identity family. It must bind
canonical FacMan and provider inputs, a qualified clean Windows host, observer
and protected-root evidence, exact package and executable identities, two
supervised launches, the human verdict, and separate route capability and
promotion decisions.

Any change to Factorio version/build, archive or executable digest, route
policy, provider identity, FacMan source/package bytes, instance/config binding,
observer, host, or protected-root baseline invalidates the affected evidence.
No evidence from the 2.0.77 identity may be reused as 2.1.14 evidence.

Until that separately reviewed transition integrates, 2.1.14 is an engineering
route only and the existing 2.0.77 definition remains non-authorizing.
