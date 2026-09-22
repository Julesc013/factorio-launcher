# Validation

Source base: `c65c66ade1d4ca2c0c03b6b9aa78bfea2b977ae6`

Passed on 2026-09-16 in the marker-owned external task root against pinned
Universal Setup `279ad4876dc325f8e1fcdc918c91b098a11bc616` and Universal
Launcher `5479939ca5cb`:

- `py -3 tools/dev.py build developer --target facman_self_setup_recovery_smoke --configuration Debug`
- direct execution of the Debug recovery smoke: 62 checks passed
- `py -3 tools/dev.py build product --target facman_setup --configuration Debug`
- `py -3 -m unittest tests.test_self_setup_recovery_contract tests.test_package_manifests tests.test_product_candidate_workflow`: 36 tests passed; all 29 package manifests, 19 bundle layouts, 14 release profiles, and 14 package skeletons passed their checks
- `py -3 -m py_compile tests/integration/facman_self_setup_lifecycle.py`
- synthetic `facman_self_setup_lifecycle.py` against the built Debug setup executable
- AIDE task inspect/noop checks classify the WorkUnit as active/partial and
  direct continued work from its status and evidence
- `py -3 tools/project_state.py --write` and
  `py -3 tools/codegen/generate_metadata.py --write`, together with the
  canonical mutable-queue index projector and `tools/generate_plan_views.py`,
  refreshed their projections after activation and predecessor integration; all
  10 pre-existing `.aide/reports` files were byte/timestamp verified against an
  external snapshot, the two task-classification report absences were
  preserved, and the report tree retained no additional file
- the final `py -3 tools/strict_check.py` passed, including plan views, queue
  state, 426 schemas, package/profile/layout/skeleton checks, setup workflow,
  refusal contracts, code generation, security, and source formatting

The predecessor setup/native recovery WorkUnit has an exact integrated partial
checkpoint: PR #292 source `6ef1a9d3c95523b4e2b36aa5277ef498f555d523`,
source/merge tree `6fdbda15fd22db01c4de0794efed790a22b837ff`, CI run
`34976666277`, Windows package job `104406007552`, protected promotion rerun
`34976666335`, and dev integration
`c65c66ade1d4ca2c0c03b6b9aa78bfea2b977ae6`. The predecessor remains active
because that receipt does not qualify update/downgrade recovery. It also does
not qualify locked-file restart handoff or this WorkUnit's closure.

The real current-user lifecycle gained produced-package cases for uninstall
with the repair ZIP withheld, fresh registered repair with the ZIP withheld,
and plan-reviewed repair resumed from retained input. Those cases remain for
the gated Windows candidate job; they were not run against this workstation's
real Start Menu and HKCU registration.

Independent lifecycle review passed the runtime slice. Its first evidence
review rejected an incorrect terminal claim for the predecessor WorkUnit,
whose acceptance also requires update recovery. The predecessor task, status,
canonical plan and generated views now remain active/PENDING; its exact PR #292
receipt is explicitly PARTIAL with `workunit_closed=false`. The independent
re-review returned PASS after that correction.

## Hosted coverage timeout remediation

PR #296 run `34988087343`, job `104445285350`, checked out exact source
`9b42bf7f418c2c1fb9230fb41bc65ba3484f48d8`. Its coverage lane passed 46 of
47 CTests and passed coverage evidence generation and policy enforcement, but
`facman_self_setup_recovery_smoke` reached its 30-second CTest limit. The smoke
used the production second-resolution wait for each injected operation and had
already taken 28.63 seconds in the current-source Windows Debug matrix.

The remediation adds a narrow injected clock for tests and embedders. Null
production requests retain the bounded system-clock wait. Injected timestamps
must remain valid and strictly advance the bound; a new negative assertion
proves a non-advancing clock refuses before provider apply. The 63-assertion
recovery smoke now passes locally in 1.78 seconds without changing its
30-second test limit. Independent non-authoring review passed after the clock
surface was narrowed to advancing timestamps only. Full hosted requalification
remains pending on the successor commit.

The final local Debug rebuild and complete 45-test native matrix passed after
that review in 13.29 seconds; the recovery smoke took 2.16 seconds within the
parallel matrix. The 36 focused Python contract/package/candidate tests and the
426-schema strict check also passed.

