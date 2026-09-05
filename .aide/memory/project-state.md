# FacMan Project State

Generated from `release/index/project_status.v2.toml`, the workspace lock,
the command/refusal registries, capability policy, and support matrix.
Edit canonical inputs, then run `py -3 tools/project_state.py --write`.

Tracked revision fields describe the reviewed checkpoint and retain their
v1 compatibility names. They do not claim to be the live checkout HEAD.
Generate that fail-closed observation after checkout with
`tools/current_checkout_observation.py`.

## Current product truth

- phase: `facman_0_1_alpha6_workspace_migration_recovery` / `alpha6_workspace_migration_recovery_active_beta_gates_pending`;
- charter: Create any number of independent Factorio setups, select one, and launch the normal game as though it had always been installed and configured exactly that way.
- persona: A Factorio player who wants multiple complete, isolated game environments without rebuilding versions, mods, profiles, accounts, or settings by hand.
- golden journey: `find Factorio -> select/create instance -> choose version/preset/profiles/modpack/accounts -> inspect readiness -> prepare if needed -> Play to menu -> start/load/join/edit -> exit -> preserve state -> relaunch`;
- checkpoint: `facman-0-1-alpha6-workspace-migration-recovery`;
- active WorkUnit: `FACMAN-0.1-ALPHA6-WORKSPACE-MIGRATION-RECOVERY-01`;
- next dependency-ready WorkUnit: `FACMAN-0.1-ALPHA6-WORKSPACE-MIGRATION-RECOVERY-01`;
- next authority gate: `alpha6_workspace_migration_and_managed_install_then_alpha7_content_world_play_and_frontend_parity_then_feature_freeze_and_exact_beta_human_release_authority`;
- truth scope: `phase0_governance_integrated_alpha6_workspace_migration_recovery_active_alpha5_candidate_revision_exact_all_human_execution_and_release_authority_closed`; canonical main promotion: `true`; local counts promoted: `false`;
- alpha.5 exact candidate: source `4683ecd9a1b9ead5eb84be152760d12583da0f0e` (tree `c07938618bc0f533fd12756cba123f54b8592048`), run `33603385303` attempt `1`;
- alpha.5 candidate boundary: closeout qualified `false`; future revision requires a new run `true`;
- Gate 0 integration: `accepted_reviewed_dev_integration` at dev `62c2503110cdb89b9cc89f19a69903f214d33e3c`;
- Gate 1 installation closeout: `accepted_reviewed_dev_integration` at dev `6ec47046d1b1f4ab8bddfcc27bcec76a774ff305`;
- Gate 2 instance closeout: `accepted_reviewed_dev_integration` at dev `bbb46c5bfd10cd35fb965b23edc4951784f93ef4`;
- Gate 3 permit closeout: `accepted_reviewed_dev_integration` at dev `91c2aa4fe0a30be97bf16165b41a95a8fab4cd11`;
- Gates 0-3 canonical integration: `accepted_canonical_main_dev_synchronized` at main `810e92ccd52ad89fada8a9bb5699805cb5580c24` and synchronized dev `08d4318ffd32bd9553ce8914cbd8bfc98fde7b74`;
- Gate 4A hermetic Play policy: `accepted_canonical_main_dev_synchronized` with digest `6fde31f26d57e23d67c01dd598cb869a4914d11711868b46d4f817709455e7a2`;
- Gate 4B hermetic Play candidate: `eligible_for_human_verdict` at dev `e9c1e69fee1ae815f62638db8b7263cb01b70389`;
- execution: `unavailable` / `alpha6_workspace_migration_recovery_active_exact_play_route_unaccepted`;
- Safe beta: `false`;
- release: `unpublished` / `not_proven_unsigned`.

## Readiness dimensions

- playability: `product_complete_real_route_unaccepted`;
- user workflow: `complete_alpha6_workspace_migration_recovery_then_managed_install_alpha7_content_world_play_frontends_feature_freeze_and_exact_beta_human_gates`;
- safety authority: `final_candidate_machine_evidence_only_real_play_install_acceptance_signing_notarization_publication_and_support_authority_closed`;
- platform support: `windows_x64_exact_candidate_reference_pending_human_macos_intel_and_linux_x64_machine_qualified_packages_semantic_gui_previews`;
- release authenticity: `not_proven_unsigned`;
- compatibility: `experimental_public_subset`;
- user validation: `exact_alpha5_candidate_machine_qualification_passed_human_acceptance_pending`;

## Execution guarantees

- `instance_isolated`: product mode `accepted`, claim `unproven`, next gate `FACMAN-WINDOWS-INSTANCE-ISOLATED-PLAY-CANDIDATE-01`. The exact FacMan-owned instance closure is writable; protected software roots remain immutable; enumerated OS, driver, or platform state may change only after explicit disclosure.
- `hermetic`: product mode `accepted`, claim `unproven`, next gate `FACMAN-HERMETIC-PLAY-SANDBOX-POLICY-01`. An enforced isolation boundary prevents persistent change outside the authorised FacMan workspace.

## Instance product programme

