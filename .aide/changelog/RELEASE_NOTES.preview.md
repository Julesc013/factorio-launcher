# AIDE Release Notes Preview

This is a deterministic preview only. It does not publish a release.

source_range: facman-r2-local-alpha-proof-0..HEAD
source_head: a8c73eb4e34f8fbac5c2cf2207fdf47d64bcb616
preview_only: true

## Highlights

- Security: add process-bound HMAC, exact closed scopes, monotonic expiry, revocation, and atomic replay refusal. (b0d5f388c312)
- Security: keep workflow scope limited to existing sanitizer and fuzz lanes. (e883ab5cf18b)
- Security: independently authenticate, reobserve, and consume one foundation permit at the dormant launch-provider boundary. (7c351e77b0ad)
- Security: require an explicit cryptographic entropy dependency for process-session permit authentication. (407fa0471ffb)
- Security: retain fail-closed clang-tidy coverage with no allowlist exception. (5f9f122d6d3e)
- Security: Keep permit issuance, Factorio execution, Setup, credentials, networking, signing, publication, and main unpromoted. (ec4159f05678)
- Security: No tree content or authority changes. (ff57488e3cd5)
- Security: explicitly retain false permit issuance, real execution, signing, publication, and authority-promotion claims. (dac01182292b)
- Security: exact no-follow resources, independent observation, evidence closure, and Pass/Fail/Inconclusive law cannot grant authority. (cf674d852e16)
- Security: freeze the process-tree claim and retain Inconclusive for every observation gap. (d46aab915432)
- Security: kept issuance, process execution, real Play, setup, credentials, networking, host mutation, signing, and publication unavailable. (690728884f7e)
- Security: reject stable-object and process-restart ambiguity at the candidate boundary. (da2a52b6ca39)
- Security: bind plan integrity, exact resources, stable objects, process starts, provider audience, one-time nonce, observation completeness, and packet self-hash. (4e20ff3a44d5)
- Security: retain fail-closed non-Windows candidate unavailability without weakening Windows validation. (5335b8777fef)
- Security: preserve frozen policy, exact candidate identities, unset human verdict, and zero product authority. (e60ff931317a)
- Security: preserve unavailable product issuance, public Play, real Factorio execution, Setup, credentials, networking, Steam, host mutation, signing, and publication. (4bc2ec135fe2)
- Security: Missing provenance or observation evidence is a closed blocker and cannot grant authority. (71fc4f95e274)
- Security: Bind source, attestation, and observer evidence to exact, fresh identities and reject per-domain attribution ambiguity. (1aebc65dcdc3)
- Security: package/member substitution, unsafe ZIP structure, reparse paths, (f03d771ce218)
- Security: Lost or undecodable ETW events still fail closed; no observation gap is waived. (dfc741e107c3)
- Security: The exact materialized raw SHA-256 remains bound; canonicalization is limited to XML line endings. (0800e2f26bf5)
- Security: Missing live loss counts and same-row PID mismatches fail closed. (dd8438593980)
- Security: exact closed resource paths, stable identities, append-only outputs, authenticated one-use permit consumption, replay resistance, and fail-closed observation gaps. (995e6130210d)
- Security: the non-Windows harness remains refusal-only; no execution boundary changed. (89d69de0884a)
- Security: non-Windows behavior remains refusal-only. (9c080e704633)
- Security: non-Windows behavior remains refusal-only. (2684056aaf4d)
- Added: authenticated provider-neutral permit infrastructure. (b0d5f388c312)
- Added: exact Gate 2 instance-evidence projection for future menu permits. (7c351e77b0ad)
- Added: immutable Gate 4A process-tree-hermetic standalone Play policy and component contracts. (cf674d852e16)
- Added: durable Gate 4A canonical public-integration evidence. (690728884f7e)
- Added: internal exact-candidate planning, issuance, observation, and evidence-packet infrastructure. (4e20ff3a44d5)
- Added: bounded Gate 4C human-verdict WorkUnit and immutable activation boundary. (e60ff931317a)
- Added: Gate 4C preflight and ETW observer self-test tooling. (71fc4f95e274)
- Added: evidence-only Gate 4C observer, baseline, operator harness, finalizer, tests, and procedure. (995e6130210d)
- Changed: repository truth now records canonical main promotion and synchronized dev ancestry. (dac01182292b)
- Changed: development truth now records policy implemented and frozen pending reviewed closeout. (cf674d852e16)
- Changed: project truth now records accepted dev integration pending canonical policy promotion. (d46aab915432)
- Changed: product phase from policy closeout to the bounded candidate. (690728884f7e)
- Changed: generated development truth now records 279 schemas while command and refusal counts remain unchanged. (4e20ff3a44d5)
- Changed: Gate 4B development truth is accepted as reviewed, reproduced, and eligible for human verdict. (e60ff931317a)
- Changed: project truth now records the reviewed closeout as eligible for human verdict. (4bc2ec135fe2)
- Fixed: make the conditional permit fuzz entry visible to strict changed-source analysis. (5f9f122d6d3e)
- Fixed: execution-foundation clean reproductions no longer inherit an avoidably deep journal path from the build tree. (678d985ad984)
- Fixed: Linux and macOS warnings-as-errors builds no longer compile implementation helpers for the Windows-only frozen candidate. (5335b8777fef)
- Fixed: Linux and macOS warnings-as-errors builds no longer compile Windows-only candidate fixture helpers. (67110899db21)
- Fixed: candidate smoke fixtures compile cleanly with GCC range-loop warnings treated as errors. (da3e2274a3dc)
- Fixed: source provenance can now represent an exact signed standalone (f03d771ce218)
- Fixed: Gate 4C observer evidence now refuses mixed WPR/decoder toolchains. (b8d91bceded1)
- Fixed: Gate 4C observer self-test no longer records three unnecessarily broad WPR profiles. (dfc741e107c3)
- Fixed: Windows CRLF checkout materialization no longer invalidates the reviewed observer profile contract. (0800e2f26bf5)
- Fixed: Gate 4C observation proof now understands actual XPerf CSV fields. (dd8438593980)
- Fixed: portable native builds no longer compile unreachable Windows-only operator helpers. (89d69de0884a)
- Fixed: complete separation of the Windows-only interactive implementation from portable harness modes. (9c080e704633)
- Fixed: AppleClang no longer sees unused Windows session constants. (2684056aaf4d)
- Docs: Add the durable Gate 3 infrastructure-only closeout and exact proof. (ec4159f05678)
- Docs: add a durable canonical integration proof for Gates 0-3. (dac01182292b)
- Docs: define measurable hermetic scope and the human-reviewed menu-first journey. (cf674d852e16)
- Docs: add the reviewed Gate 4A policy closeout and exact evidence record. (d46aab915432)
- Docs: record the Gate 4B technical boundary and preserve Gate 4C as a separate human-reviewed run. (4e20ff3a44d5)
- Docs: add complete reviewed-head, merged-dev, reproduction, risk, storage, and checkpoint evidence. (e60ff931317a)
- Docs: add durable Gate 4B public-integration proof. (4bc2ec135fe2)
- Docs: Record exact preflight identities, blockers, and retained scratch disposition. (71fc4f95e274)
- Docs: Record the v2 evidence contracts, bounded leases, and cleanup disposition. (1aebc65dcdc3)
- Docs: recorded the pre-baseline defect and bounded correction. (f03d771ce218)
- Docs: Preserved the exact lossy self-test identities and bounded correction rationale. (dfc741e107c3)
- Docs: Distinguished raw execution bytes from reviewed canonical profile content. (0800e2f26bf5)
- Docs: Preserve the exact pre-baseline v3 Inconclusive evidence. (dd8438593980)
- Tests: add foundation-only adversarial and concurrent native proof. (b0d5f388c312)
- Tests: add mutation, drift, replay, no-write, parser-corpus, sanitizer, and bounded libFuzzer coverage. (7c351e77b0ad)
- Tests: prove both successful construction and fail-closed unavailable entropy. (407fa0471ffb)
- Tests: fuzz the instrumented permit core rather than only the entry executable. (5f9f122d6d3e)
- Tests: Bind compaction and contributor-truth assertions to the policy phase. (ec4159f05678)
- Tests: lock exact integration identities and authority exclusions in project-state regression checks. (dac01182292b)
- Tests: add canonical digest, mutation, broad-root, verdict, exclusion, and truth regression coverage. (cf674d852e16)
- Tests: bind exact review, merge, reproduction, counts, no-active-task checkpoint, and no-authority state. (d46aab915432)
- Tests: bound project-state and policy validation to canonical promotion, ancestry, tree identity, and candidate activation. (690728884f7e)
- Tests: add synthetic execution and adversarial proof without running Factorio. (4e20ff3a44d5)
- Tests: retain precise failure diagnostics for process identity, lifecycle progression, and journal persistence. (678d985ad984)
- Tests: preserve platform-specific candidate assertions without weakening cross-platform foundation coverage. (67110899db21)
- Tests: make temporary string construction explicit without changing fixture semantics. (da3e2274a3dc)
- Tests: update generated-truth and target-profile assertions for the verdict phase. (e60ff931317a)
- Tests: lock exact closeout revisions, workflow identities, and path-filtered schema disposition. (4bc2ec135fe2)
- Tests: Cover evidence mutation, path safety, source non-inference, and observer parsing. (71fc4f95e274)
- Tests: Add adversarial mutation coverage for every reviewed evidence boundary. (1aebc65dcdc3)
- Tests: Make synthetic Windows observer-tool identity fixtures host-independent. (6b3a300aa6d7)
- Tests: added signed-package, mismatch, wrong-version, unsafe-path, (f03d771ce218)
- Tests: Added exact profile, buffer, keyword, mutation, start-argument, and WPR loss-message coverage. (dfc741e107c3)
- Tests: Added explicit LF/CRLF identity parity and retained semantic mutation refusal. (0800e2f26bf5)
- Tests: canonical cross-language digest, external/protected-write, wrong-image, wrong-PID, PID-reuse, source-boundary, and human-verdict-law coverage. (995e6130210d)
- Tests: cross-platform canonicalization remains enabled. (89d69de0884a)

