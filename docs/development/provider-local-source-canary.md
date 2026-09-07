# Local source-static provider canary

The source canary selects one reviewed local USK checkpoint with an exact clean HEAD, Git tree
and local task ref. The external custody JSON and its explicitly supplied digest bind the
selected checkpoint to a non-authorizing ROOT review receipt. This permits disposable
source-static SDK-candidate builds only. A review receipt never establishes stable-main
identity, installed SDK acceptance, provider adoption or release authority.

`tools/provider_local_source_canary.py` consumes the actual FacMan source and existing stable
ULK source. It writes a separate external candidate lock, validates USK before and after
execution, and binds consumer source bytes, compiler commands, build identity, executable hashes
and raw logs. The five tracked release-input files are hashed before and after. Candidate build
identity must state that it differs from the tracked provider and is not release-coherent.

The CMake local source path requires both `FACMAN_PROVIDER_LOCAL_SOURCE_CUSTODY_FILE` and its
SHA256, `source`, `static`, and the existing explicit SDK-candidate class. Other modes refuse
these inputs. Ordinary source custody still requires the selected origin ref and reachability;
installed SDK and stable import rules are unchanged. No remote ref is invented and no
publication is needed for local evidence.
Assume-unchanged, skip-worktree and sparse tracked entries refuse before source admission,
because a clean Git status can conceal modified or missing tracked bytes. These source
observations do not establish an atomic build lease.

Physical tracked files are also compared to each reviewed HEAD blob with bounded raw reads.
Only regular files are admitted; gitlinks, symlinks, reparse indirection and control-bearing
paths refuse. Custom filter and working-tree-encoding attributes refuse before status checks;
no Git clean filter executes. A fixed UTF-8 source-text extension/name list permits CRLF to LF
normalization, with NUL-bearing/nontext mismatches refused. Every raw SHA256 and byte count is
retained alongside its Git blob and normalization rule. The source-static runner compares
these observations before configure, before build, after build and after tests. Limits are
10,000 files, 8 MiB per file and 256 MiB total. This is sequential source observation.

Windows qualification builds actual CLI, setup gateway, standalone transaction/archive tests and
FacManSetup, with parallelism capped at four. The gateway fixtures test stored ZIP, a raw
Deflate block, incomplete product layout, missing input, floating version and inconsistent
CRC/truncation refusals. The self-setup fixture uses stored and zlib-compressed Deflate
payloads, tests consistent-but-wrong payload CRC and truncation, then exercises install,
verification, owned-file damage, repair, foreign-content uninstall refusal and bounded clean
uninstall. No synthetic Factorio file is executed. Explicit retained fixture paths preserve raw
responses and failed effects; CRC apply refusal may retain provider staging and state, and must
never publish the target or alter the foreign sentinel/input bytes.

This is one source-consumer slice of PROVIDER-CANARY-01. Installed static/shared and relocation
proof, consumer interruption/replay, protected successful commit authority,
generation/stale-owner recovery, retained cleanup and provider adoption remain open. Existing
legacy commit preparation is observational and does not close its post-observation publication
race. No automatic recovery, genuine human/game experience or Beta qualification is claimed.

The deadline harness is Windows-only for qualified canary execution. The public runner starts
a suspended worker, assigns its retained process handle to an owned kill-on-close job, then
resumes it. The worker's entire lifetime covers source observation, build/test subprocesses and
final consumer checks. Default limits are 1,800 seconds overall, 900 per build/test command,
30 per metadata command and 45 for CMake local custody. Explicit command/overall values must
be finite, positive and no greater than 7,200 seconds. The earlier local C3 evidence remains
a supervised source/static observation; autonomous scheduling still requires review of this
harness and a subsequent clean-source canary checkpoint.

Each Windows command has its own owned job, restricted inherited stdin/output handles and
a retained PID plus creation-time observation. Timeout, output overflow and execution errors
request termination only through owned handles. Cleanup has a separate five-second observation
and drain budget; a termination request alone is insufficient for success. The job must be
observed empty and its primary stopped. There is no name/PID search, taskkill, detached retry,
or automatic fixture cleanup. A primary that exits while descendants still hold output pipes
cannot leave those descendants running. Nonblocking bounded pipe reads preserve partial raw
stdout/stderr; children cannot write directly to the log files.

Each output stream is capped at 32 MiB (metadata: 8 MiB), input at 8 MiB, command arguments at
256 entries/30,000 characters, environment at 262,144 characters, receipt/result observations at
8 MiB and individual artifact hashing at 512 MiB. Raw command receipts remain in new external
control/evidence directories. An interrupted initial receipt explicitly records an unknown
outcome. Only a complete worker observation and a successful overall supervisor receipt qualify
this harness run; a partial worker PASS line or timeout exit code does not. Filesystem effects
and partial output are retained when the deadline or cleanup fails. These are bounded local-host
observations, not a lease against source changes or an assurance about a stalled kernel/storage
device. The portable custody checker retains its existing behavior with finite 30-second
subprocess waits outside this runner; POSIX descendant containment and scheduling are unqualified.

The synthetic lifecycle script opts into owned command containment only with
`--canary-command-timeout` and a fresh retained fixture root. Existing produced-package
callbacks and stable/installed provider paths keep their separate behavior. CMake timeout
refusals include its textual result and never interpret a timeout string as exit status zero.
The locally synchronized 97e source does not include the separate Windows GUI package selection
fix at 8dcba9813872ea27d270af07da50921fd55d18b5. That source-only sync is planned after this
checkpoint. Current product qualification also remains blocked on the separately observed
loose-schema handshake and stale incremental object issues; no GUI or release qualification
is inferred here.


Process creation and job assignment are separate calls. Abrupt death of the top-level
supervisor after CreateProcessW and before AssignProcessToJobObject can leave an unassigned
suspended child. This is an inferred API/source boundary, not a newly executed crash probe
or a qualified active-effects escape. Inner commands already inherit the outer job. Ordinary
launch, assignment, timeout and cleanup failures are covered; crash-atomic creation/assignment
remains unqualified. These jobs contain ordinary descendants, not hostile code invoking an
external service or permission broker.

Future current-source canaries must start with a new empty build subtree. The separately
observed AppData/MSBuild tracking issue allowed an old product object to survive a source
update, so an incremental rebuild or a newly generated header alone does not establish compiled
source identity. MSBuild's [FileTracker dependency exclusion](https://github.com/dotnet/msbuild/blob/main/src/Utilities/TrackedDependencies/FileTracker.cs)
includes LocalApplicationData. Preserve the original C3 receipts at their recorded scope;
do not relabel those binaries as the next checkpoint. A fresh supervised source-static run,
actual compiled identity checks and separate runtime/schema admission remain required before
broader candidate qualification.