- status: `gate2_read_only_projection_complete`;
- active WorkUnit: `FACMAN-INSTANCE-SPEC-AND-READINESS-01`;
- next WorkUnit: `FACMAN-OPERATION-PERMIT-01`;
- portable record: `InstanceSpec`;
- machine-local record: `InstanceBinding`;
- readiness: `computed_projection_not_authoritative_state`;
- preparation: `federated_typed_subplans_by_owner`;
- default launch intent: `menu`;
- launch intents: `menu, continue_last, load_save, new_game, map_editor, connect_server, start_server, benchmark, instrumented_dev`;
- save role: `optional_content_within_instance`;
- profile families: `LaunchProfile, GraphicsProfile, AudioProfile, InterfaceProfile, MultiplayerProfile, ServerProfile, NewGameProfile, BackupProfile`;
- account bindings: `PlatformAccountBinding, FactorioAccountBinding, PlayerIdentityProfile, ServerCredentialBinding`;
- secondary save/world WorkUnit: `FACMAN-WORLD-BUNDLE-AND-SAVE-COMPATIBILITY-01`;
- runtime authority: `false`;

## Operation-permit programme

- status: `gate3_infrastructure_complete_no_issuance`;
- WorkUnit: `FACMAN-OPERATION-PERMIT-01`;
- authority model: `short_lived_plan_bound_exact_resource_permit`;
- provider revalidation required: `true`;
- permit issuance authority: `false`;

## Host-environment programme

- status: `planned_parallel_support_lane`;
- next WorkUnit: `HOST-ENVIRONMENT-CONTRACT-SPINE-01`;
- first runtime scope: `workflow_specific_read_only_list_inspect_doctor`;
- first apply WorkUnit: `WINDOWS-SANDBOX-PROFILE-01`;
- installation-model-v2 reviewed, committed, and clean: `true`;
- blocks real Play: `false`;
- host mutation authority: `false`;
- privileged broker authority: `false`;
- prerequisite: the current convergence, execution-foundation, and installation-model-v2 tree must be reviewed, committed, and reproduced cleanly.

## Capability snapshot

- available: `install.discover, install.model.inspect, install.reconciliation.plan, install.reference.register, launch.preflight, launch.preview`;
- conditional: `install.managed.plan, process.execute`;
- backlog: `install.existing.adoption.plan, install.existing.inspect`;
- unavailable: `credential.factorio.read, install.existing.adoption.apply, install.managed.apply, launch.execute.hermetic, launch.execute.instance_isolated, network.mod_portal.read, network.mod_portal.write, release.publish, release.sign`;

## Historical proof boundary

- completed technical wave: `m2`;
- last closed WorkUnit: `FACMAN-BETA-RULESET-AND-TAG-PROTECTION-01`;
- accepted FacMan integration: `c5262596483a5a9767b4c66d4d5ef51b8086cfdc`;
- historical Steam-backed H1 candidate/result: `eb629caaec9d62536a272336e940c0d3003fdaae` / `Fail`;
- Universal Launcher / Setup pins: `5479939ca5cbc9ee0f901608a92012778b4752ae` / `d2a2aae7e61c47035c92334b0522143b4fea3880`;
- M2 synthetic managed-target result: `MachinePass`;
- M3 disposition: `authorized_backlog_after_playable_alpha`; adoption apply remains `false`.

Historical M1/M2 details remain in `release/index/project_status.v2.toml`,
`.aide/history/`, and `docs/release/checkpoints/`. They do not select current
work or promote execution, network, credential, signing, or publication authority.

## Contract and validation identity

- commands / registered routes: `131` / `129`;
- schemas / refusal codes: `414` / `250`;
- command catalog digest: `535183d19263892d224965cc1ca1ab6b73e8d2da969926f8af07b78d1c702f9d`;
- accepted historical CI revision: `2f13923a9cbdd60d47cab114ba1e280282259bb5`;
- accepted historical matrix: `35` native and `337` Python tests.

## Quarantined capabilities

- launch.execute.instance_isolated
- launch.execute.hermetic
- process.execute
- install.managed.apply outside newly created, explicitly selected, policy-approved managed targets
- install.existing.adoption.apply
- network.mod_portal.read
- network.mod_portal.write
- credential.factorio.read
- release.sign
- release.publish

## Known blockers

- Alpha.1 and alpha.2 are immutable historical private drafts; their cancelled packets cannot satisfy beta acceptance.
- Alpha.3 is an immutable annotated tag with a verified exact eight-asset private draft; its cancelled, unexecuted packet cannot satisfy beta acceptance, the tag must not move, and the draft remains unpublished.
- Beta.1 requires a fresh, distinct exact-byte human receipt bound to the final candidate; no such verdict has been accepted.
- Route v5 is integrated and exact. Its new D3/D4 request records no authorization, live value, permit, execution, or verdict; every earlier authorization is expired.
- Public alpha, beta, RC, stable, signing, support, and route-promotion authority remain absent; the requested GitHub object is a private draft prerelease only.
- Any byte change after the alpha.3 tag requires another forward-only prerelease version.
- Alpha.5 source 4683ecd9a1b9ead5eb84be152760d12583da0f0e is the final exact-candidate machine-qualified source; the truth-only closeout and every future product revision do not inherit that qualification.
- Real Play, managed-install acceptance, cross-platform GUI semantics, accessibility, performance, security fault testing, signing, notarization, publication, and support remain separate gates.

## Authorities

- current status: `release/index/project_status.v2.toml`;
- capability vocabulary: `contracts/policy/capabilities.v1.toml`;
- provider revisions: `release/index/workspace_lock.v1.toml`;
- platform proof: `release/index/support_matrix.v1.toml`;
- claim limitations: `docs/quality/safety_claim_ledger.md`;
- accepted evidence: `.aide/history/` and `docs/release/checkpoints/`.
