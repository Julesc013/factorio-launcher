# AIDE Release Notes Preview

This is a deterministic preview only. It does not publish a release.

source_range: facman-r2-local-alpha-proof-0..HEAD
source_head: d746454ca85090eff7d9e4c6a1723f495da596d1
preview_only: true

## Highlights

- Security: verify exact provider notice digests and source identities. (b1fd720013ed)
- Security: prevent SBOM/package claims without retained provider notices. (71dacb277dc8)
- Security: long-path operations retain no-follow, no-clobber, and identity checks. (c253e05d882c)
- Security: retain unsigned/unpublished and no-authority boundaries explicitly. (0b4e1688b4fc)
- Security: ordinary live apply remains unavailable and execution authority remains false. (df0e42b6131f)
- Security: no live mutation authority is enabled by this pin update. (dfa0d8ad3c4c)
- Security: mutation authority remains false and the human verdict remains pending. (b1a1795c90e2)
- Security: plan remains read-only, apply remains exact-plan-gated, and the human verdict remains pending. (effce1f71784)
- Security: no target or execution authority is promoted by the pin alone. (cfb70ab88de3)
- Security: ordinary live apply, execution, H1, signing, and publication remain unavailable. (57b175ab9378)
- Security: actual current capacity is still revalidated and insufficient space still refuses. (d16e71357f13)
- Security: recovery.apply and ordinary live apply remain unavailable. (129f70d13058)
- Security: pending human verdict, ordinary live apply hold, recovery hold, and execution ban are unchanged. (e4b03c82b649)
- Security: ordinary managed apply, recovery apply, execution, and publication remain unavailable. (182ada6be86d)
- Security: all human, recovery, execution, and publication holds remain unchanged. (cad50062c955)
- Added: explicit M2 live portable setup state with a pending human gate. (df0e42b6131f)
- Added: immutable M2-WU1 live-target policy checkpoint. (b1a1795c90e2)
- Added: bounded M2-WU2 public lifecycle activation WorkUnit. (effce1f71784)
- Added: immutable M2-WU2 implementation and package proof. (129f70d13058)
- Added: evidence-only WU2 dev integration closeout lane. (2c55d1d111a2)
- Added: immutable exact-dev WU2 integration evidence. (182ada6be86d)
- Added: retained live synthetic install lifecycle evidence. (a286b5c42736)
- Added: stable managed_install_recovery_required handoff with stale launch-plan projection. (480a58ca4c10)
- Changed: Universal provider license identity from NOASSERTION to MIT at pinned revisions. (b1fd720013ed)
- Changed: both Universal dependencies now have accepted MIT and reproducibility truth. (0b4e1688b4fc)
- Changed: current Universal Setup provider identity now includes the fail-closed M2 target policy. (dfa0d8ad3c4c)
- Changed: project truth now records WU1 policy proof and WU2 public-activation handoff. (b1a1795c90e2)
- Changed: WU1 now records accepted dev integration proof. (effce1f71784)
- Changed: bundled Universal Setup provider identity now names the M2-WU2 canonical main merge. (cfb70ab88de3)
- Changed: canonical project truth now identifies the public lifecycle provider candidate. (57b175ab9378)
- Changed: project truth now distinguishes implementation proof from dev integration and human acceptance. (129f70d13058)
- Changed: WU2 is closed locally pending reviewed dev integration. (e4b03c82b649)
- Changed: branch governance evidence now reflects the completed WU2 head. (f051731b80b5)
- Changed: public lifecycle is dev-integrated pending operator acceptance. (182ada6be86d)
- Changed: WU2 exact-dev integration is fully closed. (cad50062c955)
- Changed: publication governance reports now match the closed evidence head. (53ebb488daad)
- Changed: project truth now points at the canonical WU4 provider. (a286b5c42736)
- Fixed: complete provider license closure in built packages. (71dacb277dc8)
- Fixed: workspace status now reports the exact current Universal provider pins. (724246e53b57)
- Fixed: durable transaction journals no longer fail at legacy MAX_PATH. (c253e05d882c)
- Fixed: closeout truth retains frozen M1 identities while recording the later license proof separately. (0b4e1688b4fc)
- Fixed: project-state compaction test now recognizes the accepted license checkpoint. (2b5098b076ab)
- Fixed: adequate capacity fluctuations no longer invalidate a reviewed plan. (d16e71357f13)
- Fixed: raw Python tests now use the canonical current native-smoke CLI by default. (316ee8efec5b)
- Fixed: rebuilt preferred native CLI to align runtime status with provider lock. (a286b5c42736)
- Docs: record the accepted operator decision and retained redistribution notices. (b1fd720013ed)
- Docs: add immutable license integration checkpoint and complete queue evidence. (0b4e1688b4fc)
- Docs: generated project truth now reports the active bounded WorkUnit. (df0e42b6131f)
- Docs: accepted WU3 reviewed dev integration evidence. (067397e592ce)
- Docs: bind run, packet, journal, audit, state, and package identities. (a286b5c42736)
- Docs: WU4 is now accepted as dev-integrated while its human verdict remains pending. (a6cfe28c704d)
- Tests: preserve historical M1 provider identities separately from current pins. (b1fd720013ed)
- Tests: exercise portable CLI, TUI, WinForms, relocation, tamper, SBOM, and provenance lanes. (71dacb277dc8)
- Tests: preserve lock/runtime revision parity. (724246e53b57)
- Tests: enforce the extended-path native I/O contract on Windows. (c253e05d882c)
- Tests: retain independent assertions for frozen M1 implementation and public integration records. (2b5098b076ab)
- Tests: provider and project-state assertions follow the canonical merge. (dfa0d8ad3c4c)
- Tests: target policy adds one integrated native test, bringing this build to 36/36. (b1a1795c90e2)
- Tests: enforce immutable integration identities and retained human gate. (067397e592ce)
- Tests: enforce pending verdict and zero authority promotion. (a286b5c42736)
- Tests: complete Launcher handoff proof and immutable WU5 dev evidence are now recorded. (d746454ca850)

