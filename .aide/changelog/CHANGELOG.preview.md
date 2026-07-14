# AIDE Changelog Preview

This file is generated from local Git history and is a preview only.

source_range: facman-r2-local-alpha-proof-0..HEAD
source_head: f1a9996d391ba19a4c5ce4e418193e6067bfd722
commit_count: 50
malformed_count: 14
preview_only: true
release_publishing: false

## Summary

- Added: 7
- Changed: 7
- Fixed: 4
- Security: 9
- Docs: 10
- Tests: 6
- Internal: 8
- Risks: 2
- Follow-up: 2

## Added

- immutable M2-WU2 implementation and package proof. (129f70d13058 docs(m2): bind the public lifecycle proof)
- evidence-only WU2 dev integration closeout lane. (2c55d1d111a2 chore(m2): open the WU2 dev integration proof)
- immutable exact-dev WU2 integration evidence. (182ada6be86d docs(m2): bind the exact WU2 dev integration)
- retained live synthetic install lifecycle evidence. (a286b5c42736 chore(m2): close WU4 live synthetic acceptance proof)
- stable managed_install_recovery_required handoff with stale launch-plan projection. (480a58ca4c10 feat(handoff): integrate Launcher recovery projection)
- Real target-bound Factorio portable install planning. (99f8cd8319ad feat(setup): route Factorio installs through target-bound planning)
- consistent managed-portable setup review workflow across all shipped client families. (991ff78c5cc3 feat(frontend): generate the portable setup review workflow)

## Changed

- project truth now distinguishes implementation proof from dev integration and human acceptance. (129f70d13058 docs(m2): bind the public lifecycle proof)
- WU2 is closed locally pending reviewed dev integration. (e4b03c82b649 chore(m2): close the public lifecycle work unit)
- branch governance evidence now reflects the completed WU2 head. (f051731b80b5 chore(aide): refresh the WU2 branch identity)
- public lifecycle is dev-integrated pending operator acceptance. (182ada6be86d docs(m2): bind the exact WU2 dev integration)
- WU2 exact-dev integration is fully closed. (cad50062c955 chore(m2): close the WU2 dev integration proof)
- publication governance reports now match the closed evidence head. (53ebb488daad chore(aide): refresh the integration proof branch)
- project truth now points at the canonical WU4 provider. (a286b5c42736 chore(m2): close WU4 live synthetic acceptance proof)

## Fixed

- rebuilt preferred native CLI to align runtime status with provider lock. (a286b5c42736 chore(m2): close WU4 live synthetic acceptance proof)
- Retained precise legacy archive refusal ordering. (952c46a629f0 test(cli): prove configured setup planning stays read only)
- Implemented command contract now has both success and dynamic refusal evidence. (00ca569368dd fix(contracts): complete install plan success truth)
- process supervision now honors short deadlines under a slow Windows process-query provider. (d59d22a27b08 fix(probe): preserve supervision deadlines under host load)

## Security

- recovery.apply and ordinary live apply remain unavailable. (129f70d13058 docs(m2): bind the public lifecycle proof)
- pending human verdict, ordinary live apply hold, recovery hold, and execution ban are unchanged. (e4b03c82b649 chore(m2): close the public lifecycle work unit)
- ordinary managed apply, recovery apply, execution, and publication remain unavailable. (182ada6be86d docs(m2): bind the exact WU2 dev integration)
- all human, recovery, execution, and publication holds remain unchanged. (cad50062c955 chore(m2): close the WU2 dev integration proof)
- No apply authority; default and incomplete configurations refuse. (99f8cd8319ad feat(setup): route Factorio installs through target-bound planning)
- Human acceptance remains non-automatable and every setup apply remains blocked. (0e50b6fe0e90 docs(checkpoint): close WU7 portable planning candidate)
- retained Universal Setup policy ownership and the live_target_acceptance_required gate. (991ff78c5cc3 feat(frontend): generate the portable setup review workflow)
- protected-root observation still terminates timed-out children and records the skipped observation truthfully. (d59d22a27b08 fix(probe): preserve supervision deadlines under host load)
- retained Universal Setup policy ownership and human-gated apply. (79577fd7eb8a docs(checkpoint): close the WU8 generated workflow proof)

