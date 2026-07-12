# Bounded machine transport v1

`facman rpc --stdio` is the canonical subprocess transport for tests and desktop
frontends. It is not JSON-RPC and does not start a daemon.

One strict UTF-8 `facman.transport_request.v1` object is read from stdin, with a
1 MiB input budget, JSON depth/node/string budgets, protocol version `1`, a
non-empty request ID, a canonical runtime command ID, dry-run state, and an
object payload. The process writes exactly one
`facman.transport_response.v1` line to stdout. Human presentation never shares
stdout in this mode.

Responses echo the request ID and command, report the negotiated protocol
version and typed outcome, and carry payload, error, diagnostics, and effects
fields under a 16 MiB output budget. Invalid syntax, unsupported protocol
versions, and budget failures still return one machine envelope.

WinForms and AppKit invoke only the fixed `rpc --stdio` process arguments and
write protocol JSON to stdin. Workspace paths, Unicode, quotes, backslashes,
and command values are data encoded by platform JSON serializers; they are not
reconstructed into shell or user-facing CLI grammar.
