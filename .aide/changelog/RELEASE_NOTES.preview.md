# AIDE Release Notes Preview

This is a deterministic preview only. It does not publish a release.

source_range: facman-r2-local-alpha-proof-0..HEAD
source_head: e119c221227be433edb74b5f993fe0d0b9645d47
preview_only: true

## Highlights

- Security: hostile local Git provenance now fails closed before HEAD, pin, reachability, or ABI claims. (dc659ad4e390)
- Security: enabled worktree-scoped includes remain detected and rejected before object evidence. (f04f8cc7777b)
- Security: observer provenance rules remain strict; CI removes temporary indirection instead of whitelisting it. (99deb2f834d8)
- Security: Backend descendants are assigned to a kill-on-close Job Object before execution resumes. (d6082beddd55)
- Security: Refuse mismatched or substituted packaged backends before effects. (ead81c5502d6)
- Security: Foreign, linked, changed, and inconclusive roots fail closed. (b0ad52b02e48)
- Security: No provider repin, setup mutation, product execution, signing, publication, or successor-route authority is opened. (35de93bdb9c0)
- Security: No provider repin, setup mutation, process execution, signing, publication, or successor authority is opened. (926850007a72)
- Security: No provider repin, setup mutation, product execution, signing, publication, consumer adoption, or successor authority is opened. (10f3ec73a792)
- Security: Stable provider pins and all product/setup/release authorities remain unchanged. (bcad50a66b1b)
- Security: No provider repin, setup mutation, product execution, signing, publication, adoption, or successor authority is opened. (b70be1069685)
- Security: Fail closed on input/output drift, unsafe paths, source replacement, link/reparse traversal, archive ambiguity, payload mismatch, and authority overreach. (bb2553fd282c)
- Added: three bounded pre-C1 hardening work units and a clean-Windows qualification trigger. (74e6c9726894)
- Added: Explicit FacMan workspace-root ownership authority. (b0ad52b02e48)
- Added: Synthetic product TCK is ready in the existing FacMan superbuild tests. (35de93bdb9c0)
- Added: Development-only neutral cross-provider contract TCK. (926850007a72)
- Added: Joint ULK/USK neutral fixture qualification in FacMan superbuild tests. (bcad50a66b1b)
- Added: Canonical neutral joint-fixture qualification for ULK and USK contracts. (b70be1069685)
- Added: Fresh successor Play route-definition and evidence-chain contract. (d31a9925fd16)
- Added: Deterministic per-target FacMan composition resolution with exact provider, path, authority, compatibility, qualification, and claim records. (bb2553fd282c)
- Added: Constrained staging and bounded directory/ZIP/TAR package verification against the selected composition. (bb2553fd282c)
- Added: Ratified universal product runtime and delivery programme and dependency-ordered preparation register. (04aba9d86e23)
- Changed: narrowed archive-boundary descriptions without changing repository or effect authority. (fcfb7c752237)
- Changed: packaged live acceptance now follows the ratified capability, promotion, hardening, workspace, and package order. (74e6c9726894)
- Changed: Revalidation-04 is historical and a fresh successor chain is required. (6fa120523c46)
- Changed: Promoted the reviewed three-repository convergence baseline to canonical source truth. (bfac7ce41f19)
- Changed: All three repositories now use the continuously integrated platform branch model. (2d582aad2566)
- Changed: provider contract records are design-ready and the synthetic TCK is dependency-blocked. (c4a86515a2c2)
- Changed: Provider contracts are fixture-qualified and workspace-root authority is complete. (35de93bdb9c0)
- Changed: Cross-provider contracts are jointly fixture-qualified and the synthetic TCK WorkUnit is complete. (10f3ec73a792)
- Changed: Establish FacMan as product composer and final product resolver while retaining provider ownership of reusable mechanisms. (23044eb15ae9)
- Changed: Separate observed identity, resolved product identity, package identity, authority, support, and publication claims. (23044eb15ae9)
- Changed: Refresh generated project and queue state after closeout. (d3ca9d3266bd)
- Changed: Canonical near-term queue now records provider source-versus-SDK conformance and reversible FacMan SDK adoption. (04aba9d86e23)
- Fixed: component ownership review metadata now matches the completed authority review. (a1eb28caa4f2)
- Fixed: offline checkout evidence no longer implies remote source closure or trusts redirected object provenance. (dc659ad4e390)
- Fixed: normal linked task worktrees no longer fail merely because worktree-specific config is disabled. (f04f8cc7777b)
- Fixed: hosted checkout observation no longer inherits temporary credential includes from actions/checkout. (99deb2f834d8)
- Fixed: PR #114 exact-head qualification failures. (8dc376cc3b53)
- Fixed: Windows empty-clone proof now reconstructs tracked long paths without changing global Git configuration. (93027f2232cf)
- Fixed: WinForms process transport no longer projects malformed or mismatched backend output as success. (d6082beddd55)
- Fixed: acquisition/setup and content-store ownership are no longer assigned wholesale to USK. (c4a86515a2c2)
- Fixed: Preserve the output-ownership safety refusal even when external dependency metadata cannot be observed. (bb2553fd282c)
- Docs: documented the canonical truth hierarchy and independent convergence train law. (fcfb7c752237)
- Docs: Preserved concise superseded-stage truth across generated surfaces. (8dc376cc3b53)
- Docs: Ratified the nine-lane convergence architecture and complete C1 release sequence. (6fa120523c46)
- Docs: Documented the proof-local long-path policy. (93027f2232cf)
- Docs: bound the WinForms C1 transport contract and closeout packet. (a90720ca9943)
- Docs: Record the reviewed C1 backend-identity development integration. (3fed61d3547b)
- Docs: Record canonical C1 backend-identity integration. (85896eb24b79)
- Docs: Refresh repository release-note projections through composition compiler closeout. (8c45e9104ea0)
- Docs: Bound the structured implementation commit to validation evidence. (e119c221227b)
- Tests: added adversarial include, alternate, shallow, promisor, explicit-policy, and no-lazy-fetch coverage. (dc659ad4e390)
- Tests: locked the Setup-input versus Factorio-data archive distinction. (fcfb7c752237)
- Tests: locked candidate/gate identities, truth hierarchy, activation law, dependencies, and final triggers. (74e6c9726894)
- Tests: added positive and hostile linked-worktree regression coverage. (f04f8cc7777b)
- Tests: CI proof now locks ephemeral checkout credentials for the observation lane. (99deb2f834d8)
- Tests: Updated the exact reviewed development revision. (8dc376cc3b53)
- Tests: Enforced hardening-before-successor ordering and suspended-gate truth. (6fa120523c46)
- Tests: Locked clone and detached-checkout command construction. (93027f2232cf)
- Tests: Added executable WinForms transport and complete process-tree cleanup proof. (5c56eecd1492)
- Tests: repaired qualification probes without changing product authority. (ed7884be0b3b)
- Tests: Added branch-policy enforcement and updated WIP assertions. (2d582aad2566)
- Tests: Seven-state, adoption rollback, marker-drift, plan, and provider-wave checks. (b0ad52b02e48)
- Tests: Correct the cross-platform marker-tamper expectation without weakening root authority. (81e0d9bf2b32)
- Tests: Align cross-platform CLI fixtures with the seven-state workspace ownership contract. (bdd0a48c409e)
- Tests: Fail-closed controls for pin drift, identity reuse, premature evidence, authority, verdict, and digest changes. (d31a9925fd16)
- Tests: Cover determinism, environment independence, minimal conflict diagnostics, cycles, overlap, tampering, equivalence, and embedded resolution. (bb2553fd282c)
- Tests: Added offline constitutional, authority, provider-mode, and plan-drift enforcement. (04aba9d86e23)