## Validation Summary

- b1fd720013ed: `py -3 .aide/scripts/aide_lite.py test`: PASS.
- b1fd720013ed: `py -3 .aide/scripts/aide_lite.py test`: PASS.
- b1fd720013ed: `py -3 .aide/scripts/aide_lite.py test`: PASS.
- b1fd720013ed: `py -3 .aide/scripts/aide_lite.py test`: PASS.
- b1fd720013ed: `py -3 .aide/scripts/aide_lite.py test`: PASS.
- b1fd720013ed: `py -3 .aide/scripts/aide_lite.py test`: PASS.
- 71dacb277dc8: Windows Release rebuild against final provider pins: PASS.
- 71dacb277dc8: Windows Release rebuild against final provider pins: PASS.
- 71dacb277dc8: Windows Release rebuild against final provider pins: PASS.
- 71dacb277dc8: Windows Release rebuild against final provider pins: PASS.

## Known Risks

- b1fd720013ed: None beyond the unchanged unsigned and unpublished distribution boundary.
- b1fd720013ed: None beyond the unchanged unsigned and unpublished distribution boundary.
- b1fd720013ed: None beyond the unchanged unsigned and unpublished distribution boundary.
- b1fd720013ed: None beyond the unchanged unsigned and unpublished distribution boundary.
- b1fd720013ed: None beyond the unchanged unsigned and unpublished distribution boundary.
- b1fd720013ed: None beyond the unchanged unsigned and unpublished distribution boundary.
- 71dacb277dc8: Expected package-tree and archive digest changes are not yet accepted until the fresh reproducibility proof completes.
- 71dacb277dc8: Expected package-tree and archive digest changes are not yet accepted until the fresh reproducibility proof completes.
- 71dacb277dc8: Expected package-tree and archive digest changes are not yet accepted until the fresh reproducibility proof completes.
- 71dacb277dc8: Expected package-tree and archive digest changes are not yet accepted until the fresh reproducibility proof completes.

## Follow-up

- b1fd720013ed: Close package-license inclusion and produce a dedicated reproducibility checkpoint.
- b1fd720013ed: Close package-license inclusion and produce a dedicated reproducibility checkpoint.
- b1fd720013ed: Close package-license inclusion and produce a dedicated reproducibility checkpoint.
- b1fd720013ed: Close package-license inclusion and produce a dedicated reproducibility checkpoint.
- b1fd720013ed: Close package-license inclusion and produce a dedicated reproducibility checkpoint.
- b1fd720013ed: Close package-license inclusion and produce a dedicated reproducibility checkpoint.
- 71dacb277dc8: Produce and checkpoint exact clean package, SBOM, and provenance identities.
- 71dacb277dc8: Produce and checkpoint exact clean package, SBOM, and provenance identities.
- 71dacb277dc8: Produce and checkpoint exact clean package, SBOM, and provenance identities.
- 71dacb277dc8: Produce and checkpoint exact clean package, SBOM, and provenance identities.

## Warnings

- cc4d79fec9d0 merge commit ignored
- a5e1461ac46d merge commit ignored
- d96384bf8f48 merge commit ignored
- 747b4442cf22 merge commit ignored
- 178de3192f3c merge commit ignored
- a8b298a35cd1 merge commit ignored
- 476813e6fc74 merge commit ignored
- 5563e3b8de43 merge commit ignored
- f4b02ac022ee merge commit ignored
- 14 malformed or legacy commits require review

## Preview Caveat

- This draft is not an official release note and does not create tags or GitHub Releases.
