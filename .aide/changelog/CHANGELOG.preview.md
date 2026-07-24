# AIDE Changelog Preview

This file is generated from local Git history and is a preview only.

source_range: facman-r2-local-alpha-proof-0..HEAD
source_head: a8c73eb4e34f8fbac5c2cf2207fdf47d64bcb616
commit_count: 50
malformed_count: 2
preview_only: true
release_publishing: false

## Summary

- Added: 8
- Changed: 7
- Fixed: 13
- Security: 26
- Docs: 13
- Tests: 23
- Internal: 13
- Risks: 13
- Follow-up: 15

## Added

- authenticated provider-neutral permit infrastructure. (b0d5f388c312 feat(permit): implement authenticated one-time core)
- exact Gate 2 instance-evidence projection for future menu permits. (7c351e77b0ad feat(permit): prove exact dormant provider binding)
- immutable Gate 4A process-tree-hermetic standalone Play policy and component contracts. (cf674d852e16 feat(policy): freeze hermetic standalone Play law)
- durable Gate 4A canonical public-integration evidence. (690728884f7e docs(gate4a): record canonical policy integration)
- internal exact-candidate planning, issuance, observation, and evidence-packet infrastructure. (4e20ff3a44d5 feat(play): implement the frozen hermetic candidate)
- bounded Gate 4C human-verdict WorkUnit and immutable activation boundary. (e60ff931317a docs(play): close Gate 4B candidate)
- Gate 4C preflight and ETW observer self-test tooling. (71fc4f95e274 feat(gate4c): bind exact verdict preflight blockers)
- evidence-only Gate 4C observer, baseline, operator harness, finalizer, tests, and procedure. (995e6130210d test(gate4c): add exact evidence-only verdict harness)

## Changed

- repository truth now records canonical main promotion and synchronized dev ancestry. (dac01182292b docs(checkpoint): record Gates 0-3 canonical integration)
- development truth now records policy implemented and frozen pending reviewed closeout. (cf674d852e16 feat(policy): freeze hermetic standalone Play law)
- project truth now records accepted dev integration pending canonical policy promotion. (d46aab915432 docs(checkpoint): close Gate 4A policy review)
- product phase from policy closeout to the bounded candidate. (690728884f7e docs(gate4a): record canonical policy integration)
- generated development truth now records 279 schemas while command and refusal counts remain unchanged. (4e20ff3a44d5 feat(play): implement the frozen hermetic candidate)
- Gate 4B development truth is accepted as reviewed, reproduced, and eligible for human verdict. (e60ff931317a docs(play): close Gate 4B candidate)
- project truth now records the reviewed closeout as eligible for human verdict. (4bc2ec135fe2 docs(checkpoint): record Gate 4B public integration)

## Fixed

- make the conditional permit fuzz entry visible to strict changed-source analysis. (5f9f122d6d3e fix(ci): compile permit fuzz entry in normal proof)
- execution-foundation clean reproductions no longer inherit an avoidably deep journal path from the build tree. (678d985ad984 fix(test): keep execution journals below Windows path limits)
- Linux and macOS warnings-as-errors builds no longer compile implementation helpers for the Windows-only frozen candidate. (5335b8777fef fix(play): isolate Windows candidate helpers)
- Linux and macOS warnings-as-errors builds no longer compile Windows-only candidate fixture helpers. (67110899db21 fix(test): isolate Windows candidate fixtures)
- candidate smoke fixtures compile cleanly with GCC range-loop warnings treated as errors. (da3e2274a3dc fix(test): make writable fixture copies explicit)
- source provenance can now represent an exact signed standalone (f03d771ce218 fix(gate4c): bind signed portable source packages)
- Gate 4C observer evidence now refuses mixed WPR/decoder toolchains. (b8d91bceded1 fix(gate4c): bind one observer toolkit)
- Gate 4C observer self-test no longer records three unnecessarily broad WPR profiles. (dfc741e107c3 fix(evidence): bound Gate 4C observer capture capacity)
- Windows CRLF checkout materialization no longer invalidates the reviewed observer profile contract. (0800e2f26bf5 fix(evidence): normalize observer profile identity)
- Gate 4C observation proof now understands actual XPerf CSV fields. (dd8438593980 fix(evidence): parse exact Gate 4C XPerf rows)
- portable native builds no longer compile unreachable Windows-only operator helpers. (89d69de0884a fix(gate4c): isolate Windows-only harness implementation)
- complete separation of the Windows-only interactive implementation from portable harness modes. (9c080e704633 fix(gate4c): complete portable compile boundary)
- AppleClang no longer sees unused Windows session constants. (2684056aaf4d fix(gate4c): guard Windows session constants)

