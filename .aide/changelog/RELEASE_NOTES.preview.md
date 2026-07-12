# AIDE Release Notes Preview

This is a deterministic preview only. It does not publish a release.

source_range: 29cf22fa..HEAD
source_head: 81abee2fb1220d5f8620086f354621f7d58a2281
preview_only: true

## Highlights

- Security: secret-like fields, unsafe paths, linked targets, future schemas, unavailable transports, and incomplete journal transitions fail closed. (ec77cc1f1000)
- Security: link/reparse crossings, multiply linked files, active run locks, uncertain transactions, hash drift, clobber targets, and malformed archives fail closed. (e3b010895909)
- Security: exclude secrets and local paths and verify archive closure before restore. (9f4b3d351dfb)
- Security: reserved Factorio arguments and all execution authority remain controlled outside customization documents. (fc1cbf359418)
- Added: shared cross-frontend workspace resolution with legacy preservation and structured refusal. (e5da5d2584b2)
- Added: non-secret user preferences with reviewable plan/apply/reset commands and shared preferred-workspace resolution. (ec77cc1f1000)
- Added: reversible instance inspection, verification, diff, clone, display rename, owned-trash archive, and verified restore. (e3b010895909)
- Added: portable instance snapshot management and reversible retention. (9f4b3d351dfb)
- Added: declarative instance templates and portable launch-profile lifecycle management. (fc1cbf359418)
- Added: stable, local-only mod inventory and verification commands for R3.7. (8335fde1ba12)
- Added: deterministic bounded local dependency plans and transactional modset apply and rollback. (b93d7376c625)
- Added: bounded save indexing, sidecar association, drift detection, structural diff, and reversible retention. (2e9a66f8a4bd)
- Added: secret-free dedicated-server planning and portable export bundles. (578bfb57bf82)
- Added: generated guided operational forms and cross-frontend result visualizations. (dedadfa2f95e)
- Added: Cross-transport lifecycle, adversarial, and release-scale R3.7 proof coverage. (625a964355d0)
- Added: Required Linux Release build and CTest evidence to the cross-platform closeout matrix. (81abee2fb122)
- Changed: R3.7 now has target-local resumable governance and unambiguous baseline evidence. (d07aec528068)
- Changed: R3.7 wave state now records local mod inventory as closed and verified. (05a93277d739)
- Changed: R3.7 wave state now records the local modset solver as closed and verified. (7ad66aea23d7)
- Changed: R3.7 wave state now records structural save intelligence as closed and verified. (b30e4a70272e)
- Changed: R3.7 wave state now records server planning as closed. (d90d461a99dd)
- Changed: R3.7 wave state now records operational UX as closed. (9af53a736f47)
- Changed: R3.7 wave state now records WU10 as closed with advisory-only evidence. (b6e8e6200b9e)
- Fixed: clean workspace proof now packages only artifacts produced by its own TUI-enabled build. (47bc5eff9a22)
- Fixed: affected-test module execution now exposes repository and tests helper import roots. (ec77cc1f1000)
- Fixed: affected native script tests now build real prerequisites and Python tests honor the requested Debug or Release artifact. (e3b010895909)
- Fixed: Cross-workunit lifecycle correctness and generated-client compatibility defects found by R3.7 end-to-end proof. (9fea4325129c)
- Fixed: Native transaction smoke no longer leaves an empty source-tree directory after passing. (8556b05e033a)
- Fixed: Linux and macOS warnings-as-errors portability failures in preferences and modset planning. (4d542308f806)
- Fixed: Linux and macOS launch-reference compilation no longer depends on omitted aggregate fields. (02398db38063)
- Fixed: Cross-platform TUI smoke compilation now matches the complete generated-client invocation shape. (681a614ea193)
- Fixed: Profile archive now uses a directory-safe atomic no-clobber move on POSIX. (774628f442b0)
- Docs: define immutable IDs, volatile exclusions, archive metadata, recovery states, and the explicit absence of purge. (e3b010895909)
- Tests: native transaction smoke, CLI read-only/secret rejection tests, contract goldens, schemas, frontend parity, full Release package proof. (ec77cc1f1000)
- Tests: live schema validation, complete happy path, alternate-ID restore, run-lock refusal, and clone/archive/restore fault matrices. (e3b010895909)

## Validation Summary

