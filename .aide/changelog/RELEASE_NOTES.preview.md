# AIDE Release Notes Preview

This is a deterministic preview only. It does not publish a release.

source_range: facman-r2-local-alpha-proof-0..HEAD
source_head: 4360d0f40c38d9e7f0c69151f57fd0a9ee7a92b5
preview_only: true

## Highlights

- Security: apply contracts remain unavailable and digest/confirmation bound. (d1fb7f97572a)
- Security: no apply route mutates setup state or enables Factorio execution. (7850424d3e35)
- Security: reference consumption does not grant setup mutation or execution authority. (0ce7802d9f5b)
- Security: all writes stay below an exclusive disposable root; foreign content is retained and reported. (f4fdafead6a0)
- Security: Proof refuses dirty source state and preserves unsigned/no-execution authority boundaries. (34e025540fe2)
- Security: Live-target apply, execution, H1, Steam, network, registry, elevation, signing, and publication boundaries remain closed. (efe06f385795)
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
- Added: explicit generated managed-setup lifecycle workflows. (d1fb7f97572a)
- Added: canonical CLI plan/apply/recovery grammar. (7850424d3e35)
- Added: exact managed setup-state identity on FacMan install references. (0ce7802d9f5b)
- Added: reproducible synthetic three-repository managed lifecycle proof. (f4fdafead6a0)
- Added: Complete selected-package reproducibility proof. (34e025540fe2)
- Added: Revision-pinned M1 managed portable-install checkpoint. (efe06f385795)
- Added: explicit M2 live portable setup state with a pending human gate. (df0e42b6131f)
- Added: immutable M2-WU1 live-target policy checkpoint. (b1a1795c90e2)
- Added: bounded M2-WU2 public lifecycle activation WorkUnit. (effce1f71784)
- Added: immutable M2-WU2 implementation and package proof. (129f70d13058)
- Added: evidence-only WU2 dev integration closeout lane. (2c55d1d111a2)
- Added: immutable exact-dev WU2 integration evidence. (182ada6be86d)
- Changed: setup requests now use typed target, plan, digest, and confirmation fields. (7850424d3e35)
- Changed: setup lifecycle commands now compose through their owning application handler. (d72c56b6802e)
- Changed: Canonical project truth now records fixture-proven M1 and current 35/337 validation inventory. (efe06f385795)
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
- Fixed: FacMan now consumes the scheduler-independent Universal Setup proof head. (c24237e82245)
- Fixed: legacy repair and uninstall grammar remains unambiguous beside phase subcommands. (7850424d3e35)
- Fixed: Reproducibility proof no longer treats the owned-output marker as a package archive. (2f13923a9cbd)
- Fixed: New non-ignored source files are now checked before their first commit. (5b01b36fb989)
- Fixed: M1 checkpoint satisfies the repository line-length policy. (5b01b36fb989)
- Fixed: complete provider license closure in built packages. (71dacb277dc8)
- Fixed: workspace status now reports the exact current Universal provider pins. (724246e53b57)
- Fixed: durable transaction journals no longer fail at legacy MAX_PATH. (c253e05d882c)
- Fixed: closeout truth retains frozen M1 identities while recording the later license proof separately. (0b4e1688b4fc)
- Fixed: project-state compaction test now recognizes the accepted license checkpoint. (2b5098b076ab)
- Fixed: adequate capacity fluctuations no longer invalidate a reviewed plan. (d16e71357f13)
- Fixed: raw Python tests now use the canonical current native-smoke CLI by default. (316ee8efec5b)
- Deprecated: legacy setup verbs are internal compatibility aliases. (d1fb7f97572a)
- Docs: records the managed setup frontend command law. (7850424d3e35)
- Docs: project truth reflects 121 commands, 228 schemas, and 216 refusal codes. (d72c56b6802e)
- Docs: records the exact fixture journey and non-authority claims. (f4fdafead6a0)
- Docs: Repository front doors now distinguish the implemented fixture authority from unavailable ordinary apply. (efe06f385795)
- Docs: bind M1 canonical public integration evidence. (92da90101342)
- Docs: record the accepted operator decision and retained redistribution notices. (b1fd720013ed)
- Docs: add immutable license integration checkpoint and complete queue evidence. (0b4e1688b4fc)
- Docs: generated project truth now reports the active bounded WorkUnit. (df0e42b6131f)
- Tests: adds a strict generated workflow guard. (d1fb7f97572a)
- Tests: managed install identities now round-trip through the native workspace repository. (0ce7802d9f5b)
- Tests: launch remains preview-only, ordinary setup apply remains unavailable, and H1 remains failed. (f4fdafead6a0)
- Tests: Windows CI now executes two independent package builds and compares their complete evidence closure. (34e025540fe2)
- Tests: Added artifact-classification regression coverage. (2f13923a9cbd)
- Tests: Added pre-commit file-discovery regression coverage. (5b01b36fb989)
- Tests: protect additive public-integration truth and unchanged authority boundaries. (92da90101342)
- Tests: preserve historical M1 provider identities separately from current pins. (b1fd720013ed)
- Tests: exercise portable CLI, TUI, WinForms, relocation, tamper, SBOM, and provenance lanes. (71dacb277dc8)
- Tests: preserve lock/runtime revision parity. (724246e53b57)
- Tests: enforce the extended-path native I/O contract on Windows. (c253e05d882c)
- Tests: retain independent assertions for frozen M1 implementation and public integration records. (2b5098b076ab)
- Tests: provider and project-state assertions follow the canonical merge. (dfa0d8ad3c4c)
- Tests: target policy adds one integrated native test, bringing this build to 36/36. (b1a1795c90e2)