## Security

- add process-bound HMAC, exact closed scopes, monotonic expiry, revocation, and atomic replay refusal. (b0d5f388c312 feat(permit): implement authenticated one-time core)
- keep workflow scope limited to existing sanitizer and fuzz lanes. (e883ab5cf18b chore(aide): authorize hosted permit fuzz proof)
- independently authenticate, reobserve, and consume one foundation permit at the dormant launch-provider boundary. (7c351e77b0ad feat(permit): prove exact dormant provider binding)
- require an explicit cryptographic entropy dependency for process-session permit authentication. (407fa0471ffb fix(permit): require explicit secure entropy)
- retain fail-closed clang-tidy coverage with no allowlist exception. (5f9f122d6d3e fix(ci): compile permit fuzz entry in normal proof)
- Keep permit issuance, Factorio execution, Setup, credentials, networking, signing, publication, and main unpromoted. (ec4159f05678 docs(checkpoint): close Gate 3 permit infrastructure)
- No tree content or authority changes. (ff57488e3cd5 chore(sync): merge canonical Gates 0-3 ancestry into dev)
- explicitly retain false permit issuance, real execution, signing, publication, and authority-promotion claims. (dac01182292b docs(checkpoint): record Gates 0-3 canonical integration)
- exact no-follow resources, independent observation, evidence closure, and Pass/Fail/Inconclusive law cannot grant authority. (cf674d852e16 feat(policy): freeze hermetic standalone Play law)
- freeze the process-tree claim and retain Inconclusive for every observation gap. (d46aab915432 docs(checkpoint): close Gate 4A policy review)
- kept issuance, process execution, real Play, setup, credentials, networking, host mutation, signing, and publication unavailable. (690728884f7e docs(gate4a): record canonical policy integration)
- reject stable-object and process-restart ambiguity at the candidate boundary. (da2a52b6ca39 feat(platform): bind stable candidate object identities)
- bind plan integrity, exact resources, stable objects, process starts, provider audience, one-time nonce, observation completeness, and packet self-hash. (4e20ff3a44d5 feat(play): implement the frozen hermetic candidate)
- retain fail-closed non-Windows candidate unavailability without weakening Windows validation. (5335b8777fef fix(play): isolate Windows candidate helpers)
- preserve frozen policy, exact candidate identities, unset human verdict, and zero product authority. (e60ff931317a docs(play): close Gate 4B candidate)
- preserve unavailable product issuance, public Play, real Factorio execution, Setup, credentials, networking, Steam, host mutation, signing, and publication. (4bc2ec135fe2 docs(checkpoint): record Gate 4B public integration)
- Missing provenance or observation evidence is a closed blocker and cannot grant authority. (71fc4f95e274 feat(gate4c): bind exact verdict preflight blockers)
- Bind source, attestation, and observer evidence to exact, fresh identities and reject per-domain attribution ambiguity. (1aebc65dcdc3 fix(gate4c): harden preflight evidence bindings)
- package/member substitution, unsafe ZIP structure, reparse paths, (f03d771ce218 fix(gate4c): bind signed portable source packages)
- Lost or undecodable ETW events still fail closed; no observation gap is waived. (dfc741e107c3 fix(evidence): bound Gate 4C observer capture capacity)
- The exact materialized raw SHA-256 remains bound; canonicalization is limited to XML line endings. (0800e2f26bf5 fix(evidence): normalize observer profile identity)
- Missing live loss counts and same-row PID mismatches fail closed. (dd8438593980 fix(evidence): parse exact Gate 4C XPerf rows)
- exact closed resource paths, stable identities, append-only outputs, authenticated one-use permit consumption, replay resistance, and fail-closed observation gaps. (995e6130210d test(gate4c): add exact evidence-only verdict harness)
- the non-Windows harness remains refusal-only; no execution boundary changed. (89d69de0884a fix(gate4c): isolate Windows-only harness implementation)
- non-Windows behavior remains refusal-only. (9c080e704633 fix(gate4c): complete portable compile boundary)
- non-Windows behavior remains refusal-only. (2684056aaf4d fix(gate4c): guard Windows session constants)

