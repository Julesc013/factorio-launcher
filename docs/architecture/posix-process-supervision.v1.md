# POSIX process ownership and I/O

The POSIX adapter retains one live child lifecycle object from successful fork
through its only consuming wait. Terminal observation uses non-consuming wait;
the reaping latch is permanent before a consuming call. An uncertain wait result
does not restore permission to signal a numeric child or process group. EINTR
retries during consume are finite. A successful process-group termination request
is reported as a request, not proof that every descendant stopped.

Termination validates the actual clock value and grace immediately before adding
them. Negative or unrepresentable grace, and a deadline beyond the clock maximum,
refuse before a signal. Initial option validation alone cannot establish this
later addition is safe after preparation has elapsed.

## Outcome attribution

A successful fork sets the result to pending immediately. Before confirmed exec
and successful return from any supplied started callback, cancellation, deadline,
output overflow, callback, poll/read or cleanup errors retain that uncertainty.
An absent optional started callback is a completed no-op notification after exec;
it does not establish that no effects occurred. Only a complete positive exec
error frame followed by the expected reaped 126/127 status can narrow an otherwise
certain start refusal. Missing or malformed handshakes cannot do so.

The execution outcome consumer already handles pending before other termination
reasons. No provider enum, ABI, pin or transport-schema relaxation accompanies
this correction.

## Streams and descriptors

A single nonblocking poll pump services exec status, stdin and both output
streams with bounded operations and a monotonic deadline. Stdin is a local
anonymous AF_UNIX stream socket. Linux suppresses SIGPIPE per send with
MSG_NOSIGNAL; Apple requires successful SO_NOSIGPIPE setup. Caller signal masks,
dispositions and pending signals are not changed or drained by the supervisor.

Inherited descriptor close attempts are not retried after an uncertain error.
A non-EBADF failure is reported before exec. Local descriptor ownership and the
child lifecycle object cover error paths; callback exceptions retain the original
error and trigger the same bounded cleanup path. Output caps and final draining
remain explicit, and cleanup uncertainty cannot become a completed outcome.

## Recorded validation and limits

The external V3 payload is based on 98858a7f. Its two existing tracked production
files are byte-compatible with the later 5f3ad450 base before application. The new
private headers and pump oracle retain their exact reviewed V3 bytes; the earlier
lifecycle oracle is unchanged.

The recorded Linux lane executed ten commands: five warning-as-error compile
commands, default pump and lifecycle checks, anonymous socket controls and two
deliberate lifecycle mutation failures with exact expected diagnostics. Four
x86_64 PIE test executables were run; the actual adapter was compiled to an
ET_REL object only. Five compiler dependency sets were reconciled against the
368-input preflight. ROOT's independent actual audit is
6761a5d3540391fa68e62b19698b8de19dbe7f662903daa5e547f4a6fd44bb2a.

The actual lane did not execute a product supervised child, session-changing
descendant or a PID-reuse race. Apple compilation/socket behavior, full integrated
process suites, hosted builds and release qualification remain pending. The
embedding process must preserve exclusive wait/SIGCHLD ownership. Synchronous
callbacks must return for the in-process pump deadline to advance; this is not a
hard outer-process deadline. Ordinary process groups cannot prove containment of
escaped sessions.

The CMake registrations expose the two deterministic default oracles on UNIX and
a separate anonymous-socket test. The two defaults are configuration-optional
entries in the existing fast policy, so their absence on Windows is explicit.
Affected selection currently lacks configuration filtering for optional targets.
The narrow process-source impact module therefore uses the already supported
all-native selection, which also covers the socket registration and production
consumers. This selection is a future test obligation; it does not authorize
unreviewed process effects or claim that those tests have passed.

The resource export correction is independent. Its files, outcome semantics and
Windows validation remain bound to its own source and receipts. Neither lane
transfers package, GUI, provider-adoption, human/game or publication qualification.