## Validation Summary

- b0d5f388c312: MinGW GCC facman_operation_permit_smoke build: PASS.
- b0d5f388c312: MinGW GCC facman_operation_permit_smoke build: PASS.
- b0d5f388c312: MinGW GCC facman_operation_permit_smoke build: PASS.
- b0d5f388c312: MinGW GCC facman_operation_permit_smoke build: PASS.
- b0d5f388c312: MinGW GCC facman_operation_permit_smoke build: PASS.
- b0d5f388c312: MinGW GCC facman_operation_permit_smoke build: PASS.
- e883ab5cf18b: py -3 tools/aide_queue_state_check.py --strict: PASS.
- e883ab5cf18b: py -3 tools/aide_queue_state_check.py --strict: PASS.
- e883ab5cf18b: py -3 tools/aide_queue_state_check.py --strict: PASS.
- e883ab5cf18b: py -3 tools/aide_queue_state_check.py --strict: PASS.

## Known Risks

- b0d5f388c312: The core is reachable only by internal native callers; product issuance and every real effect remain unavailable.
- b0d5f388c312: The core is reachable only by internal native callers; product issuance and every real effect remain unavailable.
- b0d5f388c312: The core is reachable only by internal native callers; product issuance and every real effect remain unavailable.
- b0d5f388c312: The core is reachable only by internal native callers; product issuance and every real effect remain unavailable.
- b0d5f388c312: The core is reachable only by internal native callers; product issuance and every real effect remain unavailable.
- b0d5f388c312: The core is reachable only by internal native callers; product issuance and every real effect remain unavailable.
- e883ab5cf18b: Scope authorization alone changes no CI behavior or product authority.
- e883ab5cf18b: Scope authorization alone changes no CI behavior or product authority.
- e883ab5cf18b: Scope authorization alone changes no CI behavior or product authority.
- e883ab5cf18b: Scope authorization alone changes no CI behavior or product authority.