## Side-by-side transition source checkpoint

Against exact base `b2f2465965cd72fe2e8e8d7dbddbca3f668095a8`, the new
transition and handoff source passed the focused Debug and Release matrices,
the Release `FacManSetup.exe` link, 42 adjacent Python tests, schema validation
for 432 schemas, source format, component ownership, code security, security
policy, portable AIDE Lite, and `git diff --check`. The complete current-source
Debug native matrix passed 47/47.

Independent non-authoring Sol review initially returned `CHANGES_REQUIRED` for
helper launch custody, deadline extension, incomplete activation continuity,
truncated physical identities, permissive phase schemas, and overstated
evidence. Re-review found source/target SemVer traversal and pre-execution path
revalidation gaps. A final re-review found rejected suspended-child cleanup was
not distinguished from confirmed closure. Each finding received a direct
regression and remediation. The final reviewer result was `PASS`; its own
handoff smoke rerun passed 1/1.

After deterministic project-state and metadata regeneration, the full strict
check passed with 131 commands, 432 schemas, and 290 refusal codes. The
checkpoint remains source qualification only: public verb/provider wiring,
two-package Windows lifecycle effects, and WorkUnit acceptance remain pending.

## Public setup and pinned-provider checkpoint

Source base: `f7779eaf71f0304a1b15c0eff2d866ce228ddade`

Passed on 2026-09-16 in the existing marker-owned external native developer
root:

- `cmake --build . --config Debug --target facman_setup facman_self_maintenance_smoke facman_self_maintenance_package_smoke facman_self_maintenance_provider_smoke`
- `ctest -C Debug --output-on-failure -R "facman_self_maintenance_(smoke|package_smoke|provider_smoke)"`: 3/3 passed
- `cmake --build . --config Debug --target ALL_BUILD -- /m` followed by
  `ctest --test-dir . -C Debug --output-on-failure`: 49/49 passed with no
  skipped or unrun tests in 51.66 seconds
- `py -3 -m unittest tests.test_self_setup_recovery_contract tests.test_self_setup_package`: 16/16 passed
- `py -3 -m unittest tests.test_generated_metadata tests.test_generated_frontend_catalogs`: 12/12 passed
- `py -3 -m py_compile tests/integration/facman_self_setup_lifecycle.py`
- `py -3 tests/integration/facman_self_setup_lifecycle.py --setup-exe <external-native-root>/Debug/FacManSetup.exe`: passed the isolated public update preview/apply, rollback preview/apply, and migrated-uninstall refusal journey
- `py -3 tools/codegen/generate_metadata.py --write`: passed
- `py -3 tools/source_format_check.py`: passed
- `py -3 .aide/scripts/aide_lite.py test`: passed
- `py -3 .aide/scripts/aide_lite.py task inspect --task-id FACMAN-0.1-ALPHA6-SELF-MAINTENANCE-01` and `task noop-check`: active/partial, continue from status and evidence, no mutation
- `py -3 tools/strict_check.py`: passed, including 432 schemas, 131 commands, 290 refusal codes, source formatting, security, package/profile/layout/skeleton, queue, and generated-view checks
- `git diff --check`: passed at closeout

The focused native provider smoke includes direct refusals for out-of-authority
roots before any provider call, replayed plan identity, empty apply payload,
mismatched apply transaction, report replay, stale verification time, changed
ownership, changed summary, and changed report digest. The core smoke proves
preview calls provider planning without retention and that plan refusal leaves
no coordinator maintenance directory.

This is local source validation. It is not the pending complete native and
Python matrices, product candidate qualification, real current-user shell run,
or two source-distinct produced-package receipt required for WorkUnit closure.

## Final remediation of the public-provider review

The final review corrections retain full generation install identities through
the provider's derived-record limit, move absent-coordinator refusal after the
read-only provider plan, revalidate held coordinator authority on the only
creation path, require completed retries to inspect and verify without writes,
and bind the no-shell route to a marked, expiring, root-specific fixture permit.