## Docs

- Add the durable Gate 3 infrastructure-only closeout and exact proof. (ec4159f05678 docs(checkpoint): close Gate 3 permit infrastructure)
- add a durable canonical integration proof for Gates 0-3. (dac01182292b docs(checkpoint): record Gates 0-3 canonical integration)
- define measurable hermetic scope and the human-reviewed menu-first journey. (cf674d852e16 feat(policy): freeze hermetic standalone Play law)
- add the reviewed Gate 4A policy closeout and exact evidence record. (d46aab915432 docs(checkpoint): close Gate 4A policy review)
- record the Gate 4B technical boundary and preserve Gate 4C as a separate human-reviewed run. (4e20ff3a44d5 feat(play): implement the frozen hermetic candidate)
- add complete reviewed-head, merged-dev, reproduction, risk, storage, and checkpoint evidence. (e60ff931317a docs(play): close Gate 4B candidate)
- add durable Gate 4B public-integration proof. (4bc2ec135fe2 docs(checkpoint): record Gate 4B public integration)
- Record exact preflight identities, blockers, and retained scratch disposition. (71fc4f95e274 feat(gate4c): bind exact verdict preflight blockers)
- Record the v2 evidence contracts, bounded leases, and cleanup disposition. (1aebc65dcdc3 fix(gate4c): harden preflight evidence bindings)
- recorded the pre-baseline defect and bounded correction. (f03d771ce218 fix(gate4c): bind signed portable source packages)
- Preserved the exact lossy self-test identities and bounded correction rationale. (dfc741e107c3 fix(evidence): bound Gate 4C observer capture capacity)
- Distinguished raw execution bytes from reviewed canonical profile content. (0800e2f26bf5 fix(evidence): normalize observer profile identity)
- Preserve the exact pre-baseline v3 Inconclusive evidence. (dd8438593980 fix(evidence): parse exact Gate 4C XPerf rows)

## Tests

- add foundation-only adversarial and concurrent native proof. (b0d5f388c312 feat(permit): implement authenticated one-time core)
- add mutation, drift, replay, no-write, parser-corpus, sanitizer, and bounded libFuzzer coverage. (7c351e77b0ad feat(permit): prove exact dormant provider binding)
- prove both successful construction and fail-closed unavailable entropy. (407fa0471ffb fix(permit): require explicit secure entropy)
- fuzz the instrumented permit core rather than only the entry executable. (5f9f122d6d3e fix(ci): compile permit fuzz entry in normal proof)
- Bind compaction and contributor-truth assertions to the policy phase. (ec4159f05678 docs(checkpoint): close Gate 3 permit infrastructure)
- lock exact integration identities and authority exclusions in project-state regression checks. (dac01182292b docs(checkpoint): record Gates 0-3 canonical integration)
- add canonical digest, mutation, broad-root, verdict, exclusion, and truth regression coverage. (cf674d852e16 feat(policy): freeze hermetic standalone Play law)
- bind exact review, merge, reproduction, counts, no-active-task checkpoint, and no-authority state. (d46aab915432 docs(checkpoint): close Gate 4A policy review)
- bound project-state and policy validation to canonical promotion, ancestry, tree identity, and candidate activation. (690728884f7e docs(gate4a): record canonical policy integration)
- add synthetic execution and adversarial proof without running Factorio. (4e20ff3a44d5 feat(play): implement the frozen hermetic candidate)
- retain precise failure diagnostics for process identity, lifecycle progression, and journal persistence. (678d985ad984 fix(test): keep execution journals below Windows path limits)
- preserve platform-specific candidate assertions without weakening cross-platform foundation coverage. (67110899db21 fix(test): isolate Windows candidate fixtures)
- make temporary string construction explicit without changing fixture semantics. (da3e2274a3dc fix(test): make writable fixture copies explicit)
- update generated-truth and target-profile assertions for the verdict phase. (e60ff931317a docs(play): close Gate 4B candidate)
- lock exact closeout revisions, workflow identities, and path-filtered schema disposition. (4bc2ec135fe2 docs(checkpoint): record Gate 4B public integration)
- Cover evidence mutation, path safety, source non-inference, and observer parsing. (71fc4f95e274 feat(gate4c): bind exact verdict preflight blockers)
- Add adversarial mutation coverage for every reviewed evidence boundary. (1aebc65dcdc3 fix(gate4c): harden preflight evidence bindings)
- Make synthetic Windows observer-tool identity fixtures host-independent. (6b3a300aa6d7 test(gate4c): normalize mocked Windows tool paths)
- added signed-package, mismatch, wrong-version, unsafe-path, (f03d771ce218 fix(gate4c): bind signed portable source packages)
- Added exact profile, buffer, keyword, mutation, start-argument, and WPR loss-message coverage. (dfc741e107c3 fix(evidence): bound Gate 4C observer capture capacity)
- Added explicit LF/CRLF identity parity and retained semantic mutation refusal. (0800e2f26bf5 fix(evidence): normalize observer profile identity)
- canonical cross-language digest, external/protected-write, wrong-image, wrong-PID, PID-reuse, source-boundary, and human-verdict-law coverage. (995e6130210d test(gate4c): add exact evidence-only verdict harness)
- cross-platform canonicalization remains enabled. (89d69de0884a fix(gate4c): isolate Windows-only harness implementation)

