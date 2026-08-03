# AIDE Release Notes Preview

This is a deterministic preview only. It does not publish a release.

source_range: facman-r2-local-alpha-proof-0..HEAD
source_head: 7ebbfa37b23ee173cbb15f399935d0e035e79375
preview_only: true

## Highlights

- Security: pull-request CI receives no signing credentials and cannot produce promoting signed claims. (c740c01505e1)
- Security: no signing credentials or protected route authority are introduced. (7c47bd1998f5)
- Security: no credential, signing, route, provider, or execution authority changes. (88b45dba6289)
- Security: live Play, signing, publication, and stable support remain false until independent evidence closes their blockers. (e3c2735d2861)
- Security: no authority, credential, signing, route, or publication change. (3709b57efa3b)
- Security: no credential, route, provider, signing, or product-execution authority changes. (038e593073b6)
- Security: no product, route, credential, signing, or publication authority changes. (70496e17de02)
- Security: no credential, route, provider, signing, or execution authority changes. (a40301ccfa57)
- Security: Candidate construction fails closed when concrete local workspace or user-profile paths are embedded. (cd28b4d6b247)
- Security: hostile local Git provenance now fails closed before HEAD, pin, reachability, or ABI claims. (dc659ad4e390)
- Security: enabled worktree-scoped includes remain detected and rejected before object evidence. (f04f8cc7777b)
- Security: observer provenance rules remain strict; CI removes temporary indirection instead of whitelisting it. (99deb2f834d8)
- Security: Backend descendants are assigned to a kill-on-close Job Object before execution resumes. (d6082beddd55)
- Added: backend-derived native C1 shell presentation and explicit evidence mode. (2e18e6d88730)
- Added: native preview runtime and frontend-package evidence tooling. (c740c01505e1)
- Added: provisional Windows C1 candidate evidence, release notes, and hosted artifact preservation. (e3c2735d2861)
- Added: end-to-end synthetic candidate inspection coverage. (70496e17de02)
- Added: versioned current-checkout and provider observation artifacts. (85752696c27d)
- Added: exact merge-checkout and provider observation artifacts in CI. (d23833e01f3b)
- Added: three bounded pre-C1 hardening work units and a clean-Windows qualification trigger. (74e6c9726894)
- Changed: Play is dispatched only after fresh backend readiness enables the exact registered route. (2e18e6d88730)
- Changed: GTK compile proof is recorded while runtime, package, publication, and support remain unproven. (c740c01505e1)
- Changed: preview proof probes now select explicit evidence mode after live-shell integration. (7c47bd1998f5)
- Changed: WinForms package selection prefers Release output and targets Windows 10/11 x64. (e3c2735d2861)
- Changed: Windows C1 candidate development now consumes exact integrated native preview proof. (41cc512407e3)
- Changed: Current execution truth observes integrated dev 6eb682e3449e464693a9f1d3758040e4709a32ed. (4ce4f6d54e3b)
- Changed: Revalidation-04 is superseded and archived before observer self-test. (0f037b36bef2)
- Changed: narrowed archive-boundary descriptions without changing repository or effect authority. (fcfb7c752237)
- Changed: packaged live acceptance now follows the ratified capability, promotion, hardening, workspace, and package order. (74e6c9726894)
- Changed: Revalidation-04 is historical and a fresh successor chain is required. (6fa120523c46)
- Changed: Promoted the reviewed three-repository convergence baseline to canonical source truth. (bfac7ce41f19)
- Fixed: GTK transport payload scoping and terminal recovery-history handling. (2e18e6d88730)
- Fixed: external AT-SPI/Orca liveness evidence and dirty-source attribution controls. (c740c01505e1)
- Fixed: AppKit Objective-C++ linkage and GTK accelerator query compilation. (7c47bd1998f5)
- Fixed: a hung AT-SPI query can no longer monopolize the GTK qualification process. (88b45dba6289)
- Fixed: local clean construction can no longer be mislabeled as hosted evidence. (3709b57efa3b)
- Fixed: GTK proof failures now terminate promptly and preserve their actionable error. (038e593073b6)
- Fixed: explicit HighContrast launches no longer fail because the desktop preference retains another name. (a40301ccfa57)
- Fixed: Generated execution dashboard remains within its bounded size at WIP 3/3. (54c4f46623a4)
- Fixed: Windows release-candidate artifacts can no longer silently bind a temporary pull-request merge revision. (4ce4f6d54e3b)
- Fixed: Product archives no longer include historical checkpoint evidence with developer-machine paths. (cd28b4d6b247)
- Fixed: Package release metadata no longer includes repository-only state with absolute build paths. (872402f0b088)
- Fixed: tracked checkpoint SHAs no longer impersonate live checkout observations. (bad4de6615a5)
- Fixed: cross-SID observation now requires a visible, bounded trust decision. (41121af2dae8)
- Fixed: clean normalized worktrees no longer produce configuration-dependent dirty claims. (8db4bba7db8a)
- Fixed: observation artifacts can no longer mutate a passed provider checkout. (6d2a0f281cd9)
- Fixed: component ownership review metadata now matches the completed authority review. (a1eb28caa4f2)
- Fixed: offline checkout evidence no longer implies remote source closure or trusts redirected object provenance. (dc659ad4e390)
- Fixed: normal linked task worktrees no longer fail merely because worktree-specific config is disabled. (f04f8cc7777b)
- Fixed: hosted checkout observation no longer inherits temporary credential includes from actions/checkout. (99deb2f834d8)
- Fixed: PR #114 exact-head qualification failures. (8dc376cc3b53)
- Fixed: Windows empty-clone proof now reconstructs tracked long paths without changing global Git configuration. (93027f2232cf)
- Fixed: WinForms process transport no longer projects malformed or mismatched backend output as success. (d6082beddd55)
- Docs: Added the permanent suspension checkpoint and generated truth updates. (0f037b36bef2)
- Docs: added the canonical three-repository convergence synthesis and repaired stale extraction-gate names. (edf599f6e6b2)
- Docs: normalized the ownership section without changing repository authority. (8b239e72d5c0)
- Docs: added the local current-truth observation workflow. (41704238677f)
- Docs: documented the canonical truth hierarchy and independent convergence train law. (fcfb7c752237)
- Docs: Preserved concise superseded-stage truth across generated surfaces. (8dc376cc3b53)
- Docs: Ratified the nine-lane convergence architecture and complete C1 release sequence. (6fa120523c46)
- Docs: Documented the proof-local long-path policy. (93027f2232cf)
- Docs: bound the WinForms C1 transport contract and closeout packet. (a90720ca9943)
- Tests: Added exact transport-envelope and Meson/GLib regressions. (2e18e6d88730)
- Tests: Added full synthetic candidate inspection regression. (41cc512407e3)
- Tests: Added source mismatch, revision syntax, workflow binding, and CI provenance regressions. (4ce4f6d54e3b)
- Tests: Added checkpoint-exclusion and cross-platform developer-path regressions. (cd28b4d6b247)
- Tests: Added exact release-metadata closure and path-integrity coverage. (872402f0b088)
- Tests: Updated current-truth regressions for the suspended gate. (0f037b36bef2)
- Tests: added hostile Git and read-only boundary proofs. (6d2a0f281cd9)
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

