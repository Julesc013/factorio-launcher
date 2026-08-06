# FacMan Project State

Generated from `release/index/project_status.v2.toml`, the workspace lock,
the command/refusal registries, capability policy, and support matrix.
Edit canonical inputs, then run `py -3 tools/project_state.py --write`.

Tracked revision fields describe the reviewed checkpoint and retain their
v1 compatibility names. They do not claim to be the live checkout HEAD.
Generate that fail-closed observation after checkout with
`tools/current_checkout_observation.py`.

## Current product truth

- phase: `provider_canonical_conformance_01` / `provider_sdk_consumption_complete_pending_integration`;
- charter: Create any number of independent Factorio setups, select one, and launch the normal game as though it had always been installed and configured exactly that way.
- persona: A Factorio player who wants multiple complete, isolated game environments without rebuilding versions, mods, profiles, accounts, or settings by hand.
- golden journey: `find Factorio -> select/create instance -> choose version/preset/profiles/modpack/accounts -> inspect readiness -> prepare if needed -> Play to menu -> start/load/join/edit -> exit -> preserve state -> relaunch`;
- checkpoint: `facman-provider-sdk-consumption`;
- active WorkUnit: `none`;
- next dependency-ready WorkUnit: `FACMAN-PROVIDER-PIN-RECONCILIATION-01`;
- next authority gate: `real-play-isolation`;
- truth scope: `provider_sdk_consumption_complete_pins_unreconciled_no_product_authority`; canonical main promotion: `false`; local counts promoted: `false`;
- Gate 0 integration: `accepted_reviewed_dev_integration` at dev `62c2503110cdb89b9cc89f19a69903f214d33e3c`;
- Gate 1 installation closeout: `accepted_reviewed_dev_integration` at dev `6ec47046d1b1f4ab8bddfcc27bcec76a774ff305`;
- Gate 2 instance closeout: `accepted_reviewed_dev_integration` at dev `bbb46c5bfd10cd35fb965b23edc4951784f93ef4`;
- Gate 3 permit closeout: `accepted_reviewed_dev_integration` at dev `91c2aa4fe0a30be97bf16165b41a95a8fab4cd11`;
- Gates 0-3 canonical integration: `accepted_canonical_main_dev_synchronized` at main `810e92ccd52ad89fada8a9bb5699805cb5580c24` and synchronized dev `08d4318ffd32bd9553ce8914cbd8bfc98fde7b74`;
- Gate 4A hermetic Play policy: `accepted_canonical_main_dev_synchronized` with digest `6fde31f26d57e23d67c01dd598cb869a4914d11711868b46d4f817709455e7a2`;
- Gate 4B hermetic Play candidate: `eligible_for_human_verdict` at dev `e9c1e69fee1ae815f62638db8b7263cb01b70389`;
- execution: `unavailable` / `provider_sdk_consumption_complete_no_product_play_authority`;
- Safe beta: `false`;
- release: `unpublished` / `not_proven_unsigned`.

## Readiness dimensions

- playability: `not_yet_playable`;
- user workflow: `native_c1_shell_present_provider_adoption_and_source_closure_pending`;
- safety authority: `provider_sdk_consumption_passed_non_authorizing_pins_unreconciled_source_closure_blocked`;
- platform support: `windows_first_alpha_planned`;
- release authenticity: `not_proven_unsigned`;
- compatibility: `experimental_public_subset`;
- user validation: `not_started`;

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
- last closed WorkUnit: `FACMAN-PROVIDER-SDK-CONSUMPTION-01`;
- accepted FacMan integration: `bd0642951a4a3abfb2cc1916c8b9c2c4e81d880f`;
- historical Steam-backed H1 candidate/result: `eb629caaec9d62536a272336e940c0d3003fdaae` / `Fail`;
- Universal Launcher / Setup pins: `7fc25340623131ba86c08dca4fb8a43b18a4520d` / `3048128963dc718a7c38c1cfcdda9e813a23b0db`;
- M2 synthetic managed-target result: `MachinePass`;
- M3 disposition: `authorized_backlog_after_playable_alpha`; adoption apply remains `false`.