## Internal

- no public issuer, command, route, or process provider is added. (b0d5f388c312 feat(permit): implement authenticated one-time core)
- authorize hosted execution of bounded permit fuzz proof. (e883ab5cf18b chore(aide): authorize hosted permit fuzz proof)
- retain 125 commands and 123 routes with no public issuer. (7c351e77b0ad feat(permit): prove exact dormant provider binding)
- keep the platform CSPRNG adapter and all issuance plumbing outside Gate 3. (407fa0471ffb fix(permit): require explicit secure entropy)
- Synchronize canonical Gates 0-3 history into dev ancestry. (ff57488e3cd5 chore(sync): merge canonical Gates 0-3 ancestry into dev)
- retain the Gate 4 policy WorkUnit as the active, separate next boundary. (dac01182292b docs(checkpoint): record Gates 0-3 canonical integration)
- keep permit issuance, process execution, Setup, credentials, networking, signing, publication, and host mutation unavailable. (cf674d852e16 feat(policy): freeze hermetic standalone Play law)
- close the policy task and prepare, but do not activate, the exact candidate WorkUnit. (d46aab915432 docs(checkpoint): close Gate 4A policy review)
- normalized the queue transition from planned to active. (690728884f7e docs(gate4a): record canonical policy integration)
- add shared platform evidence primitives without enabling a process route. (da2a52b6ca39 feat(platform): bind stable candidate object identities)
- activate no additional authority and leave the human verdict unset. (4bc2ec135fe2 docs(checkpoint): record Gate 4B public integration)
- Observer proof schema/provider revision advances to v3. (dfc741e107c3 fix(evidence): bound Gate 4C observer capture capacity)
- No policy, provider scope, buffer, keyword, runtime, or authority change. (0800e2f26bf5 fix(evidence): normalize observer profile identity)

## Risks

