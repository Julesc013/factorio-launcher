# AIDE Release Notes Preview

This is a deterministic preview only. It does not publish a release.

source_range: facman-r2-local-alpha-proof-0..HEAD
source_head: f1a9996d391ba19a4c5ce4e418193e6067bfd722
preview_only: true

## Highlights

- Security: recovery.apply and ordinary live apply remain unavailable. (129f70d13058)
- Security: pending human verdict, ordinary live apply hold, recovery hold, and execution ban are unchanged. (e4b03c82b649)
- Security: ordinary managed apply, recovery apply, execution, and publication remain unavailable. (182ada6be86d)
- Security: all human, recovery, execution, and publication holds remain unchanged. (cad50062c955)
- Security: No apply authority; default and incomplete configurations refuse. (99f8cd8319ad)
- Security: Human acceptance remains non-automatable and every setup apply remains blocked. (0e50b6fe0e90)
- Security: retained Universal Setup policy ownership and the live_target_acceptance_required gate. (991ff78c5cc3)
- Security: protected-root observation still terminates timed-out children and records the skipped observation truthfully. (d59d22a27b08)
- Security: retained Universal Setup policy ownership and human-gated apply. (79577fd7eb8a)
- Added: immutable M2-WU2 implementation and package proof. (129f70d13058)
- Added: evidence-only WU2 dev integration closeout lane. (2c55d1d111a2)
- Added: immutable exact-dev WU2 integration evidence. (182ada6be86d)
- Added: retained live synthetic install lifecycle evidence. (a286b5c42736)
- Added: stable managed_install_recovery_required handoff with stale launch-plan projection. (480a58ca4c10)
- Added: Real target-bound Factorio portable install planning. (99f8cd8319ad)
- Added: consistent managed-portable setup review workflow across all shipped client families. (991ff78c5cc3)
- Changed: project truth now distinguishes implementation proof from dev integration and human acceptance. (129f70d13058)
- Changed: WU2 is closed locally pending reviewed dev integration. (e4b03c82b649)
- Changed: branch governance evidence now reflects the completed WU2 head. (f051731b80b5)
- Changed: public lifecycle is dev-integrated pending operator acceptance. (182ada6be86d)
- Changed: WU2 exact-dev integration is fully closed. (cad50062c955)
- Changed: publication governance reports now match the closed evidence head. (53ebb488daad)
- Changed: project truth now points at the canonical WU4 provider. (a286b5c42736)
- Fixed: rebuilt preferred native CLI to align runtime status with provider lock. (a286b5c42736)
- Fixed: Retained precise legacy archive refusal ordering. (952c46a629f0)
- Fixed: Implemented command contract now has both success and dynamic refusal evidence. (00ca569368dd)
- Fixed: process supervision now honors short deadlines under a slow Windows process-query provider. (d59d22a27b08)
- Docs: accepted WU3 reviewed dev integration evidence. (067397e592ce)
- Docs: bind run, packet, journal, audit, state, and package identities. (a286b5c42736)
- Docs: WU4 is now accepted as dev-integrated while its human verdict remains pending. (a6cfe28c704d)
- Docs: WU6 now records accepted dev integration proof pending only the human M2 verdict. (a64037693f4b)
- Docs: WU6 compaction law now matches its accepted dev integration. (00ca569368dd)
- Docs: Added the M2-WU7 immutable implementation checkpoint. (0e50b6fe0e90)
- Docs: Final package evidence is revision-pinned and immutable. (526d6f5a2d1c)
- Docs: recorded WU7 exact dev integration evidence. (d3b5458645e2)
- Docs: recorded the WU8 local proof candidate. (6ca7e62889f6)
- Docs: published the local WU8 implementation and package checkpoint. (79577fd7eb8a)
- Tests: enforce immutable integration identities and retained human gate. (067397e592ce)
- Tests: enforce pending verdict and zero authority promotion. (a286b5c42736)
- Tests: complete Launcher handoff proof and immutable WU5 dev evidence are now recorded. (d746454ca850)
- Tests: Correct synthetic ZIP CRC metadata and prove planning causes no state or target creation. (99f8cd8319ad)
- Tests: Added CLI-level immutable plan and no-write coverage. (952c46a629f0)
- Tests: pinned every required workflow label and authority boundary. (991ff78c5cc3)

