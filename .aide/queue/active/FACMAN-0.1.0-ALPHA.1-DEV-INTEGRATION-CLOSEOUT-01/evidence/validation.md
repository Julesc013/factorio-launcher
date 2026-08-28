# Validation

The closeout binds PR #191 to protected `dev` merge commit
`06f0f7c9084ad90c59b09c5691847791ddc7dd85`, tree
`ffeb7b092f4c8f2a55f5418068593677d5426670`, the exact two parents, actor
`Julesc013`, all seven hosted workflow runs, and all 20 successful merge-head
checks. Exact ULK and USK commit/tree identities are retained in
`release/index/alpha1_dev_integration_closeout.v1.toml`.

The original final-integration WorkUnit was reviewed, closed, and archived at
`.aide/history/facman-0-1-alpha1-final-integration-merged-2026-08-28/` after its
stale package/CodeQL risk was reconciled. PRs #188, #189, and #190 were already
marked merged by GitHub at the #191 merge because all three heads are ancestors
of the normal merge commit; none was merged a second time.

Closeout validation includes:

- exact merge-receipt checker and negative tests;
- 384-schema validation;
- alpha source, three-package asset assembly, tag policy, publication boundary,
  and no-clobber portable packet tests;
- release programme, branch policy, CI proof, release identity, AIDE queue,
  project-state, generated metadata, and plan-view validation;
- Python compilation for all new and changed release tools;
- clean-clone native configuration/build plus 39 of 39 CTest cases passing;
- clean-clone local obligation evidence with 1,265 tests, zero failures, zero
  errors, zero unknown skips, and the following classified skips: two optional,
  one required-blocked, five unsupported, and two not-applicable;
- clean-clone strict validation with exact fresh ULK and USK checkouts and all
  384 schemas passing;
- normal exact-head pull-request checks before protected integration.

The first protected closeout merge-head CI run (`33178491848`, attempt 1)
exposed a Windows-only timing weakness in
`facman_presentation_service_smoke`: 38 of 39 Debug tests passed, and that test
failed without diagnostics after 5.36 seconds. Its unique five-second
transport-fixture dispatch wait is the only failure path consistent with that
duration; every other synchronization bound in the test is ten seconds. The
same exact merge commit and tree passed 39 of 39 native tests in a fresh local
checkout, and the affected executable then passed 15 consecutive runs. The
closeout repair aligns the outlier bound with the existing ten-second waits and
emits a specific timeout diagnostic. A fresh build against the exact pinned
providers passed the repaired smoke test 20 consecutive times and the full
Debug native suite 39 of 39. This is test reliability hardening; it does not
alter product runtime behavior or authority.

The first exact-final-dev qualification run (`33185567254`) passed release
source preflight, then failed before cloning any qualification root because
the documented `python tools/alpha_qualification.py` entry point could not
import the repository `tools` package. Unit tests had imported the module and
therefore did not exercise script-mode path initialization. The same workflow
step then attempted asset assembly after the failed producer because PowerShell
did not treat the native exit code as terminating. The closeout repair adds the
standard repository-root bootstrap, a subprocess regression test for the exact
documented invocation, and explicit native-command fail-fast behavior. No
package from the failed run exists or is accepted.

The second exact-final-dev qualification run (`33191075579`) proved the repaired
entry point and fail-fast behavior, cloned root 1, and then stopped before any
build because the producer requested `--filter=blob:none` for all three source
repositories. The checkout-observation policy correctly rejects partial-clone
configuration and promisor packs, and a local exact reproduction preserved the
seven resulting source-safety findings. The closeout repair removes the partial
clone filter so every qualification input is a full, non-promisor clone and
adds a regression test that forbids filter/depth arguments. No package from the
failed run exists or is accepted.

A local real-clone probe using the repaired helper cloned FacMan at
`608056ea0962388f4a6c074a3317d17cbb677cf1`, ULK at
`5479939ca5cbc9ee0f901608a92012778b4752ae`, and USK at
`d2a2aae7e61c47035c92334b0522143b4fea3880` without filter or depth options.
The cloned FacMan `current_checkout_observation.py` accepted the exact source,
providers, Windows line-ending profile, full object stores, and non-promisor
configuration.

Local repair validation passes the exact script invocation, all 19 focused
asset-set and CI-proof tests, CI proof, AIDE queue state and target truth,
portable AIDE Lite self-test, and `git diff --check`. The broader local strict
check passes its release source, closeout, portable packet, tag policy,
publication boundary, CI proof, source format, and all 384 schema gates. Its
aggregate result remains non-authoritative because the operator workspace
contains preserved `.aide.local`, `.vscode`, and `tmp` trees and its sibling ULK
and USK worktrees are not currently at the release pins; the prior exact-pinned
clean-clone strict evidence remains the authoritative full-profile result.

The local-profile required-blocked skip is the intentionally absent shared
WinForms build in the native smoke root. It does not satisfy final
qualification; the final three-root producer builds the shared Debug and
Release matrices and WinForms Release explicitly, and its result must pass
before any later decision. The unsupported skips are Windows symlink-privilege
cases, the not-applicable skips are POSIX PTY cases covered separately by the
Windows ConPTY lane, and the optional skips are the absent shared install-tree
fixture and opt-in bounded performance corpus.

The machine qualification producer now rebuilds the static and shared Debug and
Release native matrices, WinForms Release, and all three exact packages in
three fresh roots. Its schema freezes source/provider/package/ABI/contract/state
identity plus package tree, archive, embedded manifest, SBOM, provenance,
licence inventory, file count, uncompressed bytes, and archive bytes. Final
values are deliberately deferred until this closeout reaches protected `dev`.

No tag, release, publication, signing, support, main promotion, route promotion,
Factorio execution, or human verdict is created by this evidence.