## Docs

- accepted WU3 reviewed dev integration evidence. (067397e592ce docs(m2): bind WU3 exact-dev integration proof)
- bind run, packet, journal, audit, state, and package identities. (a286b5c42736 chore(m2): close WU4 live synthetic acceptance proof)
- WU4 is now accepted as dev-integrated while its human verdict remains pending. (a6cfe28c704d docs(state): accept exact-dev WU4 integration)
- WU6 now records accepted dev integration proof pending only the human M2 verdict. (a64037693f4b docs(checkpoint): bind WU6 exact dev integration evidence)
- WU6 compaction law now matches its accepted dev integration. (00ca569368dd fix(contracts): complete install plan success truth)
- Added the M2-WU7 immutable implementation checkpoint. (0e50b6fe0e90 docs(checkpoint): close WU7 portable planning candidate)
- Final package evidence is revision-pinned and immutable. (526d6f5a2d1c docs(evidence): bind final WU7 package identities)
- recorded WU7 exact dev integration evidence. (d3b5458645e2 docs(checkpoint): bind WU7 exact dev integration evidence)
- recorded the WU8 local proof candidate. (6ca7e62889f6 docs(state): record the WU8 four-client proof candidate)
- published the local WU8 implementation and package checkpoint. (79577fd7eb8a docs(checkpoint): close the WU8 generated workflow proof)

## Tests

- enforce immutable integration identities and retained human gate. (067397e592ce docs(m2): bind WU3 exact-dev integration proof)
- enforce pending verdict and zero authority promotion. (a286b5c42736 chore(m2): close WU4 live synthetic acceptance proof)
- complete Launcher handoff proof and immutable WU5 dev evidence are now recorded. (d746454ca850 test(proof): bind complete WU6 validation identities)
- Correct synthetic ZIP CRC metadata and prove planning causes no state or target creation. (99f8cd8319ad feat(setup): route Factorio installs through target-bound planning)
- Added CLI-level immutable plan and no-write coverage. (952c46a629f0 test(cli): prove configured setup planning stays read only)
- pinned every required workflow label and authority boundary. (991ff78c5cc3 feat(frontend): generate the portable setup review workflow)

## Internal

- refreshed WU3 review-only changelog artifacts. (5f93f42f9708 chore(aide): refresh WU3 integration changelog preview)
- refresh generated project state and AIDE review artifacts. (067397e592ce docs(m2): bind WU3 exact-dev integration proof)
- WU6 local proof is closed pending reviewed dev integration. (f0b27c2e7f21 chore(aide): close WU6 Launcher handoff proof)
- Refreshed branch governance evidence only. (1b029ead969e chore(aide): refresh WU7 branch detection)
- opened WU8 without changing runtime authority. (d3b5458645e2 docs(checkpoint): bind WU7 exact dev integration evidence)
- advanced generated project truth to the 229-schema catalog. (6ca7e62889f6 docs(state): record the WU8 four-client proof candidate)
- closed the WU8 AIDE task with complete evidence. (79577fd7eb8a docs(checkpoint): close the WU8 generated workflow proof)
- refreshed non-mutating branch governance evidence for WU8. (d40596f0654b chore(aide): refresh the WU8 task branch detection)

## Risks

- no live acceptance or ordinary apply authority is inferred. (067397e592ce docs(m2): bind WU3 exact-dev integration proof)
- cross-volume and interruption recovery remain unproven. (a286b5c42736 chore(m2): close WU4 live synthetic acceptance proof)

## Follow-up