- Factorio resource projection, dormant launch verification, fuzzing, and full platform proof remain. (b0d5f388c312 feat(permit): implement authenticated one-time core)
- fuzz targets and workflow wiring remain to be implemented. (e883ab5cf18b chore(aide): authorize hosted permit fuzz proof)
- hosted cross-platform and libFuzzer results remain pending until this head is published. (7c351e77b0ad feat(permit): prove exact dormant provider binding)
- no product authenticator can be constructed until a later reviewed issuer wires the OS-backed source. (407fa0471ffb fix(permit): require explicit secure entropy)
- replacement hosted Linux sanitizer/libFuzzer proof is pending. (5f9f122d6d3e fix(ci): compile permit fuzz entry in normal proof)
- the product remains non-playable and no issuer, process route, or human verdict exists. (d46aab915432 docs(checkpoint): close Gate 4A policy review)
- real Factorio execution and the human Play verdict remain unproven. (690728884f7e docs(gate4a): record canonical policy integration)
- real process-tree observation, normal-menu behavior, save persistence, and human judgment remain unproven until Gate 4C. (e60ff931317a docs(play): close Gate 4B candidate)
- The source artifact, elevated zero-loss observer proof, and fresh quiet-host attestation remain unavailable. (71fc4f95e274 feat(gate4c): bind exact verdict preflight blockers)
- the human Gate 4C run remains blocked on quiet-host and observer (f03d771ce218 fix(gate4c): bind signed portable source packages)
- The custom profile still requires a fresh elevated operator self-test after merge; it has not yet produced a zero-loss trace on the target host. (dfc741e107c3 fix(evidence): bound Gate 4C observer capture capacity)
- The corrected v3 observer remains target-host-unproven until a fresh elevated self-test passes. (0800e2f26bf5 fix(evidence): normalize observer profile identity)
- the real interactive Factorio journey remains unexecuted and requires a new fresh blocker-clearing lease after this tooling revision is merged. (995e6130210d test(gate4c): add exact evidence-only verdict harness)

## Follow-up

- bind Gate 2 instance evidence and add dormant launch-provider validation. (b0d5f388c312 feat(permit): implement authenticated one-time core)
- add parser harnesses and run the bounded corpus. (e883ab5cf18b chore(aide): authorize hosted permit fuzz proof)
- require explicit secure entropy for process-session authenticators, then publish for hosted review. (7c351e77b0ad feat(permit): prove exact dormant provider binding)
- publish the exact Gate 3 head for hosted cross-platform, sanitizer, and libFuzzer proof. (407fa0471ffb fix(permit): require explicit secure entropy)
- push the repair and require every replacement PR check to pass. (5f9f122d6d3e fix(ci): compile permit fuzz entry in normal proof)
- Freeze the standalone menu-Play policy before implementing or running a candidate. (ec4159f05678 docs(checkpoint): close Gate 3 permit infrastructure)
- implement only the exact frozen Gate 4B candidate, then open the separate human-verdict WorkUnit. (690728884f7e docs(gate4a): record canonical policy integration)
- Supply authenticated source evidence, run the elevated observer self-test, attest the quiet interval, and regenerate preflight. (71fc4f95e274 feat(gate4c): bind exact verdict preflight blockers)
- merge only after exact-head hosted CI, CodeQL, and policy checks, (f03d771ce218 fix(gate4c): bind signed portable source packages)
- Merge the reviewed evidence-only correction, synchronize dev/evidence ancestry, then rerun the elevated self-test before attestation or baseline. (dfc741e107c3 fix(evidence): bound Gate 4C observer capture capacity)
- Rerun all exact-head hosted checks and merge only when the Windows lane is green. (0800e2f26bf5 fix(evidence): normalize observer profile identity)
- merge this tooling checkpoint, rebuild and bind the exact merge, then conduct the two-launch human verdict session. (995e6130210d test(gate4c): add exact evidence-only verdict harness)
- require the refreshed PR matrix to pass before review or merge. (89d69de0884a fix(gate4c): isolate Windows-only harness implementation)
- accept no merge until refreshed Linux and full hosted matrices pass. (9c080e704633 fix(gate4c): complete portable compile boundary)
- require a completely green refreshed PR head before merge. (2684056aaf4d fix(gate4c): guard Windows session constants)

## Malformed Commits

- 7fe12635f730 Gate 4B: close candidate as eligible for human verdict (#53): subject_not_conventional; missing_required_headings: ## Summary, ## Why, ## Changed, ## Validation, ## Changelog, ## Risks, ## Follow-up; missing_changelog_category
- 6f883cd00e7a Gate 4B: record final public integration evidence (#54): subject_not_conventional; missing_required_headings: ## Summary, ## Why, ## Changed, ## Validation, ## Changelog, ## Risks, ## Follow-up; missing_changelog_category

## Release Caveat

- Preview only. No tags, GitHub Releases, branch mutation, or publishing were performed.
