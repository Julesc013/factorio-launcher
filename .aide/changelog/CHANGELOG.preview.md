# AIDE Changelog Preview

This file is generated from local Git history and is a preview only.

source_range: 29cf22fa..HEAD
source_head: 81abee2fb1220d5f8620086f354621f7d58a2281
commit_count: 31
malformed_count: 0
preview_only: true
release_publishing: false

## Summary

- Added: 12
- Changed: 7
- Fixed: 9
- Security: 4
- Docs: 1
- Tests: 2
- Internal: 5

## Added

- shared cross-frontend workspace resolution with legacy preservation and structured refusal. (e5da5d2584b2 feat(workspace): centralize safe default resolution)
- non-secret user preferences with reviewable plan/apply/reset commands and shared preferred-workspace resolution. (ec77cc1f1000 feat(preferences): add non-secret transactional product settings)
- reversible instance inspection, verification, diff, clone, display rename, owned-trash archive, and verified restore. (e3b010895909 feat(instances): add reversible transactional lifecycle)
- portable instance snapshot management and reversible retention. (9f4b3d351dfb feat(snapshots): add portable instance lifecycle)
- declarative instance templates and portable launch-profile lifecycle management. (fc1cbf359418 feat(profiles): add declarative customization lifecycle)
- stable, local-only mod inventory and verification commands for R3.7. (8335fde1ba12 feat(mods): add stable local inventory)
- deterministic bounded local dependency plans and transactional modset apply and rollback. (b93d7376c625 feat(modsets): add bounded local solver)
- bounded save indexing, sidecar association, drift detection, structural diff, and reversible retention. (2e9a66f8a4bd feat(saves): add structural index and retention)
- secret-free dedicated-server planning and portable export bundles. (578bfb57bf82 feat(servers): add non-executing plan bundles)
- generated guided operational forms and cross-frontend result visualizations. (dedadfa2f95e feat(frontends): generate guided operational forms)
- Cross-transport lifecycle, adversarial, and release-scale R3.7 proof coverage. (625a964355d0 test(lifecycle): prove R3.7 cross-transport journey)
- Required Linux Release build and CTest evidence to the cross-platform closeout matrix. (81abee2fb122 ci(linux): add explicit Release proof)

## Changed

- R3.7 now has target-local resumable governance and unambiguous baseline evidence. (d07aec528068 chore(aide): establish the R3.7 authority and evidence graph)
- R3.7 wave state now records local mod inventory as closed and verified. (05a93277d739 chore(aide): close local mod inventory workunit)
- R3.7 wave state now records the local modset solver as closed and verified. (7ad66aea23d7 chore(aide): close local modset solver workunit)
- R3.7 wave state now records structural save intelligence as closed and verified. (b30e4a70272e chore(aide): close save intelligence workunit)
- R3.7 wave state now records server planning as closed. (d90d461a99dd chore(aide): close server planning workunit)
- R3.7 wave state now records operational UX as closed. (9af53a736f47 chore(aide): close operational UX workunit)
- R3.7 wave state now records WU10 as closed with advisory-only evidence. (b6e8e6200b9e chore(aide): close R3.7 lifecycle proof)

## Fixed

- clean workspace proof now packages only artifacts produced by its own TUI-enabled build. (47bc5eff9a22 test(repro): bind package proof to the clean TUI build)
- affected-test module execution now exposes repository and tests helper import roots. (ec77cc1f1000 feat(preferences): add non-secret transactional product settings)
- affected native script tests now build real prerequisites and Python tests honor the requested Debug or Release artifact. (e3b010895909 feat(instances): add reversible transactional lifecycle)
- Cross-workunit lifecycle correctness and generated-client compatibility defects found by R3.7 end-to-end proof. (9fea4325129c fix(lifecycle): close cross-workunit integrity gaps)
- Native transaction smoke no longer leaves an empty source-tree directory after passing. (8556b05e033a test(transaction): clean native smoke workspace)
- Linux and macOS warnings-as-errors portability failures in preferences and modset planning. (4d542308f806 fix(portability): satisfy GCC and AppleClang warnings)
- Linux and macOS launch-reference compilation no longer depends on omitted aggregate fields. (02398db38063 fix(portability): initialize launch profile defaults)
- Cross-platform TUI smoke compilation now matches the complete generated-client invocation shape. (681a614ea193 test(tui): initialize complete invocation shape)
- Profile archive now uses a directory-safe atomic no-clobber move on POSIX. (774628f442b0 fix(profiles): archive directories atomically on POSIX)

## Security

- secret-like fields, unsafe paths, linked targets, future schemas, unavailable transports, and incomplete journal transitions fail closed. (ec77cc1f1000 feat(preferences): add non-secret transactional product settings)
- link/reparse crossings, multiply linked files, active run locks, uncertain transactions, hash drift, clobber targets, and malformed archives fail closed. (e3b010895909 feat(instances): add reversible transactional lifecycle)
- exclude secrets and local paths and verify archive closure before restore. (9f4b3d351dfb feat(snapshots): add portable instance lifecycle)
- reserved Factorio arguments and all execution authority remain controlled outside customization documents. (fc1cbf359418 feat(profiles): add declarative customization lifecycle)

## Docs

- define immutable IDs, volatile exclusions, archive metadata, recovery states, and the explicit absence of purge. (e3b010895909 feat(instances): add reversible transactional lifecycle)

## Tests

- native transaction smoke, CLI read-only/secret rejection tests, contract goldens, schemas, frontend parity, full Release package proof. (ec77cc1f1000 feat(preferences): add non-secret transactional product settings)
- live schema validation, complete happy path, alternate-ID restore, run-lock refusal, and clone/archive/restore fault matrices. (e3b010895909 feat(instances): add reversible transactional lifecycle)

## Internal

- R3.7 baseline governance is closed and WorkUnit 1 is unblocked. (a171ba92ad49 chore(aide): close the verified R3.7 baseline gate)
- close WU1 evidence without promoting execution, setup, network, publication, or human-acceptance claims. (a2cb04b258bd chore(aide): close the verified R3.7 preferences gate)
- close WU2 at its clean last-green revision and retain fail-closed authority boundaries. (6af71551826f chore(aide): close the verified R3.7 lifecycle gate)
- close the R3.7 snapshot lifecycle queue item with exact green evidence. (62133fae53a1 chore(aide): close snapshot lifecycle workunit)
- close the R3.7 profiles/templates queue item with exact green evidence. (f40e9d31f940 chore(aide): close profiles and templates workunit)

## Malformed Commits

- None.

## Release Caveat

- Preview only. No tags, GitHub Releases, branch mutation, or publishing were performed.
