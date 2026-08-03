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

## WinForms C1 client law

The Windows C1 client encodes the complete request as strict UTF-8 and proves
its raw-byte length before starting a process. Its default finite budgets are:

| Surface | Budget |
| --- | ---: |
| Request | 1 MiB |
| Standard output | 16 MiB |
| Standard error | 64 KiB |
| Whole operation | 30 seconds |
| Reserved tree cleanup | 2 seconds |
| Cancellation/terminal-response race | 150 milliseconds |

The process is created suspended without a shell, assigned to a Windows Job
Object with kill-on-close, and resumed only after containment succeeds. The
client drains stdout and stderr concurrently as raw bytes. It terminates the
complete job, drains the pipes, and proves the job empty within the same
whole-operation deadline.

Cancellation before the request write begins is `cancelled_before_dispatch`
and cannot imply effects. Once the request write begins, dispatch is possible.
Any timeout, cancellation, write or read failure, output exhaustion, early
exit, malformed UTF-8, malformed JSON, identity mismatch, or incomplete
response from that point becomes `outcome_unknown` with
`effects_may_have_occurred = true` and recovery inspection required. A complete
validated terminal response may win the bounded cancellation race and is then
reported as `cancellation_requested_but_completed`.

Success is constructed only from one strictly decoded v2 response whose
schema, protocol, request ID, command ID, operation ID, and attempt ID match the
request exactly. The response and nested operation/recovery records are closed
objects with known typed outcomes. Missing values are never defaulted and
request-side identities are never substituted into a backend response.