- run WU4 only with a harmless synthetic archive below D:\FacMan-Live-Acceptance\M2. (067397e592ce docs(m2): bind WU3 exact-dev integration proof)
- merge reviewed WU4 into dev, then open WU5 interruption/recovery. (a286b5c42736 chore(m2): close WU4 live synthetic acceptance proof)

## Malformed Commits

- 307690ad9bbb chore(m2): open live-target evidence packet work unit: missing_required_headings: ## Summary, ## Why, ## Changed, ## Validation, ## Changelog, ## Risks, ## Follow-up; missing_changelog_category
- 2e6012e0b14c build(provider): pin Universal Setup M2-WU3 main: missing_required_headings: ## Summary, ## Why, ## Changed, ## Validation, ## Changelog, ## Risks, ## Follow-up; missing_changelog_category
- ecec3a46e78a docs(state): bind M2-WU3 provider implementation proof: missing_required_headings: ## Summary, ## Why, ## Changed, ## Validation, ## Changelog, ## Risks, ## Follow-up; missing_changelog_category
- 057b4be50e43 docs(evidence): checkpoint WU3 implementation and package proof: missing_required_headings: ## Summary, ## Why, ## Changed, ## Validation, ## Changelog, ## Risks, ## Follow-up; missing_changelog_category
- 2678e1e23576 chore(m2): close WU3 without authority promotion: missing_required_headings: ## Summary, ## Why, ## Changed, ## Validation, ## Changelog, ## Risks, ## Follow-up; missing_changelog_category
- 461251d7fd3d fix(state): advance latest closed WorkUnit validator to WU3: missing_required_headings: ## Summary, ## Why, ## Changed, ## Validation, ## Changelog, ## Risks, ## Follow-up; missing_changelog_category
- 4360d0f40c38 chore(state): bind WU3 closeout and branch identity: missing_required_headings: ## Summary, ## Why, ## Changed, ## Validation, ## Changelog, ## Risks, ## Follow-up; missing_changelog_category
- 2d8b723ef048 build(provider): pin Universal Setup M2-WU4 main: missing_required_headings: ## Summary, ## Why, ## Changed, ## Validation, ## Changelog, ## Risks, ## Follow-up; missing_changelog_category; legacy_semi_structured_body
- b203574a8aa4 docs(m2): bind WU4 retained live lifecycle evidence: missing_required_headings: ## Summary, ## Why, ## Changed, ## Validation, ## Changelog, ## Risks, ## Follow-up; missing_changelog_category; legacy_semi_structured_body
- 61cdb5190d8e build(setup): pin Universal Setup WU5 recovery main: missing_required_headings: ## Summary, ## Why, ## Changed, ## Validation, ## Changelog, ## Risks, ## Follow-up; missing_changelog_category; legacy_semi_structured_body
- a056c4a62343 docs(state): bind WU5 interruption and recovery evidence: missing_required_headings: ## Summary, ## Why, ## Changed, ## Validation, ## Changelog, ## Risks, ## Follow-up; missing_changelog_category; legacy_semi_structured_body
- aa0aa89b4564 fix(status): report the locked WU5 setup revision: missing_required_headings: ## Summary, ## Why, ## Changed, ## Validation, ## Changelog, ## Risks, ## Follow-up; missing_changelog_category; legacy_semi_structured_body
- 7cc7ca39792e test(proof): bind complete WU5 validation identities: missing_required_headings: ## Summary, ## Why, ## Changed, ## Validation, ## Changelog, ## Risks, ## Follow-up; missing_changelog_category; legacy_semi_structured_body
- 7a14314940b3 chore(aide): close WU5 recovery integration proof: missing_required_headings: ## Summary, ## Why, ## Changed, ## Validation, ## Changelog, ## Risks, ## Follow-up; missing_changelog_category; legacy_semi_structured_body

## Release Caveat

- Preview only. No tags, GitHub Releases, branch mutation, or publishing were performed.