## Validation Summary

- a1eb28caa4f2: `python tools/component_ownership_check.py`: PASS.
- dc659ad4e390: python -m unittest tests.test_current_checkout_observation tests.test_ci_proof -v: PASS (23 tests).
- dc659ad4e390: python -m unittest tests.test_current_checkout_observation tests.test_ci_proof -v: PASS (23 tests).
- dc659ad4e390: python -m unittest tests.test_current_checkout_observation tests.test_ci_proof -v: PASS (23 tests).
- fcfb7c752237: python tools/component_ownership_check.py: PASS.
- fcfb7c752237: python tools/component_ownership_check.py: PASS.
- fcfb7c752237: python tools/component_ownership_check.py: PASS.
- 74e6c9726894: python -m unittest tests.test_plan_views -v: PASS (19 tests).
- 74e6c9726894: python -m unittest tests.test_plan_views -v: PASS (19 tests).
- 74e6c9726894: python -m unittest tests.test_plan_views -v: PASS (19 tests).

## Known Risks

- a1eb28caa4f2: None; authority assignments and extraction obligations are byte-for-byte unchanged.
- dc659ad4e390: The observer deliberately cannot establish current remote state; tools/remote_source_closure.py remains required for that stronger claim.
- dc659ad4e390: The observer deliberately cannot establish current remote state; tools/remote_source_closure.py remains required for that stronger claim.
- dc659ad4e390: The observer deliberately cannot establish current remote state; tools/remote_source_closure.py remains required for that stronger claim.
- fcfb7c752237: None; no component owner, final owner, extraction dependency, provider pin, runtime code, or Setup mutation authority changed.
- fcfb7c752237: None; no component owner, final owner, extraction dependency, provider pin, runtime code, or Setup mutation authority changed.
- fcfb7c752237: None; no component owner, final owner, extraction dependency, provider pin, runtime code, or Setup mutation authority changed.
- 74e6c9726894: These are planned prerequisites only; they grant no observer, permit, execution, route, Setup, signing, publication, or release authority.
- 74e6c9726894: These are planned prerequisites only; they grant no observer, permit, execution, route, Setup, signing, publication, or release authority.
- 74e6c9726894: These are planned prerequisites only; they grant no observer, permit, execution, route, Setup, signing, publication, or release authority.

## Follow-up

- a1eb28caa4f2: Advance reviewed_on only after a future whole-manifest authority review.
- dc659ad4e390: Run the complete exact-head qualification matrix after the remaining ratified architecture and plan amendments.
- dc659ad4e390: Run the complete exact-head qualification matrix after the remaining ratified architecture and plan amendments.
- dc659ad4e390: Run the complete exact-head qualification matrix after the remaining ratified architecture and plan amendments.
- fcfb7c752237: Commit the synchronized canonical C1 dependency graph and generated views.
- fcfb7c752237: Commit the synchronized canonical C1 dependency graph and generated views.
- fcfb7c752237: Commit the synchronized canonical C1 dependency graph and generated views.
- 74e6c9726894: Run full exact-head native, Python, AIDE, observer, architecture, plan, and authority-preservation qualification.
- 74e6c9726894: Run full exact-head native, Python, AIDE, observer, architecture, plan, and authority-preservation qualification.
- 74e6c9726894: Run full exact-head native, Python, AIDE, observer, architecture, plan, and authority-preservation qualification.

## Warnings

- a7d3837aae9d merge commit ignored
- 84cbd3695a8f merge commit ignored
- fc4bfc5430a3 merge commit ignored
- 7ebbfa37b23e merge commit ignored
- e1304bafb961 merge commit ignored
- 7 malformed or legacy commits require review

## Preview Caveat

- This draft is not an official release note and does not create tags or GitHub Releases.