The first isolated lifecycle replay exposed a real provider limit: a full
generation install ID plus the prior transaction label made Universal Setup's
derived ownership identifier exceed its 128-character limit. The fix keeps the
full generation ID and shortens only the opaque transaction label. The replay
then passed.

After that remediation, the existing external Debug root passed the three
self-maintenance native CTests (3/3), 28 focused Python
contract/generated-metadata tests, metadata regeneration, source formatting,
portable AIDE Lite validation, `git diff --check`, and the isolated public
update-preview/apply, rollback-preview/apply, and migrated-uninstall-refusal
lifecycle. A fresh single Debug CTest matrix then recorded all 49 tests as
passed. The earlier overlapping duplicate CTest attempt left a stale
`LastTestsFailed.log` entry for the otherwise-passing maintenance smoke; it is
not used as qualification evidence. The historical 49/49 receipt above remains
an earlier-source observation, while the fresh matrix is the final-remediation
source evidence.

## PR #299 Windows path-capacity remediation

The hosted Windows lifecycle on `dc927ee5` refused the update plan before
effects because the former physical root embedded two 256-bit digests and a
payload file exceeded the 259 UTF-16-code-unit limit. The source now derives
one domain-separated 256-bit physical-root commitment from the normalized
logical-root identity and the full generation identity. It does not shorten the
generation ID or `install_id`.

The exact immediately preceding sibling form,
`FacMan.generation.<logical-root-sha256>.<generation-sha256>`, remains
read-compatible only for immutable retained records. The native regression
discovers that record, updates it into the current one-digest mapping, rolls
back to it, and separately refuses arbitrary absolute siblings and legacy
alternate roots.

The external Debug root rebuilt `facman_self_maintenance_smoke` and
`FacManSetup`; the focused native smoke passed. The real synthetic public
lifecycle then passed with `--ci-length-root`. Its controlled temporary root
measured 72 UTF-16 units against the hosted failing root's 63; the hosted
predecessor payload reference measured 261 units, while the exercised compact
provider payload measured 205, below the 259-unit limit. The core regression
also checks deterministic same-input mapping, distinct-generation mapping,
full install IDs, exact side-by-side record mapping, legacy-root equivalence,
and the resulting CI-length GUI path budget.

## PR #299 hosted portability follow-up

The compact-root successor initially supplied a Windows `C:/...` runner path
to its native path-budget assertion on every platform. On Linux that path is
relative, so `plan()` correctly refused it and the hosted Linux native and
coverage jobs failed before product behavior ran. The Windows path-budget
assertion is now compiled only on Windows; deterministic mapping, predecessor
compatibility, arbitrary-root refusal, identity, discovery and rollback checks
remain cross-platform.

The existing external Debug root rebuilt
`facman_self_maintenance_smoke`, and its focused CTest passed 1/1. Source
formatting and `git diff --check` passed. Fresh hosted requalification of the
successor commit remains pending.

## 2026-09-16 gated candidate preparation validation

The source-level workflow guard and lifecycle/package contract regressions pass
for the new optional transition route. This is not a produced-package or host
qualification: alpha.5 is intentionally not eligible to supply both package
identities, and no alpha.6 package pair has been built. The required later run
must retain its exact A/B source revisions, provider lock, package hashes,
native command receipts, Start Menu/HKCU observations, and durable generation
and activation records.

`C:\Users\Jules\AppData\Local\FacMan\Development\repositories\factorio-launcher-5db2844e2f29\tasks\beta1-admissi-68051e628e\python\Scripts\python.exe -B -m unittest tests.test_product_candidate tests.test_product_candidate_workflow tests.test_self_maintenance_candidate tests.test_self_setup_package tests.test_self_setup_recovery_contract`
passed 51 tests on the preparation source. `py_compile` of the candidate tool,
lifecycle harness, and its focused test, plus `git diff --check`, passed. The
suite's intentional negative package-contract and provenance messages were
observed inside passing tests.

## 2026-09-16 candidate-review remediation validation

