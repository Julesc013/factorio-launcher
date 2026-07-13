# AIDE Release Notes Preview

This is a deterministic preview only. It does not publish a release.

source_range: 29cf22fa..HEAD
source_head: 2671ca55d91d87e32f48b28890768339820b2d5d
preview_only: true

## Highlights

- Security: Raw Steam evidence, account identifiers, absolute local paths, credentials, and proprietary binaries remain outside Git. (6d3c61c009ab)
- Security: Identifier shape validation remains before application dispatch. (514413661f13)
- Security: run.execute still cannot start Factorio and now distinguishes the known Steam isolation failure. (a06669155e57)
- Security: user-data roots are redirected and raw process output, absolute paths, credentials, and binaries are not persisted. (e74255d5209c)
- Security: preserved credentials, download tokens, proprietary binaries, and raw local evidence outside Git. (7502462385d0)
- Security: lifecycle-generated launch references preserve external-state domains and eligibility instead of defaulting them. (21ae0f68ed30)
- Security: only an allowlisted external component is staged and its destination remains traversal-validated. (b6006e514d03)
- Security: Real content changes remain SHA-256 detected after deterministic text normalization. (91b5985b818f)
- Security: H1 remains Fail; standalone/manual isolation remains unproven; authority promotion remains false. (2671ca55d91d)
- Added: stable, local-only mod inventory and verification commands for R3.7. (8335fde1ba12)
- Added: deterministic bounded local dependency plans and transactional modset apply and rollback. (b93d7376c625)
- Added: bounded save indexing, sidecar association, drift detection, structural diff, and reversible retention. (2e9a66f8a4bd)
- Added: secret-free dedicated-server planning and portable export bundles. (578bfb57bf82)
- Added: generated guided operational forms and cross-frontend result visualizations. (dedadfa2f95e)
- Added: Cross-transport lifecycle, adversarial, and release-scale R3.7 proof coverage. (625a964355d0)
- Added: Required Linux Release build and CTest evidence to the cross-platform closeout matrix. (81abee2fb122)
- Added: Exact R3.7 lifecycle checkpoint with target-native evidence and honest authority boundaries. (6cce8ed15a8f)
- Added: Generated R3.7 review and branch-workflow evidence. (1f840e533774)
- Added: Canonical machine-readable R3.7 and H1-pending project status. (9539338419c5)
- Added: Declarative request-field contracts and generated native boundary validators. (49101f7acfba)
- Added: experimental relocatable FLB 1.2 installed SDK and compatibility metadata. (2f4f7b5460b2)
- Added: Sanitized, digest-bound H1 operator verdict and checkpoint. (6d3c61c009ab)
- Added: explicit install-origin and external-state isolation metadata. (08cf8a58fb17)
- Added: Steam external-state refusal and explicit preview/preflight write-domain policy. (a06669155e57)
- Added: sanitized Factorio version capability corpus tooling and contract. (e74255d5209c)
- Changed: R3.7 wave state now records local mod inventory as closed and verified. (05a93277d739)
- Changed: R3.7 wave state now records the local modset solver as closed and verified. (7ad66aea23d7)
- Changed: R3.7 wave state now records structural save intelligence as closed and verified. (b30e4a70272e)
- Changed: R3.7 wave state now records server planning as closed. (d90d461a99dd)
- Changed: R3.7 wave state now records operational UX as closed. (9af53a736f47)
- Changed: R3.7 wave state now records WU10 as closed with advisory-only evidence. (b6e8e6200b9e)
- Changed: R3.7 AIDE state is closed with advisory-only evidence and no automatic human or release promotion. (dcd9a6cbb0d2)
- Changed: Current status and platform claims are generated and evidence-qualified. (9539338419c5)
- Changed: Command schemas and frontend catalogs derive field constraints from the same source. (49101f7acfba)
- Changed: client transports are independently linkable and daemon IPC remains explicitly unavailable. (6dce5c194457)
- Changed: Canonical status now reports the Steam-backed H1 Fail and active narrow repair. (6d3c61c009ab)
- Changed: Steam, standalone, archive, manual, and package installs now receive conservative isolation classifications. (08cf8a58fb17)
- Changed: Steam preflight is refused even when instance-local config routing is structurally valid. (a06669155e57)
- Changed: Canonical project truth now records no active WorkUnit and the closed repair identity. (2671ca55d91d)
- Fixed: Cross-workunit lifecycle correctness and generated-client compatibility defects found by R3.7 end-to-end proof. (9fea4325129c)
- Fixed: Native transaction smoke no longer leaves an empty source-tree directory after passing. (8556b05e033a)
- Fixed: Linux and macOS warnings-as-errors portability failures in preferences and modset planning. (4d542308f806)
- Fixed: Linux and macOS launch-reference compilation no longer depends on omitted aggregate fields. (02398db38063)
- Fixed: Cross-platform TUI smoke compilation now matches the complete generated-client invocation shape. (681a614ea193)
- Fixed: Profile archive now uses a directory-safe atomic no-clobber move on POSIX. (774628f442b0)
- Fixed: Made the R3.7 public-integration addendum satisfy Linux source-format policy. (2190b044ad86)
- Fixed: Coverage is aggregated by module and release structure is no longer called readiness. (9539338419c5)
- Fixed: `modsets.rollback` now enforces its required lowercase SHA-256 transaction identity at the native boundary. (49101f7acfba)
- Fixed: Cross-platform safety refusals retain invalid_identifier instead of degrading to invalid_request. (514413661f13)
- Fixed: relocated SDK sanitizer runtime ordering in Linux CI. (aa794491ad68)
- Fixed: slash-rooted transaction paths are refused consistently on Windows and POSIX. (c4d8ee0f4d54)
- Fixed: cross-platform lifecycle builds now initialize the complete isolation contract. (21ae0f68ed30)
- Fixed: the Windows legacy compatibility package again includes the separately built WinForms shell. (b6006e514d03)
- Fixed: Evidence-only compacted queue placeholders no longer block lifecycle indexing. (d365ceaf7cda)
- Fixed: Newly archived Windows lifecycle evidence no longer reports false line-ending drift. (91b5985b818f)
- Docs: Added the accepted R3.7 public-integration evidence layer. (6619c04c9c1a)
- Docs: No evidence meaning or product claim changed. (2190b044ad86)
- Docs: Daemon and frontend capability descriptions now match implemented transport reality. (9539338419c5)
- Docs: added the bounded R3.8 isolation-repair and standalone-acquisition handoff. (7502462385d0)
- Docs: Bound the exact R3.8 implementation and dev integration evidence. (2671ca55d91d)
- Tests: Every registered command is differentially checked against its generated request schema through the live CLI. (49101f7acfba)
- Tests: Added native coverage for a path-escape identifier. (514413661f13)
- Tests: added parent-cache propagation coverage. (aa794491ad68)
- Tests: expanded transaction state-machine and relative-path contract coverage. (c4d8ee0f4d54)
- Tests: added Steam and standalone classification assertions plus import/inspect persistence checks. (08cf8a58fb17)
- Tests: added end-to-end Steam preview, preflight, refusal, and no-side-effect proof. (a06669155e57)
- Tests: added parsing, capability, tree-fingerprint, metadata-fallback, and executable-discovery coverage. (e74255d5209c)
- Tests: reproduced the hosted compiler failure with GCC and reran Windows native plus focused lifecycle suites. (21ae0f68ed30)
- Tests: added focused external-component staging and path-refusal coverage. (b6006e514d03)
- Tests: Partial live records remain fail-closed. (d365ceaf7cda)
- Tests: Added data-level assertions for the closed repair and refreshed validation identity. (2671ca55d91d)