## Follow-up

- b0d5f388c312: Implement exact Factorio permit resources and an execution-free owning-provider verifier.
- b0d5f388c312: Implement exact Factorio permit resources and an execution-free owning-provider verifier.
- b0d5f388c312: Implement exact Factorio permit resources and an execution-free owning-provider verifier.
- b0d5f388c312: Implement exact Factorio permit resources and an execution-free owning-provider verifier.
- b0d5f388c312: Implement exact Factorio permit resources and an execution-free owning-provider verifier.
- b0d5f388c312: Implement exact Factorio permit resources and an execution-free owning-provider verifier.
- e883ab5cf18b: Implement and wire the permit envelope and canonical claims fuzz harnesses.
- e883ab5cf18b: Implement and wire the permit envelope and canonical claims fuzz harnesses.
- e883ab5cf18b: Implement and wire the permit envelope and canonical claims fuzz harnesses.
- e883ab5cf18b: Implement and wire the permit envelope and canonical claims fuzz harnesses.

## Warnings

- 91c2aa4fe0a3 merge commit ignored
- 11feb2e53539 merge commit ignored
- 810e92ccd52a merge commit ignored
- 08d4318ffd32 merge commit ignored
- 6dcfb29ed556 merge commit ignored
- 51f4fc24c916 merge commit ignored
- cb7b951b1fc8 merge commit ignored
- ca9ca5db4435 merge commit ignored
- 0b8783325233 merge commit ignored
- df580f00600c merge commit ignored
- e9c1e69fee1a merge commit ignored
- 5b2459bf1642 merge commit ignored
- 6ade64d41927 merge commit ignored
- 14ce6ded2b04 merge commit ignored
- 802b3fdda510 merge commit ignored
- 8d95513fe815 merge commit ignored
- a8c73eb4e34f merge commit ignored
- 2 malformed or legacy commits require review

## Preview Caveat

- This draft is not an official release note and does not create tags or GitHub Releases.