The retained-generation correction was built in the existing external Debug
root. All eight setup-labelled native tests passed, including the new exact
legacy A -> physical B -> retained A -> B regression and the complete fixture
lifecycle. `FacManSetup.exe` also rebuilt from the corrected application entry.
The focused Python matrix passed 55 tests covering candidate/package contracts,
workflow handoff, strict setup identities, canonical SemVer, exact generation
and activation records, physical-root shell assertions, and recovery contracts.
Pinned-Python `py_compile`, `tools/source_format_check.py`, and
`git diff --check` passed. The complete strict check passed with 432 schemas,
131 commands and 290 refusal codes; its engineering-quality and generated-view
checks remained current. No real current-user effect path was executed; the
optional alpha.6 hosted qualification and its retained evidence remain pending.

## 2026-09-16 candidate evidence-admission review corrections

Pinned-Python `py_compile` passed for the candidate tool, real transition
harness, candidate tests, and workflow tests. The focused candidate/workflow
set passed 28/28. The broader candidate, workflow, setup-package, and recovery
matrix passed 57/57; its package-contract and GitHub-provenance diagnostics are
intentional negative cases inside passing tests.
The same candidate/workflow set passed under WSL Python with 28 tests run and
one existing platform-conditioned case skipped; this is cross-platform source
validation, not physical-Linux product qualification.

`tools/source_format_check.py` and `git diff --check` passed. The product
candidate workflow remains exactly 516 lines. The tests include fixed generation
and physical-root derivation vectors, substituted generation/install/logical
root refusals, exact retained-legacy admission, hard-linked and symlinked repair
input refusals, stable ownership-marker validation, and preservation of staged
baseline artifacts with `produced_unqualified` status after a failed
payload-equivalence gate. No C++ changed in this review pass, so the already
passing native legacy A/B/A/B regression was not rebuilt or relabelled. No real
current-user effect path was executed.

The final focused review correction derives legacy-target mode solely from the
caller's retained-predecessor contract. The 9 candidate-tool tests pass with a
negative proving that an otherwise coherent physical side-by-side A response
and record cannot replace the required retained `facman.self` logical-root A.
Pinned-Python compilation, source formatting, and `git diff --check` pass.

## 2026-09-21 restart-safe lifecycle epoch routing

Source base: `f8cb69e62c2fd5f9f59094dd3b1ba1d6cde58174`

The current-source Windows developer root passed:

- a complete Debug build and 49/49 CTests in 198.90 seconds;
- a later focused rebuild after the final provider-interface correction, with
  `facman_self_setup_lifecycle`, `facman_self_maintenance_smoke`, and
  `facman_self_maintenance_provider_smoke` passing 3/3;
- the isolated public setup lifecycle, including matching pre-handoff epoch
  continuation, mismatched-request refusal, and the existing update, downgrade,
  rollback, and migrated-uninstall controls.

The current-source Ubuntu 24.04 external root rebuilt and passed
`facman_posix_child_lifecycle_smoke`, `facman_posix_process_pump_smoke`,
`facman_posix_process_pump_socket_smoke`, and
`facman_self_maintenance_smoke` (4/4). After the final provider-interface
correction, the directly affected maintenance smoke rebuilt and passed again.
This is WSL execution evidence, not physical-Linux product qualification.

Pinned Python passed 74 tests across product candidate, candidate workflow,
self-maintenance candidate, setup package, recovery contract, generated
metadata, and generated frontend catalogs. The integration lifecycle compiled
with `py_compile`. `tools/strict_check.py` passed with 436 schemas, 131
commands, and 290 refusal codes. Source formatting, portable AIDE Lite,
task inspect/noop, Git policy, `git diff --check`, and protected-report
restoration also passed.

The full 49-test Windows matrix predates only the explicit pure-virtual
declaration and the raw-provider refusal for offline retention. The three
directly affected setup/maintenance/provider tests rebuilt and passed after
that correction; no broader product behavior changed.

## 2026-09-22 macOS override portability correction

PR #317's first `macos-native-cli` build failed before test execution because
Clang diagnosed seven inherited `ProviderBridge` declarations without explicit
`override` under `-Winconsistent-missing-override -Werror`. The declaration-only
correction rebuilt `facman_self_maintenance_smoke` in the existing Windows and
Ubuntu 24.04 external roots. The focused test passed in both roots (31.08 and
9.47 seconds respectively). `tools/source_format_check.py` and
`git diff --check` passed. The corrected hosted macOS result remains pending;
the failed run does not qualify macOS behavior.

