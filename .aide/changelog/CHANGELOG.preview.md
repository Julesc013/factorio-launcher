# AIDE Changelog Preview

This file is generated from local Git history and is a preview only.

source_range: 29cf22fa..HEAD
source_head: 2671ca55d91d87e32f48b28890768339820b2d5d
commit_count: 50
malformed_count: 8
preview_only: true
release_publishing: false

## Summary

- Added: 16
- Changed: 14
- Fixed: 16
- Security: 9
- Docs: 5
- Tests: 11
- Internal: 2
- Risks: 2

## Added

- stable, local-only mod inventory and verification commands for R3.7. (8335fde1ba12 feat(mods): add stable local inventory)
- deterministic bounded local dependency plans and transactional modset apply and rollback. (b93d7376c625 feat(modsets): add bounded local solver)
- bounded save indexing, sidecar association, drift detection, structural diff, and reversible retention. (2e9a66f8a4bd feat(saves): add structural index and retention)
- secret-free dedicated-server planning and portable export bundles. (578bfb57bf82 feat(servers): add non-executing plan bundles)
- generated guided operational forms and cross-frontend result visualizations. (dedadfa2f95e feat(frontends): generate guided operational forms)
- Cross-transport lifecycle, adversarial, and release-scale R3.7 proof coverage. (625a964355d0 test(lifecycle): prove R3.7 cross-transport journey)
- Required Linux Release build and CTest evidence to the cross-platform closeout matrix. (81abee2fb122 ci(linux): add explicit Release proof)
- Exact R3.7 lifecycle checkpoint with target-native evidence and honest authority boundaries. (6cce8ed15a8f docs(release): freeze the R3.7 lifecycle checkpoint)
- Generated R3.7 review and branch-workflow evidence. (1f840e533774 chore(aide): preserve R3.7 review evidence)
- Canonical machine-readable R3.7 and H1-pending project status. (9539338419c5 fix(truth): establish the R3.7 H1-pending authority plane)
- Declarative request-field contracts and generated native boundary validators. (49101f7acfba feat(contracts): generate and enforce native request boundary law)
- experimental relocatable FLB 1.2 installed SDK and compatibility metadata. (2f4f7b5460b2 feat(sdk): establish the experimental FLB 1.2 consumer boundary)
- Sanitized, digest-bound H1 operator verdict and checkpoint. (6d3c61c009ab docs(evidence): record H1 Fail for Steam-backed candidate)
- explicit install-origin and external-state isolation metadata. (08cf8a58fb17 feat(installs): classify external-state isolation eligibility)
- Steam external-state refusal and explicit preview/preflight write-domain policy. (a06669155e57 fix(launch): refuse Steam external state in strict mode)
- sanitized Factorio version capability corpus tooling and contract. (e74255d5209c feat(compat): add read-only Factorio version capability corpus)

## Changed

- R3.7 wave state now records local mod inventory as closed and verified. (05a93277d739 chore(aide): close local mod inventory workunit)
- R3.7 wave state now records the local modset solver as closed and verified. (7ad66aea23d7 chore(aide): close local modset solver workunit)
- R3.7 wave state now records structural save intelligence as closed and verified. (b30e4a70272e chore(aide): close save intelligence workunit)
- R3.7 wave state now records server planning as closed. (d90d461a99dd chore(aide): close server planning workunit)
- R3.7 wave state now records operational UX as closed. (9af53a736f47 chore(aide): close operational UX workunit)
- R3.7 wave state now records WU10 as closed with advisory-only evidence. (b6e8e6200b9e chore(aide): close R3.7 lifecycle proof)
- R3.7 AIDE state is closed with advisory-only evidence and no automatic human or release promotion. (dcd9a6cbb0d2 chore(aide): close the R3.7 wave)
- Current status and platform claims are generated and evidence-qualified. (9539338419c5 fix(truth): establish the R3.7 H1-pending authority plane)
- Command schemas and frontend catalogs derive field constraints from the same source. (49101f7acfba feat(contracts): generate and enforce native request boundary law)
- client transports are independently linkable and daemon IPC remains explicitly unavailable. (6dce5c194457 refactor(client): separate model and transport link boundaries)
- Canonical status now reports the Steam-backed H1 Fail and active narrow repair. (6d3c61c009ab docs(evidence): record H1 Fail for Steam-backed candidate)
- Steam, standalone, archive, manual, and package installs now receive conservative isolation classifications. (08cf8a58fb17 feat(installs): classify external-state isolation eligibility)
- Steam preflight is refused even when instance-local config routing is structurally valid. (a06669155e57 fix(launch): refuse Steam external state in strict mode)
- Canonical project truth now records no active WorkUnit and the closed repair identity. (2671ca55d91d docs(closeout): bind and close the R3.8 repair)