- 47bc5eff9a22: Focused repro tests, source-format check, and the complete three-repository build matrix: PASS.
- d07aec528068: Focused AIDE truth tests, strict policy, AIDE Lite self-test, project-state generation, source formatting, and diff checks: PASS.
- a171ba92ad49: AIDE wave verification and close checks: PASS.
- e5da5d2584b2: Native resolver, client, and TUI CTests: PASS (3/3).
- ec77cc1f1000: `py -3 tools/dev.py test --affected --base e5da5d2 --build-root build/native-smoke --configuration Debug`: PASS (21 native, 89 selected Python, all selected validators).
- ec77cc1f1000: `py -3 tools/dev.py test --affected --base e5da5d2 --build-root build/native-smoke --configuration Debug`: PASS (21 native, 89 selected Python, all selected validators).
- ec77cc1f1000: `py -3 tools/dev.py test --affected --base e5da5d2 --build-root build/native-smoke --configuration Debug`: PASS (21 native, 89 selected Python, all selected validators).
- ec77cc1f1000: `py -3 tools/dev.py test --affected --base e5da5d2 --build-root build/native-smoke --configuration Debug`: PASS (21 native, 89 selected Python, all selected validators).
- a2cb04b258bd: `py -3 tools/repro_workspace_smoke.py --require-clean --build`: PASS across Universal Launcher, Universal Setup, and FacMan.
- e3b010895909: `py -3 tools/dev.py test --affected --base a2cb04b --build-root build/native-smoke --configuration Release`: PASS (7 native, 74 Python, all selected validators).

## Known Risks

- 47bc5eff9a22: The stronger matrix builds one additional frontend target; no product behavior, authority, or test requirement changes.
- d07aec528068: This commit changes development truth only; it does not enable execution, setup mutation, networking, credentials, signing, or publication.
- a171ba92ad49: Metadata only; H1 and all execution, network, setup, credential, signing, and publication quarantines remain unchanged.
- e5da5d2584b2: Users without an explicit workspace and without safe platform user paths now receive a refusal instead of a relative current-directory workspace; this is the intended safety correction.
- ec77cc1f1000: AppKit catalog generation is contract-checked on Windows but native AppKit compilation remains a macOS CI responsibility.
- ec77cc1f1000: AppKit catalog generation is contract-checked on Windows but native AppKit compilation remains a macOS CI responsibility.
- ec77cc1f1000: AppKit catalog generation is contract-checked on Windows but native AppKit compilation remains a macOS CI responsibility.
- ec77cc1f1000: AppKit catalog generation is contract-checked on Windows but native AppKit compilation remains a macOS CI responsibility.
- a2cb04b258bd: None; this commit records verified task state only.
- e3b010895909: Snapshot references in instances.diff remain explicitly unavailable until WU3 creates the portable snapshot contract.

## Follow-up

- 47bc5eff9a22: Commit this repair and rerun the authoritative matrix with `--require-clean`.
- d07aec528068: Verify and close WorkUnit 0, then implement the shared workspace resolver and non-secret preferences layer.
- a171ba92ad49: Start FACMAN-WORKSPACE-PREFERENCES-AND-POLICY-01 and implement shared path resolution first.
- e5da5d2584b2: Add schema-versioned non-secret preferences and allow the resolver to consume a reviewed preferred workspace after explicit environment precedence.
- ec77cc1f1000: Prove the exact commit in the clean three-repository workspace, close WU1 evidence, then begin transactional instance lifecycle operations.
- ec77cc1f1000: Prove the exact commit in the clean three-repository workspace, close WU1 evidence, then begin transactional instance lifecycle operations.
- ec77cc1f1000: Prove the exact commit in the clean three-repository workspace, close WU1 evidence, then begin transactional instance lifecycle operations.
- ec77cc1f1000: Prove the exact commit in the clean three-repository workspace, close WU1 evidence, then begin transactional instance lifecycle operations.
- a2cb04b258bd: Start FACMAN-INSTANCE-LIFECYCLE-02 and keep destructive behavior backup-first and transaction-journaled.
- e3b010895909: Prove this exact revision in the clean three-repository workspace, close WU2 evidence, and begin portable deterministic snapshots and retention policy.

## Warnings

- None.

## Preview Caveat

- This draft is not an official release note and does not create tags or GitHub Releases.