## 2026-09-22 external retained-helper handoff

Source base: `ea43094b2dfa8d4b2b80fe3b2811e2a50bacafda`

The existing Windows Debug root rebuilt `FacManSetup` and
`facman_self_maintenance_smoke`. The final focused lifecycle regression passed
after adding a provider-reviewed staged-v3 fixture. A second public apply
promotes the staged journal and relaunches the retained helper while the
initiating process remains outside continuation effects. The normal packaged
case reaches `shell_cutover_complete` through the real retained Setup helper.
The earlier invalid synthetic attempt was retained as a failed test
observation; it used a fake provider-plan digest and the product correctly
refused it before effects.

The affected Windows validation passed:

- `facman_self_setup_lifecycle`: 1/1 in 166.58 seconds, including normal
  external handoff, strict private-input refusals and staged public retry;
- the preceding final focused run passed
  `facman_self_maintenance_smoke`,
  `facman_windows_maintenance_handoff_smoke`, and
  `facman_self_setup_lifecycle` 3/3 in 90.16 seconds before the staged retry was
  added;
- the pinned-Python provider-controller and candidate/workflow matrix passed
  48/48 in 7.849 seconds.

The Ubuntu 24.04 WSL external root rebuilt and passed the directly affected
maintenance smoke. This is cross-platform source/native evidence, not physical
Linux product qualification. `tools/strict_check.py` passed with 436 schemas,
131 commands and 290 refusal codes. Source formatting, Python compilation,
portable AIDE Lite validation and `git diff --check` passed.

An independent non-authoring source review traced current-helper/target-helper
separation, exact parent wait, strict private arguments, canonical journal
derivation, pinned launch, one absolute deadline, no post-launch public
effects, v3 recovery, shell binding and Job-empty containment. Its verdict was
PASS with no source-safety blocker. Its one suggested packaged retry case is
the staged-v3 public regression recorded above.

PR #320 run `35633030665` then exposed two bounded CI failures. The Windows
Debug lifecycle exceeded its unchanged 180-second CTest limit because two full
continuations were duplicated and the private child retained the caller's
captured standard handles. The Linux coverage job passed 49 other CTests and
preserved its evidence, but the resource export child reached its fixed
30-second limit after the other coverage-instrumented resource CLI children
also took about 27 seconds each. No timeout or coverage policy was increased.

The corrective successor isolates the private Windows helper with explicit
inherited `NUL` handles and `CREATE_NO_WINDOW`, polls the immutable terminal
record before invoking the public read-side observer, reuses the first active
epoch for staged retry, and limits that second case to staged promotion plus
exact helper launch. One full packaged continuation remains. The unchanged
Windows gate now passes `facman_self_setup_lifecycle` in 111.31 seconds; the
focused four-test set passes in 143.08 seconds, including maintenance smoke in
30.73 seconds, provider smoke in 0.29 seconds, and handoff smoke in 0.57 seconds.
Ubuntu 24.04 WSL rebuilt and passed the maintenance and provider smokes 2/2 in
9.46 seconds. The pinned-Python provider/candidate matrix passed 61/61 in 9.673
seconds; source formatting, Python compilation, and portable AIDE Lite also
passed. The full strict repository check passed with the current 436 schemas,
131 commands, and 290 refusal codes. Exact hosted Windows and coverage
requalification remains pending.

PR #320 run `35640200272` then passed Linux coverage in 6 minutes 45
seconds without changing its 30-second resource-child limit or coverage
threshold. Windows Debug reached the corrected external continuation, but the
fixture stopped observing it after 65 seconds even though the product has one
existing 600-second absolute handoff deadline. The still-running continuation
held the installed target executable, so temporary-root cleanup correctly
refused deletion instead of hiding the live process. The fixture observation
cap is corrected to 120 seconds within the unchanged 180-second outer CTest
gate, leaving the remainder for the staged-launch regression and cleanup.
The exact local Windows Debug lifecycle then passed in 112.21 seconds; Python
parsing, source formatting, and diff checks also passed. Exact hosted
requalification remains pending.

