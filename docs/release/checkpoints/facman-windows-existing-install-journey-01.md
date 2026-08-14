# Windows existing-install journey checkpoint

Status: active bounded implementation. The fake execution-to-authoritative
Last Run bridge is implemented and locally qualified; the complete
CLI JSON/TUI/WinForms existing-install journey remains open.

## Identity and dependency boundary

- WorkUnit: `FACMAN-WINDOWS-EXISTING-INSTALL-JOURNEY-01`
- branch: `task/facman-windows-existing-install-journey-01`
- stacked base: exact TUI parity closeout head
  `b2b35d91ed6789109983c8c795c57c45d3418087`
- canonical branch at task start: FacMan
  `dev@03d3dd5a7315ade3272033ca428e0ca82b5cdbaf`
- canonical ULK provider pin:
  `09f0639ab6529fba2f2aa22e9bf68e5eebed0553`
- canonical USK provider pin:
  `32488fc13bd2439f9f6e52e83a97f6da345a7650`

This branch preserves the exact #150 history and must be normally
forward-integrated with the eventual #150 merge commit before it can be
retargeted to `dev`. It grants no real Factorio execution, Setup mutation,
network acquisition, daemon, signing, publication, or release authority.

## Implemented slice

The existing `LaunchExecutionService` now accepts an optional caller-rooted ULK
session journal contract. The contract carries product-owned opaque runnable
identity and durable session/operation/attempt identity; ULK receives no
Factorio model or terminology. Inputs are checked against the installed ULK
ABI and no-follow filesystem boundary before process dispatch.

For the admitted fake process only, the service now:

1. keeps `factorio.launch_session.v1` as a local diagnostic journal;
2. writes the authoritative ULK running record from the supervised started
   callback;
3. preserves exact process identity across the running-to-terminal transition;
4. releases local run ownership and finalizes local state before committing the
   immutable ULK terminal record;
5. exposes ULK's exact terminal classification and journal failure in the
   returned session result;
6. leaves a missing/corrupt provider explicit instead of manufacturing Last
   Run in a frontend cache.

The native journey uses the same fake process probe as the execution
foundation and reads results back through
`ulk.session.journal.v1.authoritative`. It covers:

- successful exit and provider reconstruction after restart;
- observed nonzero exit code;
- cancellation after dispatch;
- cancellation before dispatch;
- refusal before effects;
- post-dispatch `outcome_unknown`;
- running-record failure followed by an authoritative
  `recovery_required` terminal record;
- pre-dispatch rejection of an invalid ULK identity/reference contract.

The default local-only execution path remains compatible when no ULK journal
root is supplied.

## Current evidence

- fresh Visual Studio Release source-provider configuration: pass;
- exact canonical ULK and USK revisions observed by CMake: pass;
- warnings-as-errors `ALL_BUILD`: pass;
- native CTest: 44/44 pass;
- complete Python census with the external Release CLI/TUI/package-proof build
  bound explicitly: 1,022 pass, ten declared not-applicable skips;
- plan views, source format, project state, provider-adoption policy, and the
  complete portable AIDE suite: pass;
- real Factorio executions: zero.

Hosted exact-head validation will be bound to the final task head before
review.

## Remaining WorkUnit acceptance

This slice does not mark the WorkUnit complete. Remaining work is to compose
the already existing workspace, Doctor, fixture discovery, ownership,
read-only registration, instance selection, readiness, and Launch Deck paths
with this fake session lifecycle through the common presentation service; then
prove equivalent CLI JSON, same-binary TUI, and WinForms projections. Stale
revision, duplicate intent, transport loss, frontend close, corrupt journal,
relaunch, accessibility, and packaged-candidate receipts remain required.