## Fixed

- Cross-workunit lifecycle correctness and generated-client compatibility defects found by R3.7 end-to-end proof. (9fea4325129c fix(lifecycle): close cross-workunit integrity gaps)
- Native transaction smoke no longer leaves an empty source-tree directory after passing. (8556b05e033a test(transaction): clean native smoke workspace)
- Linux and macOS warnings-as-errors portability failures in preferences and modset planning. (4d542308f806 fix(portability): satisfy GCC and AppleClang warnings)
- Linux and macOS launch-reference compilation no longer depends on omitted aggregate fields. (02398db38063 fix(portability): initialize launch profile defaults)
- Cross-platform TUI smoke compilation now matches the complete generated-client invocation shape. (681a614ea193 test(tui): initialize complete invocation shape)
- Profile archive now uses a directory-safe atomic no-clobber move on POSIX. (774628f442b0 fix(profiles): archive directories atomically on POSIX)
- Made the R3.7 public-integration addendum satisfy Linux source-format policy. (2190b044ad86 docs(release): wrap R3.7 integration evidence)
- Coverage is aggregated by module and release structure is no longer called readiness. (9539338419c5 fix(truth): establish the R3.7 H1-pending authority plane)
- `modsets.rollback` now enforces its required lowercase SHA-256 transaction identity at the native boundary. (49101f7acfba feat(contracts): generate and enforce native request boundary law)
- Cross-platform safety refusals retain invalid_identifier instead of degrading to invalid_request. (514413661f13 fix(contracts): preserve identifier refusal semantics at decode)
- relocated SDK sanitizer runtime ordering in Linux CI. (aa794491ad68 fix(ci): link relocated SDK consumers to sanitizer runtimes)
- slash-rooted transaction paths are refused consistently on Windows and POSIX. (c4d8ee0f4d54 test(transaction): cover state law and reject slash-root paths)
- cross-platform lifecycle builds now initialize the complete isolation contract. (21ae0f68ed30 fix(launch): propagate isolation fields through lifecycle refs)
- the Windows legacy compatibility package again includes the separately built WinForms shell. (b6006e514d03 fix(package): stage WinForms artifact into installed tree)
- Evidence-only compacted queue placeholders no longer block lifecycle indexing. (d365ceaf7cda fix(aide): tolerate compacted queue placeholders)
- Newly archived Windows lifecycle evidence no longer reports false line-ending drift. (91b5985b818f fix(aide): canonicalize immutable history hashes)

## Security

- Raw Steam evidence, account identifiers, absolute local paths, credentials, and proprietary binaries remain outside Git. (6d3c61c009ab docs(evidence): record H1 Fail for Steam-backed candidate)
- Identifier shape validation remains before application dispatch. (514413661f13 fix(contracts): preserve identifier refusal semantics at decode)
- run.execute still cannot start Factorio and now distinguishes the known Steam isolation failure. (a06669155e57 fix(launch): refuse Steam external state in strict mode)
- user-data roots are redirected and raw process output, absolute paths, credentials, and binaries are not persisted. (e74255d5209c feat(compat): add read-only Factorio version capability corpus)
- preserved credentials, download tokens, proprietary binaries, and raw local evidence outside Git. (7502462385d0 docs(checkpoint): freeze R3.8 repair without H1 promotion)
- lifecycle-generated launch references preserve external-state domains and eligibility instead of defaulting them. (21ae0f68ed30 fix(launch): propagate isolation fields through lifecycle refs)
- only an allowlisted external component is staged and its destination remains traversal-validated. (b6006e514d03 fix(package): stage WinForms artifact into installed tree)
- Real content changes remain SHA-256 detected after deterministic text normalization. (91b5985b818f fix(aide): canonicalize immutable history hashes)
- H1 remains Fail; standalone/manual isolation remains unproven; authority promotion remains false. (2671ca55d91d docs(closeout): bind and close the R3.8 repair)

## Docs

- Added the accepted R3.7 public-integration evidence layer. (6619c04c9c1a docs(release): bind R3.7 public integration evidence)
- No evidence meaning or product claim changed. (2190b044ad86 docs(release): wrap R3.7 integration evidence)
- Daemon and frontend capability descriptions now match implemented transport reality. (9539338419c5 fix(truth): establish the R3.7 H1-pending authority plane)
- added the bounded R3.8 isolation-repair and standalone-acquisition handoff. (7502462385d0 docs(checkpoint): freeze R3.8 repair without H1 promotion)
- Bound the exact R3.8 implementation and dev integration evidence. (2671ca55d91d docs(closeout): bind and close the R3.8 repair)