This checkpoint does not claim the source-distinct produced-package Windows
A/B lifecycle, real Start Menu/HKCU effects, physical Linux/macOS package
behavior, chain-aware repair/removal or human acceptance. Those exits remain
active.

## 2026-09-22 hosted Debug archive-cost correction

PR #320 run `35642988291` passed Linux native, Linux coverage, macOS CLI,
macOS archive, AppKit, CodeQL, C/C++, C#, Python, security policy, synthetic
provider and promotion checks. Its Windows job built successfully and passed
48/49 native tests, but `facman_self_setup_lifecycle` reached the unchanged
180.01-second CTest timeout. This was an outer timeout rather than a reported
product refusal or failed assertion.

A retained local run recorded the external helper's exact phase sequence from
`00-handoff-ready.v3.json` through `80-registration-cutover.v2.json`. Changing
only the synthetic maintenance archives from stored to admitted Deflate reduced
each archive from 7,429,970 to 2,220,607 bytes and the complete exact lifecycle
passed in 81.04 seconds. The ordinary lifecycle still covers stored archives;
the external helper, provider, publication, shell, mismatch and staged-retry
assertions all remain. No product deadline, outer CTest timeout, test selection,
coverage threshold, or assertion changed. Exact hosted requalification remains
pending.

The corrective successor also passed 53 focused Python candidate, workflow,
setup-package and process-controller tests, source formatting, the full strict
repository check (436 schemas, 131 commands and 290 refusal codes), portable
AIDE Lite validation, Python parsing and `git diff --check`.

## 2026-09-22 source-distinct predecessor product correction

Run `35662564497` tested exact source
`171eb897e3390078a73a9d300593a22ce3a3984f`. Linux completed in 5 minutes 17
seconds and macOS in 10 minutes 23 seconds. Windows passed 49/49 native tests,
the current-source product package and current-user setup lifecycle, then
failed while constructing the detached Alpha.5 predecessor product. The first
failure was `package-build: missing built artifact for
apps/gui/windows/winforms`; no source-distinct A-to-B transition was entered.
The retained Windows job log has SHA-256
`e77129aa8d46fb97e416ea2357e7c9b10e5e662d1a670e9f1fabfa68ee3f5d78`.

The successor builds predecessor WinForms through the predecessor checkout's
own helper and predecessor-owned output root before package construction.
Validation passed:

- 32 focused self-maintenance candidate and workflow tests;
- 120 broader candidate, package-contract, resource-proof and development-root
  tests, with one platform-conditioned skip;
- Python compilation, source formatting and `git diff --check`;
- full strict validation with 436 schemas, 131 commands and 290 refusal codes.

The exact hosted rerun is pending. The Linux/macOS successes retain their
original source scope, while the Windows source-distinct transition and final
six-asset bundle remain unqualified.

## 2026-09-22 predecessor WinForms output binding correction

Run `35668651886` was bound to source
`05016bb154c147b0926642f190437f3578bc1dfa` and Alpha.5 baseline
`203321188f88cc5587bd95ff6b4da4a602c745d2`. Linux and macOS passed. The
Windows job completed the current-source package and real current-user setup
lifecycle, then built the detached predecessor native and WinForms products.
The WinForms build succeeded at the owned external path, but the Alpha.5
package builder was not given `FACMAN_WINFORMS_OUTPUT_ROOT` and refused its
required `apps/gui/windows/winforms` component before the A-to-B transition.
The retained Windows log has SHA-256
`16a35e340277437b85432624915e226783188dd5d18e4e5e9340295c7c7535ff`.

The successor sets that existing package input to the same predecessor-owned
`winforms-product/Release` directory used by the build helper. The focused
candidate, workflow, and external-component staging selection passed 40 tests.
The broader candidate/package matrix passed 120 tests with one
platform-conditioned skip; Python compilation, source formatting, diff checks
and full strict validation with 436 schemas, 131 commands and 290 refusal codes
also passed. Exact hosted requalification remains pending. No source-distinct
transition, six-asset candidate, release, or publication claim follows from
the failed run.

## 2026-09-22 predecessor CI source-identity correction

