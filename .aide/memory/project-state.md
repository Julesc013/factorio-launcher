# FacMan Project State

Generated from `release/index/project_status.v2.toml`, the workspace lock,
the command/refusal registries, capability policy, and support matrix.
Edit canonical inputs, then run `py -3 tools/project_state.py --write`.

## Current product truth

- phase: `multi_version_install_lifecycle` / `active`;
- charter: Choose a world, press Play, and remain in control of everything that changes.
- persona: A Factorio player who wants multiple safe, reproducible worlds without managing launcher internals.
- golden journey: `find Factorio -> choose or create a world -> review readiness -> Play -> exit -> relaunch`;
- checkpoint: `multi-version-install-lifecycle`;
- active WorkUnit: `FACMAN-MULTI-VERSION-INSTALL-LIFECYCLE-01`;
- next WorkUnit: `FACMAN-WORLD-SPEC-AND-READINESS-01`;
- next authority gate: `real-play-isolation`;
- execution: `unavailable` / `real_play_gate_not_passed`;
- Safe beta: `false`;
- release: `unpublished` / `not_proven_unsigned`.

## Readiness dimensions

- playability: `not_yet_playable`;
- user workflow: `advanced_command_surface_only`;
- safety authority: `execution_foundation_proven_real_play_unproven`;
- platform support: `windows_first_alpha_planned`;
- release authenticity: `not_proven_unsigned`;
- compatibility: `experimental_public_subset`;
- user validation: `not_started`;

## Execution guarantees

- `instance_isolated`: product mode `accepted`, claim `unproven`, next gate `FACMAN-STEAM-AWARE-PLAY-01`. FacMan-owned instance data is isolated; enumerated Steam/platform state may change after explicit disclosure.
- `hermetic`: product mode `accepted`, claim `unproven`, next gate `FACMAN-HERMETIC-STANDALONE-PLAY-01`. No persistent change may occur outside the authorised FacMan workspace.

## World product programme

- status: `planned_after_installation_model_v2_closeout`;
- next WorkUnit: `FACMAN-WORLD-SPEC-AND-READINESS-01`;
- portable record: `WorldSpec`;
- machine-local record: `WorldBinding`;
- readiness: `computed_projection_not_authoritative_state`;
- preparation: `federated_typed_subplans_by_owner`;
- runtime authority: `false`;

## Operation-permit programme

- status: `planned_after_world_readiness`;
- WorkUnit: `FACMAN-OPERATION-PERMIT-01`;
- authority model: `short_lived_plan_bound_exact_resource_permit`;
- provider revalidation required: `true`;
- permit issuance authority: `false`;

## Host-environment programme

- status: `planned_parallel_support_lane`;
- next WorkUnit: `HOST-ENVIRONMENT-CONTRACT-SPINE-01`;
- first runtime scope: `workflow_specific_read_only_list_inspect_doctor`;
- first apply WorkUnit: `WINDOWS-SANDBOX-PROFILE-01`;
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
- last closed historical WorkUnit: `FACMAN-EXECUTION-FOUNDATION-01`;
- accepted FacMan integration: `bd0642951a4a3abfb2cc1916c8b9c2c4e81d880f`;
- historical Steam-backed H1 candidate/result: `eb629caaec9d62536a272336e940c0d3003fdaae` / `Fail`;
- Universal Launcher / Setup pins: `7bd4425f0c35414f738159b45d8bec42edf70235` / `3f8489275077347c2918f3bb03614ec6431362ff`;
- M2 synthetic managed-target result: `MachinePass`;
- M3 disposition: `authorized_backlog_after_playable_alpha`; adoption apply remains `false`.

Historical M1/M2 details remain in `release/index/project_status.v2.toml`,
`.aide/history/`, and `docs/release/checkpoints/`. They do not select current
work or promote execution, network, credential, signing, or publication authority.

## Contract and validation identity

- commands / registered routes: `123` / `121`;
- schemas / refusal codes: `250` / `217`;
- command catalog digest: `671764ee966fe44d269d6787664049383ff461152616762b4312b0a1789abfdb`;
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

- The local Wube-signed Factorio 2.0.77 conversion succeeded, but FacMan does not yet expose authenticated source inspection or transaction-backed lifecycle apply as product commands.
- Official Factorio Windows installers share uninstall registration identities; installing an older version can supersede the current 2.1 Add/Remove Programs registration even when program directories are separate.
- Steam-aware instance-isolated Play and hermetic standalone Play are independent, unproven real-product gates.
- The current desktop UI exposes commands rather than the first-run world-to-Play journey.
- AppKit remains compile-only until an actual bundle runtime invocation is recorded.
- Artifacts are unsigned and unpublished; integrity and provenance do not authenticate a publisher.

## Authorities

- current status: `release/index/project_status.v2.toml`;
- capability vocabulary: `contracts/policy/capabilities.v1.toml`;
- provider revisions: `release/index/workspace_lock.v1.toml`;
- platform proof: `release/index/support_matrix.v1.toml`;
- claim limitations: `docs/quality/safety_claim_ledger.md`;
- accepted evidence: `.aide/history/` and `docs/release/checkpoints/`.