## Validation Summary

- 129f70d13058: Clean three-repository reconstruction: PASS.
- 129f70d13058: Clean three-repository reconstruction: PASS.
- 129f70d13058: Clean three-repository reconstruction: PASS.
- e4b03c82b649: AIDE task inspection: PASS and complete with no missing evidence.
- e4b03c82b649: AIDE task inspection: PASS and complete with no missing evidence.
- f051731b80b5: AIDE git detect: PASS with high-confidence task/dev/main roles.
- 2c55d1d111a2: Exact dev CI, CodeQL, and security policy: PASS.
- 182ada6be86d: Exact dev CI 29326004461: PASS.
- 182ada6be86d: Exact dev CI 29326004461: PASS.
- 182ada6be86d: Exact dev CI 29326004461: PASS.

## Known Risks

- 129f70d13058: Hosted FacMan dev workflows and the human live-target verdict are still pending.
- 129f70d13058: Hosted FacMan dev workflows and the human live-target verdict are still pending.
- 129f70d13058: Hosted FacMan dev workflows and the human live-target verdict are still pending.
- e4b03c82b649: Hosted PR and exact dev workflow evidence remain unavailable until publication and merge.
- e4b03c82b649: Hosted PR and exact dev workflow evidence remain unavailable until publication and merge.
- f051731b80b5: No remote branch, pull request, or repository setting has changed in this commit.
- 2c55d1d111a2: No product behavior or authority changes; the human M2 verdict remains pending.
- 182ada6be86d: The human M2 verdict remains pending and no live acceptance lifecycle has run.
- 182ada6be86d: The human M2 verdict remains pending and no live acceptance lifecycle has run.
- 182ada6be86d: The human M2 verdict remains pending and no live acceptance lifecycle has run.

## Follow-up

- 129f70d13058: Review and close the implementation WorkUnit, merge it to dev, and bind exact hosted workflow identities separately.
- 129f70d13058: Review and close the implementation WorkUnit, merge it to dev, and bind exact hosted workflow identities separately.
- 129f70d13058: Review and close the implementation WorkUnit, merge it to dev, and bind exact hosted workflow identities separately.
- e4b03c82b649: Push the reviewed branch, merge it to dev after green checks, and add a separate exact-dev integration record.
- e4b03c82b649: Push the reviewed branch, merge it to dev after green checks, and add a separate exact-dev integration record.
- f051731b80b5: Re-run the helper plan from a clean tree, then push and open the reviewed dev PR.
- 2c55d1d111a2: Bind merge/run identities, validate project truth, close the task, and land the record on dev.
- 182ada6be86d: Review and close this evidence WorkUnit, land it on dev, then open WU3 live evidence packet work.
- 182ada6be86d: Review and close this evidence WorkUnit, land it on dev, then open WU3 live evidence packet work.
- 182ada6be86d: Review and close this evidence WorkUnit, land it on dev, then open WU3 live evidence packet work.

## Warnings

- 747b4442cf22 merge commit ignored
- 178de3192f3c merge commit ignored
- a8b298a35cd1 merge commit ignored
- 476813e6fc74 merge commit ignored
- 5563e3b8de43 merge commit ignored
- f4b02ac022ee merge commit ignored
- 8c1ed5351133 merge commit ignored
- 37c83c653882 merge commit ignored
- f1a9996d391b merge commit ignored
- 14 malformed or legacy commits require review

## Preview Caveat

- This draft is not an official release note and does not create tags or GitHub Releases.