Run `35673461778` was bound to source
`bd838f1b92c976f9c6138d188a8d978ede023fd1` and Alpha.5 baseline
`203321188f88cc5587bd95ff6b4da4a602c745d2`. Linux and macOS passed. Windows
accepted the predecessor's external WinForms output, then the Alpha.5 package
provenance check refused with `GitHub source SHA disagrees with packaged source
revision`. No source-distinct A-to-B transition was entered. The retained
Windows job log has SHA-256
`810aecce911eb98b9d9680585bbdec4c2eac857ae4694633a055fc147b2058b5`;
the downloaded GitHub artifact digest is
`c7bdbc744d3b1c938f67990df16470f7e3cb94ff33191a2488a374feff86cfcf`, and the
1,623-entry local evidence manifest has SHA-256
`2abd735a549f4de76bbc010c145ea6e85276b362b5657fe2bb7e1732ac707c68`.

The successor binds `FACMAN_CI_SOURCE_SHA` to the exact resolved predecessor
revision. Its regression starts with conflicting candidate and stale explicit
CI identities, proves the predecessor value replaces the explicit identity,
and proves the outer candidate `GITHUB_SHA` remains unchanged. The focused
candidate, workflow, and external-component staging selection passed 40 tests.
The broader candidate/package matrix passed 120 tests with one
platform-conditioned skip. Python compilation, source formatting, diff checks,
portable AIDE testing and validation, and the full strict check passed. The
strict result retains 436 schemas, 131 commands, and 290 refusal codes. Exact
hosted requalification remains pending; no transition, six-asset candidate,
release, or publication claim follows from the failed run.

## 2026-09-22 current-contract predecessor audit correction

Run `35678300868` was bound to source
`d94166a2337ca27794881212586c7bce92cd48a2` and Alpha.5 baseline
`203321188f88cc5587bd95ff6b4da4a602c745d2`. Linux and macOS passed. Windows
passed the current-source native, package, resource and real current-user setup
work, then produced the exact detached Alpha.5 portable and Setup artifacts.
The predecessor's historical package auditor refused the Setup payload because
its setup-overlay ownership catalogue omitted the legitimate
`facman/state/self-maintenance-package.v1.json` file. The transition was not
entered.

The retained Windows job log has SHA-256
`b6ffa34ed4fd54c31610f633ce1e224bfd422d7e457950a77382ade95a22b47c`;
the downloaded GitHub artifact digest is
`1984e17c0a79700f48e170bfdac4894a6df075e2099a869d5b19ac44c50263fc`, and the
1,741-entry local evidence manifest has SHA-256
`e85d5b741f395ecd9bece78df3a7ff8590f761236d5d93ec4355b03229773707`.
The retained portable has SHA-256
`b4ef9a2606b4ad462a8bd6c1d57179ad892eb3aa061326f95cc91ca20bba7764` and the
retained Setup has SHA-256
`139efc98637e7b98b4866f105a11ed9f84e6774f48c7540925c80610483ae6bf`.

Replaying those exact artifacts through the current source's
`windows_setup_overlay_v1` auditor passed without artifact changes. Its
`current-auditor-equivalence.v1.json` receipt has SHA-256
`80a0c55f3ad92586d408166761d7ac34ab118f2d943af535bbc2668c90a6a422`
and binds all 115 canonical files. The successor changes only the auditor
selection after Alpha.5 production. Its focused candidate, workflow and
external-component staging selection passed 40 tests. The broader candidate,
package, resource and development-root matrix passed 120 tests with one
platform-conditioned skip, and the current package-contract TCK passed 14
tests. Python compilation, source formatting, diff checks, portable AIDE
testing and validation, and the full strict check passed. The strict result
retains 436 schemas, 131 commands and 290 refusal codes. Exact hosted
requalification remains pending; no transition, six-asset candidate, release,
or publication claim follows from the failed run or local replay.

## 2026-09-22 predecessor produced-name identity correction

Run `35683529084` was bound to source
`e94142405f868f996f555916279fb1428a65c1ea` and Alpha.5 baseline
`203321188f88cc5587bd95ff6b4da4a602c745d2`. Linux and macOS passed. Windows
passed the current-source native, package, resource and real current-user setup
work, then produced the exact Alpha.5 portable and Setup artifacts. The current
package-contract TCK passed all 115 canonical files and the three admitted
setup-overlay files. Identity admission then refused before transition because
the retained portable evidence filename was
`windows-self-maintenance-baseline-portable.zip`, while the Setup correctly
bound the produced filename
`FacMan-0.1.0-alpha.5-windows-x64-portable.zip`. The bytes and SHA-256 were
identical.