## Tests

- Every registered command is differentially checked against its generated request schema through the live CLI. (49101f7acfba feat(contracts): generate and enforce native request boundary law)
- Added native coverage for a path-escape identifier. (514413661f13 fix(contracts): preserve identifier refusal semantics at decode)
- added parent-cache propagation coverage. (aa794491ad68 fix(ci): link relocated SDK consumers to sanitizer runtimes)
- expanded transaction state-machine and relative-path contract coverage. (c4d8ee0f4d54 test(transaction): cover state law and reject slash-root paths)
- added Steam and standalone classification assertions plus import/inspect persistence checks. (08cf8a58fb17 feat(installs): classify external-state isolation eligibility)
- added end-to-end Steam preview, preflight, refusal, and no-side-effect proof. (a06669155e57 fix(launch): refuse Steam external state in strict mode)
- added parsing, capability, tree-fingerprint, metadata-fallback, and executable-discovery coverage. (e74255d5209c feat(compat): add read-only Factorio version capability corpus)
- reproduced the hosted compiler failure with GCC and reran Windows native plus focused lifecycle suites. (21ae0f68ed30 fix(launch): propagate isolation fields through lifecycle refs)
- added focused external-component staging and path-refusal coverage. (b6006e514d03 fix(package): stage WinForms artifact into installed tree)
- Partial live records remain fail-closed. (d365ceaf7cda fix(aide): tolerate compacted queue placeholders)
- Added data-level assertions for the closed repair and refreshed validation identity. (2671ca55d91d docs(closeout): bind and close the R3.8 repair)

## Internal

- close the R3.7 profiles/templates queue item with exact green evidence. (f40e9d31f940 chore(aide): close profiles and templates workunit)
- No product, contract, schema, runtime, frontend, provider, package, release, or H1-state change. (6619c04c9c1a docs(release): bind R3.7 public integration evidence)

## Risks

- H1 has automated evidence but no reviewed operator verdict; execution remains unavailable. (9539338419c5 fix(truth): establish the R3.7 H1-pending authority plane)
- Domain-specific cross-field policy remains intentionally hand-written after boundary validation. (49101f7acfba feat(contracts): generate and enforce native request boundary law)

## Malformed Commits

- bb3814a49053 land: task/r3.7-instance-content-lifecycle into dev: missing_commit_body; missing_required_headings: ## Summary, ## Why, ## Changed, ## Validation, ## Changelog, ## Risks, ## Follow-up; missing_changelog_category
- d00456069eb5 promote: dev into main: missing_commit_body; missing_required_headings: ## Summary, ## Why, ## Changed, ## Validation, ## Changelog, ## Risks, ## Follow-up; missing_changelog_category
- 19e8fa6e5ef1 land: task/r3.7-public-integration-proof into dev: missing_commit_body; missing_required_headings: ## Summary, ## Why, ## Changed, ## Validation, ## Changelog, ## Risks, ## Follow-up; missing_changelog_category
- 2a991df21fd8 promote: dev into main: missing_commit_body; missing_required_headings: ## Summary, ## Why, ## Changed, ## Validation, ## Changelog, ## Risks, ## Follow-up; missing_changelog_category
- 6581d19e269f land: task/r3.7-public-integration-proof-ci-fix into dev: missing_commit_body; missing_required_headings: ## Summary, ## Why, ## Changed, ## Validation, ## Changelog, ## Risks, ## Follow-up; missing_changelog_category
- eb629caaec9d promote: dev into main: missing_commit_body; missing_required_headings: ## Summary, ## Why, ## Changed, ## Validation, ## Changelog, ## Risks, ## Follow-up; missing_changelog_category
- 9d3ccd663e9d land: task/r3.7-truth-conformance-repair into dev: missing_commit_body; missing_required_headings: ## Summary, ## Why, ## Changed, ## Validation, ## Changelog, ## Risks, ## Follow-up; missing_changelog_category
- f10aef03517a land: R3.8 Steam external-state isolation repair into dev: missing_required_headings: ## Summary, ## Why, ## Changed, ## Validation, ## Changelog, ## Risks, ## Follow-up; missing_changelog_category

## Release Caveat

- Preview only. No tags, GitHub Releases, branch mutation, or publishing were performed.