## Validation Summary

- 2e18e6d88730: `dotnet build apps/gui/windows/winforms/FacMan.WinForms.csproj --configuration Release --no-restore`: PASS.
- 2e18e6d88730: `dotnet build apps/gui/windows/winforms/FacMan.WinForms.csproj --configuration Release --no-restore`: PASS.
- 2e18e6d88730: `dotnet build apps/gui/windows/winforms/FacMan.WinForms.csproj --configuration Release --no-restore`: PASS.
- 2e18e6d88730: `dotnet build apps/gui/windows/winforms/FacMan.WinForms.csproj --configuration Release --no-restore`: PASS.
- 2e18e6d88730: `dotnet build apps/gui/windows/winforms/FacMan.WinForms.csproj --configuration Release --no-restore`: PASS.
- c740c01505e1: `python -m unittest` focused preview/package suites: PASS (21 tests).
- c740c01505e1: `python -m unittest` focused preview/package suites: PASS (21 tests).
- c740c01505e1: `python -m unittest` focused preview/package suites: PASS (21 tests).
- c740c01505e1: `python -m unittest` focused preview/package suites: PASS (21 tests).
- c740c01505e1: `python -m unittest` focused preview/package suites: PASS (21 tests).

## Known Risks

- 2e18e6d88730: AppKit and GTK native runtime behavior remains subject to exact-head hosted CI.
- 2e18e6d88730: AppKit and GTK native runtime behavior remains subject to exact-head hosted CI.
- 2e18e6d88730: AppKit and GTK native runtime behavior remains subject to exact-head hosted CI.
- 2e18e6d88730: AppKit and GTK native runtime behavior remains subject to exact-head hosted CI.
- 2e18e6d88730: AppKit and GTK native runtime behavior remains subject to exact-head hosted CI.
- c740c01505e1: Current archives are frontend-only prototypes and are not clean-machine launcher packages.
- c740c01505e1: Current archives are frontend-only prototypes and are not clean-machine launcher packages.
- c740c01505e1: Current archives are frontend-only prototypes and are not clean-machine launcher packages.
- c740c01505e1: Current archives are frontend-only prototypes and are not clean-machine launcher packages.
- c740c01505e1: Current archives are frontend-only prototypes and are not clean-machine launcher packages.

## Follow-up

- 2e18e6d88730: Activate C1-WINDOWS-RELEASE-CANDIDATE-01 from the exact post-merge dev head.
- 2e18e6d88730: Activate C1-WINDOWS-RELEASE-CANDIDATE-01 from the exact post-merge dev head.
- 2e18e6d88730: Activate C1-WINDOWS-RELEASE-CANDIDATE-01 from the exact post-merge dev head.
- 2e18e6d88730: Activate C1-WINDOWS-RELEASE-CANDIDATE-01 from the exact post-merge dev head.
- 2e18e6d88730: Activate C1-WINDOWS-RELEASE-CANDIDATE-01 from the exact post-merge dev head.
- c740c01505e1: Keep C1-PREVIEW-RUNTIME-PACKAGES-01 active until every recorded blocker is closed by exact evidence.
- c740c01505e1: Keep C1-PREVIEW-RUNTIME-PACKAGES-01 active until every recorded blocker is closed by exact evidence.
- c740c01505e1: Keep C1-PREVIEW-RUNTIME-PACKAGES-01 active until every recorded blocker is closed by exact evidence.
- c740c01505e1: Keep C1-PREVIEW-RUNTIME-PACKAGES-01 active until every recorded blocker is closed by exact evidence.
- c740c01505e1: Keep C1-PREVIEW-RUNTIME-PACKAGES-01 active until every recorded blocker is closed by exact evidence.

## Warnings

- a7d3837aae9d merge commit ignored
- 84cbd3695a8f merge commit ignored
- fc4bfc5430a3 merge commit ignored
- 7ebbfa37b23e merge commit ignored
- 4 malformed or legacy commits require review

## Preview Caveat

- This draft is not an official release note and does not create tags or GitHub Releases.