The retained Windows job log has SHA-256
`637f3498ca16f503f86d1d3791a867e4730f3ed9b2770765570d8bcfd951619f`;
GitHub artifact `10675968541` has digest
`0a324598abad7e0d1522eaa5ffb7e5a70dfbe2f4bd55b5d88d8daeeb1579465c`,
and the 1,626-entry local evidence manifest has SHA-256
`90f190f3a83d17787aae4ded62c0deae018da038fa91d9e0fed7ca2ac0494457`.
The retained portable and Setup SHA-256 values remain respectively
`b4ef9a2606b4ad462a8bd6c1d57179ad892eb3aa061326f95cc91ca20bba7764`
and `139efc98637e7b98b4866f105a11ed9f84e6774f48c7540925c80610483ae6bf`.

The successor validates identity against the original produced names and
bytes, then independently requires each original and renamed retained copy to
match the retained byte count and SHA-256 record. A regression accepts the
legitimate renamed retained copies and refuses a changed retained portable.
The focused candidate, workflow and external-component staging selection
passed 41 tests. The broader candidate, package, resource and development-root
matrix passed 121 tests with one platform-conditioned skip, and the current
package-contract TCK passed 14 tests. Python compilation, source formatting,
diff checks, portable AIDE testing and validation, and the full strict check
passed. The strict result retains 436 schemas, 131 commands and 290 refusal
codes. Exact hosted requalification remains pending; no transition, six-asset
candidate, release or publication claim follows from the failed run.

## 2026-09-22 retained Setup-overlay identity correction

Run `35688220467` was bound to source
`d84e464b00fa8a533399c59b266f107de9a63f7e`, tree
`da6efdeaafa9b51ecdeea8c13335a32b741184b4`, and Alpha.5 baseline
`203321188f88cc5587bd95ff6b4da4a602c745d2`. Linux and macOS passed. Windows
completed the current-source package and real current-user setup lifecycle,
produced and audited the exact Alpha.5 portable and Setup products, and then
installed Alpha.5 from that source-distinct Setup. Its real shortcut and HKCU
registration bound repair to
`b5cdf9d768e192e2c1b877625b05577b910ba061d79d95a15777b7d2965aadc7.zip`.
The harness incorrectly supplied the outer Setup executable SHA-256
`139efc98637e7b98b4866f105a11ed9f84e6774f48c7540925c80610483ae6bf`
as the expected retained-package identity and stopped at the first post-install
assertion. No update, downgrade, repair, rollback or removal phase ran.

The retained Windows log has SHA-256
`833186e8c3c0965952965f0ca67667cfbb8e1263aa8ba85f239900a96b120d25`;
GitHub artifact `10678237103` has digest
`462ff805fbed0424efa59b6dce57bbe7b80a5bde8bb71f621db34f0a2d5e9760`,
and the 1,624-entry local evidence manifest has SHA-256
`6e05c68c21aedfb9be23d87c3c1c22b5f35673b91ba236110f600cd94948647e`.
The transition attempt and retained lifecycle receipts have SHA-256 values
`0ea744fa4e4dd957fa910b5bfe66f332c8b505719ddd0c3201f0212923deb59a`
and `2c7dff5bda8cb63f5e9bab5575475bc33281ae964346bb8d590f1e580992b783`.

The successor's exact overlay reader computes `b5cdf9d7...` from the retained
Alpha.5 Setup, matching the installed repair-source filename and registry
commands. Its regression proves a prefixed Setup and the corresponding pure ZIP
have the same materialized digest and refuses foreign trailing bytes. Fifteen
focused tests and the 107-test broader candidate/package matrix pass. Python
compilation, source formatting, diff checks, portable AIDE testing and
validation, and the full strict check pass; the strict result retains 436
schemas, 131 commands and 290 refusal codes. Exact hosted requalification is
pending, and the failed run grants no transition, final candidate, release or
publication claim.
