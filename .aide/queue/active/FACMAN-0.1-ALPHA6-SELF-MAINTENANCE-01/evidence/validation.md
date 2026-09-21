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