Historical M1/M2 details remain in `release/index/project_status.v2.toml`,
`.aide/history/`, and `docs/release/checkpoints/`. They do not select current
work or promote execution, network, credential, signing, or publication authority.

## Contract and validation identity

- commands / registered routes: `125` / `123`;
- schemas / refusal codes: `331` / `242`;
- command catalog digest: `beb52338c984123c805a0c42c4d7e258702cdc9eac30f6357d6be557cc59cfb3`;
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

- Installation model v2 and deterministic reconciliation planning are complete read-only; authenticated source inspection and transaction-backed lifecycle apply remain unavailable.
- Official Factorio Windows installers share uninstall registration identities; installing an older version can supersede the current 2.1 Add/Remove Programs registration even when program directories are separate.
- Normal-host instance-isolated Play and enforced hermetic Play are independent, unproven real-product gates; Steam-aware Play remains a later route qualification.
- Gate 4C verdict attempt 01 is Inconclusive; the observer-start defect is repaired and live-proven without Factorio.
- Gate 4C verdict attempt 02 is blocked before baseline; its split-privilege repair remains accepted.
- Gate 4C Verdict 03 is Inconclusive after the first real launch because lifecycle packet staging collided and ETW target resolution remained incomplete.
- The same attempt changed the protected selected installation by creating NVIDIA Corporation/umdlogs.
- Verdict 03 proves that the frozen subdirectory-only writable model and normal-host Windows side effects cannot satisfy the current hermetic claim.
- The repaired Windows instance-isolated candidate is remotely reconstructible and historically qualified, but its revalidation was superseded before prepare because the human-verdict protocol requires integrity repairs.
- Revalidation 01 produced no authority or evidence; integrity repairs and fresh remote-only candidate qualification 03 are accepted.
- Revalidation 02 is superseded before prepare because its source-bound observer self-test lacks repository import closure; it produced no observer evidence, prepare, execution, verdict, or authority.
- Qualification-04 and its exact revalidation-03 stage are preserved, but revalidation-03 is superseded before observer start because Python observer identity and native session routing were bound to stale WorkUnits.
- Qualification-05 is accepted; revalidation-04's stage is preserved but owner direction superseded it before observer self-test. Pending renames blocked admission. No observer evidence, prepare, execution, verdict, or authority.
- The native WinForms, AppKit, and GTK shells now expose the backend-derived instance-to-Launch-Deck journey, but live Play remains unavailable until the exact registered route receives separate authority and evidence.
- Canonical ULK and USK SDK promotions are complete; FacMan still consumes ULK 7fc25340623131ba86c08dca4fb8a43b18a4520d and USK 3048128963dc718a7c38c1cfcdda9e813a23b0db.
- Provider-input, semantic conformance, and explicit non-adopted SDK consumption pass on Linux, Windows, and macOS; atomic pin reconciliation remains required.
- Successor source closure is required_but_blocked on coherent provider identity and a capable Windows host; the current managed host cannot spawn the native cmd.exe toolchain child process.
- AppKit has provisional native bundle runtime and frontend-only package proof on macos-15-intel, but the exact supported legacy toolchain, deployment-floor host, VoiceOver, full product closure, signing, and publication remain unproven.
- Artifacts are unsigned and unpublished; integrity and provenance do not authenticate a publisher.
- The verified WinForms backend binding is parent-mediated Windows evidence; actual packaged-GUI startup, standalone CLI/TUI/POSIX snapshot stability, and network/shared filesystems remain unproven.
- All current artifacts remain unsigned and unpublished; no current package authenticates a publisher or serves as canonical successor integration evidence.

## Authorities

- current status: `release/index/project_status.v2.toml`;
- capability vocabulary: `contracts/policy/capabilities.v1.toml`;
- provider revisions: `release/index/workspace_lock.v1.toml`;
- platform proof: `release/index/support_matrix.v1.toml`;
- claim limitations: `docs/quality/safety_claim_ledger.md`;
- accepted evidence: `.aide/history/` and `docs/release/checkpoints/`.
