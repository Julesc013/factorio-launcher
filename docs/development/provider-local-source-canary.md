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
be finite, positive and no greater than 7,200 seconds. The earlier local C3 evidence retains its original
source/static scope. The deadline harness was reviewed and checkpointed locally at
eee1b04c457b0f3bf50f003ba8019417bbd744fb. The later C4 run below provides a fresh
source/static observation; continuous scheduling remains outside this WorkUnit slice.

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
The Windows GUI package selection source fix at
8dcba9813872ea27d270af07da50921fd55d18b5 was synchronized locally in
6c5b545f50c675e5f57b657037e109ffbc55ea8f. That source merge does not renew the older
package or GUI interpretation. The separately observed schema/runtime admission defects and
AppData incremental-object limitation remain outside the C4 source/static result.


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
do not relabel those binaries as another checkpoint. C4 supplies the bounded fresh-run and
typed compiled-identity evidence for its exact source below. Separate runtime/schema admission
and the remaining consumption modes are still required before broader candidate qualification.


The single C4 run used a new empty build tree at clean FacMan
6c5b545f50c675e5f57b657037e109ffbc55ea8f (tree
8259233dc90b0c8c446df60816061b27ea9c9a90), local USK
8d02dfcbf7f7e16308b37815eb7c91d0beb668be and stable ULK
5479939ca5cbc9ee0f901608a92012778b4752ae. In 151.462 seconds it completed the four
native suites, stored/Deflate self-setup lifecycles and their CRC/truncation refusals,
then read the actual CLI's typed product.inspect response. The response matched those
source revisions, JSON source_dirty=false, the generated build identity and the compiled
catalog/contract digests; package mode was source_checkout with verified=false.
Source observations and all five stable inputs remained unchanged. No retry occurred.

ROOT independently verified the original 2,074 artifacts, 1,307 selected archive members,
168 closed owned-command receipts and typed executed response, concluding
PASS_SOURCE_STATIC_ONLY. The actual product translation unit's FileTracker record still
has 152 dependency rows, zero worktree dependencies and no generated build identity header.
A preserved label correction distinguishes source-record keys from dependency rows and
selects the actual product object. The fresh run does not qualify incremental rebuilding.

[C4 custody](../../.aide/queue/active/FACMAN-0.1-ALPHA6-PROVIDER-CANARY-01/evidence/c4-CUSTODY.md)
retains the exact review, original receipts, correction attempts and artifact map. This
checkpoint records that tested source; it does not relabel its executables to a later
documentation or runtime commit. Installed/relocated consumption, interruption/replay,
protected successful publication, generation/recovery/cleanup, adoption, GUI/fullruntime,
real Factorio, continuous scheduling and release qualification remain open.


The later C5 run used clean FacMan
7dafa130225dadae824c377b76140622486c39b8 (tree
71d941bb1ccb5d54985cc49df3bdbc3367146408), after the normal source merge of
the reviewed f9d runtime/schema checkpoint. Local USK8d02 and stable ULK5479939c
were unchanged. A new empty source/static build and actual typed readback
completed in 155.314 seconds; the four native suites and synthetic
Stored/Deflate lifecycles passed, including causal CRC/truncation refusals.
The executable identified exactly those inputs and remained a source_checkout
with verified=false and candidate release coherence disabled.

The original metadata-only preflight failed before that source/static dispatch.
It was retained, and ROOT approved the narrowly corrected external byte
normalization preflight before the first effectful run. There was no automatic
retry. Independent review checked 2,464 original artifacts, 43 source inputs,
1,721 archived members and 259 closed owned-command receipts. All 286 physical
USK inputs matched across the four recorded boundaries. The product translation
unit still lacks worktree/generated-identity dependency tracking; the evidence
qualifies a fresh build only.

[C5 custody](../../.aide/queue/active/FACMAN-0.1-ALPHA6-PROVIDER-CANARY-01/evidence/c5-CUSTODY.md)
binds that independent review, original failure, corrected approval, actual
typed response and retained fixture effects. It preserves selected raw evidence
plus the complete external artifact byte roster; it does not contain all native
binaries or reconstruct omitted fixture trees. C4 remains unchanged.

Installed static/shared SDK consumption, relocation and consumer replay need
new admission and independent success/refusal oracles. The current local
source/static exception cannot admit those modes. Protected successful child
publication, generation/recovery/cleanup and adoption remain separately gated.
P6's current Windows product/startup/gallery evidence belongs to exact f9d
artifacts and its separate documentation checkpoint; it supplies no C5 package,
installed-SDK, GUI, hosted, game/human or release qualification.
