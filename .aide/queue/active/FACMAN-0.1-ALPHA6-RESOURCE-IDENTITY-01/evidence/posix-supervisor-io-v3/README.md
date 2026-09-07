# POSIX supervisor V3 proof custody

This supplement preserves the exact reviewed source and recorded Linux proof
for the [POSIX ownership and I/O contract](../../../../../../docs/architecture/posix-process-supervision.v1.md)
under the existing [resource WorkUnit](../../ExecPlan.md). The implementation
bookkeeping remains a separate, unapplied proposal against 5f3ad450.

[Custody records](custody.json) map original paths and raw SHA-256 values to
[custody.zip](custody.zip). Files were captured once, each nested source/actual
archive was checked against its original roster, and every selected original
and outer archive member was rechecked afterward. Original bytes are preserved;
the existing source manifests' compiled=false fields describe their earlier
source freeze and are not rewritten after the later native run.

The selected evidence includes the original I/O V1 bytes, V2 source custody,
the five-file V3 source and reviews, reviewed driver custody, actual three-query
dependency preflight, ten-command actual evidence and ROOT independent review,
and the earlier focused seven-command lifecycle proof. The ten-command proof's
91-original ZIP and the predecessor's 40-original ZIP remain intact.
Nested archives contain repeated source/evidence bytes. Their member counts
are not added together or presented as a unique-artifact total. The outer
custody map names any selected originals sharing one identical stored member.

## What changed and what ran

The POSIX correction retains child ownership through the single consuming wait,
bounds EINTR retries, and checks termination-clock arithmetic at the actual
addition. Its nonblocking pump handles exec status, stdin and both output streams.
Anonymous socket stdin suppresses SIGPIPE locally without changing caller
signals. Post-fork uncertainty remains pending; only the exact positive exec
failure handshake plus expected reaped status narrows start failure. Ambiguous
inherited-descriptor close failures refuse before exec.

The recorded V3 validation ran ten exact commands: five warning-as-error compile
commands, default pump and unchanged lifecycle oracles, anonymous AF_UNIX socket
controls, and two deliberately broken lifecycle variants with their required
exact exit1 diagnostics. Four x86_64 PIE test binaries were executed. The actual
supervisor adapter was compiled to an ET_REL object and was never executed.
All 21 source copies and both mutations were checked. Five actual dependency
lists close against the 368-input preflight. The native archive contains all
33 recorded regular files from the 52-row child inventory.

ROOT's independent actual review is
6761a5d3540391fa68e62b19698b8de19dbe7f662903daa5e547f4a6fd44bb2a.
The predecessor focused lifecycle proof remains separately bound to d90a6a4f
and does not qualify the later I/O source by inheritance.

## Remaining boundaries

This is bounded ordinary native evidence. No product supervised child, session
escape, PID-reuse race, Apple compilation/socket behavior, full integrated
process suite, hosted build or release was qualified by this lane. A successful
group termination request is not proof that every descendant stopped. The
embedding process must preserve exclusive wait/SIGCHLD ownership; synchronous
callbacks must return for the in-process deadline to advance.

The ZIP makes selected source, logs, receipts and the exported small native
artifacts portable. Original Linux directories and the host's 368 compiler/header
inputs are not installed or reconstructed by this supplement. Their observations
remain exact recorded-run evidence, with no fresh Linux readback or ongoing
availability claim. Absolute original paths in the custody map are provenance,
not instructions to access or recreate those paths.

No repository patch is applied, no WorkUnit is closed, and no current package,
GUI, provider adoption, human/game, signing or publication gate is discharged.
The resource-export correction and its Windows evidence remain independent.