## Validation Summary

- c24237e82245: Setup exact-main CI 29293560341 test, sanitizer, and fuzz-smoke: PASS.
- d1fb7f97572a: py -3 tools/codegen/generate_metadata.py --check: PASS.
- d1fb7f97572a: py -3 tools/codegen/generate_metadata.py --check: PASS.
- d1fb7f97572a: py -3 tools/codegen/generate_metadata.py --check: PASS.
- d1fb7f97572a: py -3 tools/codegen/generate_metadata.py --check: PASS.
- 7850424d3e35: cmake --build build/m1-wu10 --config Debug --parallel: PASS.
- 7850424d3e35: cmake --build build/m1-wu10 --config Debug --parallel: PASS.
- 7850424d3e35: cmake --build build/m1-wu10 --config Debug --parallel: PASS.
- 7850424d3e35: cmake --build build/m1-wu10 --config Debug --parallel: PASS.
- 7850424d3e35: cmake --build build/m1-wu10 --config Debug --parallel: PASS.

## Known Risks

- c24237e82245: FacMan hosted cross-platform confirmation remains required at the new exact head.
- d1fb7f97572a: No ordinary setup apply route is authorized; fixture-backed lifecycle integration remains WU11 work.
- d1fb7f97572a: No ordinary setup apply route is authorized; fixture-backed lifecycle integration remains WU11 work.
- d1fb7f97572a: No ordinary setup apply route is authorized; fixture-backed lifecycle integration remains WU11 work.
- d1fb7f97572a: No ordinary setup apply route is authorized; fixture-backed lifecycle integration remains WU11 work.
- 7850424d3e35: Lifecycle operations remain deliberately unavailable to ordinary users; only their contract and refusal paths are active.
- 7850424d3e35: Lifecycle operations remain deliberately unavailable to ordinary users; only their contract and refusal paths are active.
- 7850424d3e35: Lifecycle operations remain deliberately unavailable to ordinary users; only their contract and refusal paths are active.
- 7850424d3e35: Lifecycle operations remain deliberately unavailable to ordinary users; only their contract and refusal paths are active.
- 7850424d3e35: Lifecycle operations remain deliberately unavailable to ordinary users; only their contract and refusal paths are active.

## Follow-up

- c24237e82245: Rebuild the complete FacMan matrix and update PR #5.
- d1fb7f97572a: Route the canonical descriptors through the application boundary and prove frontend refusal behavior.
- d1fb7f97572a: Route the canonical descriptors through the application boundary and prove frontend refusal behavior.
- d1fb7f97572a: Route the canonical descriptors through the application boundary and prove frontend refusal behavior.
- d1fb7f97572a: Route the canonical descriptors through the application boundary and prove frontend refusal behavior.
- 7850424d3e35: Build the cross-repository synthetic lifecycle proof and consume verified setup results through Launcher references.
- 7850424d3e35: Build the cross-repository synthetic lifecycle proof and consume verified setup results through Launcher references.
- 7850424d3e35: Build the cross-repository synthetic lifecycle proof and consume verified setup results through Launcher references.
- 7850424d3e35: Build the cross-repository synthetic lifecycle proof and consume verified setup results through Launcher references.
- 7850424d3e35: Build the cross-repository synthetic lifecycle proof and consume verified setup results through Launcher references.

## Warnings

- 10b1caa915ed merge commit ignored
- cfd30b769cc9 merge commit ignored
- 73bec99916d5 merge commit ignored
- cc4d79fec9d0 merge commit ignored
- a5e1461ac46d merge commit ignored
- d96384bf8f48 merge commit ignored
- 747b4442cf22 merge commit ignored
- 178de3192f3c merge commit ignored
- 10 malformed or legacy commits require review

## Preview Caveat

- This draft is not an official release note and does not create tags or GitHub Releases.
