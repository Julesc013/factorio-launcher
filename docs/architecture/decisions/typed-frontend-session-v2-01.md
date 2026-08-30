# Typed FrontendSession v2

Status: implemented experimental boundary; no broad public SDK stability promise.

`FrontendSession` is the single typed frontend boundary for in-process and CLI
process consumers. It exposes `negotiate`, `query`, `act`, `inspect`, `cancel`,
`capabilities`, and `advanced_execute`; the old `execute` spelling remains a
source-compatible forwarding method.

The frontend allocates request, operation, and attempt identities once. The
client request model retains all three. Process RPC sends and validates the
exact request identity, command, protocol, operation, and attempt returned by
the child. Direct semantic actions validate the request and operation identity
carried by `facman.semantic_action_result.v1`. A mismatch is a fail-closed
client error and is never rewritten using the expected frontend identity.

Typed queries retain the immutable canonical snapshot JSON so explicitly
namespaced `x-*` read extensions survive. Effect inputs remain closed. The
action input map accepts only fields in the canonical request schema and, when
used, only fields advertised by the selected backend action descriptor.

`inspect` reads live launch-session projections from the
`activity_recovery` snapshot and terminal outcomes only from authoritative
Last Run/recovery projections. `cancel` first admits the targeted live launch
session and then dispatches the ordinary confirmed, idempotent
`sessions.stop` semantic action. It is not a generic process-kill boundary.

Canonical frontend context, inspection, cancellation, capability, and
correlation schemas join the deterministic C++, C#, and Python generated
bundle. Generated C++ helpers preserve objects and arrays as JSON values,
reject ordinary unknown fields, validate bounded identities/enums/scalars,
and retain raw canonical JSON for read projections.
