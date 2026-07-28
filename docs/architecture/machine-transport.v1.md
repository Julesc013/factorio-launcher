# Bounded machine transport

`facman rpc --stdio` is the canonical subprocess transport for tests and desktop
frontends. It is not JSON-RPC and does not start a daemon.

One strict UTF-8 transport request is read from stdin, with a 1 MiB input
budget, JSON depth/node/string budgets, a non-empty request ID, a canonical
runtime command ID, dry-run state, and an object payload. Protocol v1 remains
accepted for compatibility. FacMan clients use
`facman.transport_request.v2`, which also requires a durable logical
`operation_id` and one-dispatch `attempt_id`. The process writes exactly one
matching transport-response line to stdout. Human presentation never shares
stdout in this mode.

Responses echo the request ID and command, report the negotiated protocol
version and typed command outcome, and carry payload, error, diagnostics, and
effects fields under a 16 MiB output budget. V2 responses additionally carry
the exact `ulk.operation_outcome.v1` result. A cancellation or timeout after
dispatch is `outcome_unknown`, says that effects may have occurred, and directs
the caller to `workspace.recovery.inspect`. A completed provider result is not
discarded when cancellation races with completion; it becomes
`cancellation_requested_but_completed`. Invalid syntax, unsupported protocol
versions, and budget failures still return one machine envelope.

WinForms and AppKit invoke only the fixed `rpc --stdio` process arguments and
write protocol JSON to stdin. Workspace paths, Unicode, quotes, backslashes,
and command values are data encoded by platform JSON serializers; they are not
reconstructed into shell or user-facing CLI grammar.