## Validation Summary

- f40e9d31f940: `py -3 .aide/scripts/aide_lite.py test`: PASS.
- 8335fde1ba12: PASS: py -3 tools/dev.py test --full --build-root build --configuration Release.
- 05a93277d739: PASS: AIDE Lite wave verify.
- b93d7376c625: PASS: py -3 tools/dev.py test --full --build-root build --configuration Release.
- 7ad66aea23d7: PASS: AIDE Lite wave verify.
- 2e9a66f8a4bd: PASS: py -3 tools/dev.py test --full --build-root build --configuration Release.
- b30e4a70272e: PASS: AIDE Lite wave verify.
- 578bfb57bf82: PASS: py -3 tools/dev.py test --full --build-root build --configuration Release
- d90d461a99dd: PASS: py -3 .aide/scripts/aide_lite.py wave verify for nine WU8 gates.
- dedadfa2f95e: PASS: py -3 tools/dev.py test --full --build-root build --configuration Release.

## Known Risks

- f40e9d31f940: Process execution and human acceptance remain separate, unpromoted authorities.
- 8335fde1ba12: Archive metadata parsing remains intentionally bounded and does not claim portal availability or installation readiness.
- 05a93277d739: This records machine-verifiable evidence only and does not grant portal, publication, or human acceptance claims.
- b93d7376c625: Optional dependencies are not silently installed; they constrain the plan only when already requested or selected.
- 7ad66aea23d7: This ledger records machine evidence only and does not grant real Factorio, setup, network, signing, publication, or human-acceptance authority.
- 2e9a66f8a4bd: Deep Factorio save metadata remains explicitly unsupported.
- b30e4a70272e: This ledger records machine evidence only and does not claim deep save semantics, real Factorio execution, publication, or human acceptance.
- 578bfb57bf82: LOW: execution remains unavailable and exports exclude saves unless explicitly requested.
- d90d461a99dd: LOW: this commit changes report-only AIDE state and no product behavior.
- dedadfa2f95e: LOW: frontend controls submit the same generated request fields and backend validation remains authoritative.

## Follow-up

- f40e9d31f940: Start FACMAN-LOCAL-MOD-INVENTORY-02 from the closed customization baseline.
- 8335fde1ba12: Use these stable inventory identities as the evidence input for the deterministic modset solver workunit.
- 05a93277d739: Start FACMAN-LOCAL-MODSET-SOLVER-01 using the committed inventory identities as local evidence.
- b93d7376c625: Reproduce this exact commit from a clean three-repository workspace and close FACMAN-LOCAL-MODSET-SOLVER-01.
- 7ad66aea23d7: Start FACMAN-SAVE-INDEX-AND-RETENTION-02.
- 2e9a66f8a4bd: Reproduce this exact commit from a clean three-repository workspace and close FACMAN-SAVE-INDEX-AND-RETENTION-02.
- b30e4a70272e: Start FACMAN-SERVER-PLAN-02.
- 578bfb57bf82: Implement grammar-generated operational UX in the next R3.7 work unit.
- d90d461a99dd: Start FACMAN-OPERATIONAL-UX-03 from the generated command grammar.
- dedadfa2f95e: Prove the full reversible lifecycle across direct, stdio, CLI, TUI, desktop, and package transports in WU10.

## Warnings

- 8 malformed or legacy commits require review

## Preview Caveat

- This draft is not an official release note and does not create tags or GitHub Releases.
