Completed `DOMINIUM-UNIVERSAL-BOUNDARY-AUDIT-01` as a read-only audit.

## Audit identity

```toml
repository = "Julesc013/dominium"
source_commit = "623ab08ae8c867719d5abc2e60c16a6fbb37b313"
head = "623ab08ae8c867719d5abc2e60c16a6fbb37b313"
audit_date = "2026-08-04"
read_only = true
implementation_moved = false
branch = "main"
upstream_delta = "+0/-0"
worktree_before = "clean"
worktree_after = "clean"
definitions_reviewed = 740
c_cpp_contract_declarations_reviewed = 101
files_modified = 0
tests_run = []
validation = ["git diff --check", "git status --short --branch", "git rev-parse HEAD"]
```

**No-code-move verdict:** this audit moved no implementation code, changed no Dominium file, opened no setup or execution authority, and authorizes no extraction. It is a characterization and convergence map only.

No current deletion is ratifiable. Every `delete` disposition below means delete only after provider equivalence, ABI/reference census, dual-run proof, and a proven rollback route.

## Material findings

1. **The generic launcher does not launch anything.** `run_with_resolved_manifests` performs preflight and
   writes a `COMMIT` log, then returns success without constructing a process specification or spawning a
   process (`tools/package/launcher/launcher_cli.py:1498-1542`). The active native process API is a hard stub
   returning `-1` (`apps/launcher/lifecycle/launcher_process_stub.c:8-40`). Existing launcher tests cover
   refusal/preflight but no successful supervised process (`tests/launcher/launcher_cli_tests.py:539-580`).

2. **Current setup transaction behavior is not sufficient as the universal contract.**

   - Failed uninstall can move an embedded data root out of the install and return “ROLLBACK” without restoring it (`tools/package/setup/setup_cli.py:1711-1722`).
   - Successful uninstall deletes the install-scoped log and writes no terminal record to the data-root log
     allowed by doctrine (`tools/package/setup/setup_cli.py:1724-1735`; doctrine at
     `docs/architecture/SETUP_TRANSACTION_MODEL.md:33-40`).
   - Repair writes `ROLLBACK` before deleting the log-bearing root and restoring the earlier backup, losing the rollback entry (`tools/package/setup/setup_cli.py:1674-1684`).
   - Update mutates managed paths in place (`tools/package/setup/setup_cli.py:2522-2547`) and has no PLAN/STAGE/COMMIT operation journal.
   - Install’s copy fallback can expose a partial final root if `copytree` fails after `os.replace` fails (`tools/package/setup/setup_cli.py:1537-1541`).
   - A failed install can leave packs copied into a pre-existing data root (`tools/package/setup/setup_cli.py:1525-1535,1571-1579`).

3. **Content-store publication and GC are non-transactional.** Artifact writers create the final hash directory
   before payload and manifest completion, while duplicate detection trusts any existing directory
   (`tools/package/libraries/store/content_store.py:241-264,282-302`). Safe/aggressive GC can mutate earlier
   candidates before refusing or failing on a later candidate (`runtime/storage/gc_engine.py:288-323`).

4. **Several linked native launcher surfaces are placeholders.** Core, config, profile, mods, and process
   implementations are compiled into `launcher_core` (`apps/launcher/CMakeLists.txt:3-24`) but are unused by the
   actual CLI and are stubs.

5. **Duplicate Win32 shadows exist.** Active CMake selects the non-nested files
   (`apps/setup/CMakeLists.txt:38-50`, `apps/launcher/CMakeLists.txt:41-52`); parallel
   `runtime/platform/win32/{setup,launcher}/win32/**` files are unbuilt and sometimes divergent. They require
   quarantine, not immediate deletion.

6. **A strong legacy setup characterization corpus exists but is dormant.**
   `tests/game/tests/setup/CMakeLists.txt` points at nonexistent `source/dominium/setup/**`; that subtree is not
   included by active `tests/CMakeLists.txt`. Its crash, resume, deterministic-journal, and rollback cases
   should be ported as provider tests, not treated as current proof.

## Consumer capability matrix

| Capability | Dominium requirement | Current state | Permanent owner | Dominium-owned remainder |
|---|---:|---|---|---|
| Package authoring | Yes | Implemented through build/release tooling | Development tooling + USK format | Product recipes, component selection, release metadata |
| Package verification | Yes | Implemented | USK | Trust roots and product compatibility policy |
| Install | Yes | Implemented with atomicity gaps | USK | Product payload recipe and presentation |
| Repair | Yes | Implemented in-place with backup/log gaps | USK | Product repair policy inputs |
| Uninstall | Yes | Implemented with rollback/terminal-log defect | USK | Confirmation and data-retention presentation |
| Update | Yes | Resolver and apply path implemented; active characterization absent | USK | Channels, support window, release selection policy |
| Rollback/recovery | Yes | Backup rollback exists; crash recovery incomplete | USK | Product downgrade/support policy |
| Installed-state registry | Yes | Implemented | USK | Registry location preference only |
| Install/product/instance refs | Yes | Implemented across install library and launcher | ULK | Product compatibility interpretation |
| Profiles and instances | Yes | Implemented in Python; native API stubbed | ULK | Dominium profile definitions/defaults |
| Content store | Yes | Implemented; publication is not atomic | USK | Product content and authored pack inputs |
| Store reachability/GC | Yes | Implemented; multi-item mutation is not transactional | USK | Product retention policy selection |
| Preflight | Yes | Substantial implementation and refusal coverage | ULK | Dominium readiness rules |
| Launch-plan/staleness | Yes | No explicit durable launch plan or staleness model | ULK | Product plan adapter |
| Process supervision | Yes | Native hard stubs; Python generic run does not spawn | ULK | Product executable/process-spec translation |
| Launch sessions/journals | Yes | A launcher log exists; no attempt/session lifecycle | ULK | Product session metadata |
| CLI/TUI/GUI | Yes | Active product façades, some GUI/TUI placeholders | Product | Entire branded/presentational layer |
| Entitlement/authority mapping | Yes | Implemented and tested separately | Product | Entire policy |
| Legacy OS packaging | Yes | Packaging scripts and Win32 shells exist | Product + development tooling | Supported-platform decisions |

## Function-level row set

Expansion rule: each `symbol@line` in a row is an individual machine row inheriting all other fields.

Codes:

```toml
owner.P = "product_policy_presentation"
owner.U = "usk_setup_lifecycle"
owner.L = "ulk_launcher_lifecycle"
owner.D = "development_tooling"
owner.X = "legacy_compat_retire"

rollback.R1 = "disable universal provider and route facade to frozen local Python implementation"
rollback.R2 = "pin prior USK/ULK package and retain dual-readable state/journal format"
rollback.R3 = "relink prior native target/API shim"
rollback.R4 = "restore quarantined file from exact audited commit"
rollback.R0 = "not applicable; implementation remains in Dominium"

migration_dependency.D1 = "USK product-package, setup-recipe, installed-state, journal and lifecycle contracts plus a consumable SDK"
migration_dependency.D2 = "ULK composition, reference, client, result and journal contracts plus a consumable SDK"
migration_dependency.D3 = "Dominium product recipe, release policy and compatibility inputs separated from neutral provider behavior"
migration_dependency.D4 = "exact build, import, ABI and reference census with audited source retained in quarantine"
migration_dependency.D7 = "ULK launch-plan, process, containment, bounded-I/O and session backend"
migration_dependency.D8 = "atomic persistence, durable recovery, dual-readable state and crash/fault-injection proof"
migration_dependency.D9 = "thin Dominium product adapter and CLI/TUI/GUI compatibility facade"
migration_dependency.D10 = "neutral artifact-set, content-store locator and governed-reference contracts"
migration_dependency.D11 = "USK authenticity, release-index, update/downgrade and rollback policy contracts"
```

```text
id|file|symbols|current_responsibility|owner|disposition|tests|dependency|rollback
S01
  files:
    tools/package/setup/setup_cli.py
  symbols:
    _emit_setup_event@128
    now_timestamp@137
    normalize_path@143
    safe_rel@149
    ensure_dir@160
    write_json@166
    load_json@173
    canonical_bytes@178
    digest64@182
    refusal_payload@188
    build_compat_report@199
    parse_deterministic@274
    derive_artifact_root@287
    payload_root_from_artifact@300
    normalize_invocation_path@306
    build_invocation@413
    load_invocation@434
    make_plan@439
    ensure_file@465
    copy_tree@471
    sync_tree@485
    sync_tree._sha256@486
    detect_network_status@515
    _store_root_ref_payload@546
  responsibility: generic setup normalization, planning, filesystem, refusal and deterministic helpers
  permanent_owner: U
  disposition: move
  tests:
    U01
    U02
    U15
  dependencies:
    D1
    D4
  rollback: R1
S02
  files:
    tools/package/setup/setup_cli.py
  symbols:
    ops_log_path@237
    append_ops_log@241
    SetupTransaction@247
    SetupTransaction.__init__@248
    SetupTransaction.log@254
    setup_state_payload@708
    read_setup_state@723
    latest_backup@733
    append_backup@746
    backup_install_root@758
    transaction_log_path@783
    _managed_paths_from_rows@887
    _remove_managed_paths@894
    _copy_managed_paths@903
    _merge_install_manifest_for_update@924
  responsibility: installed state, operation journal, backup and managed-tree mutation
  permanent_owner: U
  disposition: adapt
  tests:
    U03
    U04
    U05
    U06
    U08
    U09
    U15
  dependencies:
    D1
    D4
    D8
  rollback: R1
S03
  files:
    tools/package/setup/setup_cli.py
  symbols:
    resolve_ops_cli@312
    resolve_share_cli@316
    resolve_plan_migration_cli@320
    resolve_apply_migration_cli@324
    resolve_import_engine_module@328
    _setup_vpath_context@332
    resolve_pack_root@368
    run_script@399
    _semantic_contract_registry_payload@537
    _semantic_contract_registry_hash@542
    _install_version_for_products@561
    _descriptor_sidecar_path@575
    _discover_install_products@580
  responsibility: Dominium tool routing, virtual paths, product descriptors, registry and pack recipe
  permanent_owner: P
  disposition: adapt
  tests:
    P01
    P02
  dependencies:
    D3
    D9
    D10
  rollback: R0
S04
  files:
    tools/package/setup/setup_cli.py
  symbols:
    install_manifest_payload@616
  responsibility: mixed generic installed-state manifest assembly and Dominium product discovery
  permanent_owner: U
  disposition: adapt
  tests:
    U01
    P01
    X02
  dependencies:
    D1
    D3
  rollback: R1
S05
  files:
    tools/package/setup/setup_cli.py
  symbols:
    _update_refusal@787
    _trust_root_local_registry_path@792
    _load_effective_trust_policy@796
    _load_imported_trust_root_rows@817
    _load_install_profile_for_root@871
    _load_release_resolution_policy_for_root@879
  responsibility: generic trust, install profile and update-policy loading
  permanent_owner: U
  disposition: move
  tests:
    U07
    U10
    U11
  dependencies:
    D1
    D11
  rollback: R1
S06
  files:
    tools/package/setup/setup_cli.py
  symbols:
    write_output@951
    output_refusal@959
    output_error@978
    output_ok@985
    bridge_engine_payload@991
  responsibility: Dominium CLI response presentation and compatibility bridge
  permanent_owner: P
  disposition: retain
  tests:
    P02
    L10
  dependencies:
    D9
  rollback: R0
S07
  files:
    tools/package/setup/setup_cli.py
  symbols:
    _compat_root@1018
    _verify_pack_root@1023
    _write_verification_outputs@1046
    handle_verify@1066
    handle_list_packs@1189
    handle_build_lock@1227
    handle_diagnose_pack@1281
  responsibility: package verification, lock creation and diagnostics
  permanent_owner: U
  disposition: move
  tests:
    U10
    U11
    U16
  dependencies:
    D1
    D3
    D10
  rollback: R1
S08
  files:
    tools/package/setup/setup_cli.py
  symbols:
    handle_export_invocation@1335
    handle_plan@1355
    install_from_plan@1398
    repair_from_plan@1583
    uninstall_from_plan@1687
    rollback_from_plan@1738
    handle_apply@1813
    handle_install_registry@1891
    handle_install_registry._plan_targets@1916
    handle_install_registry._plan_source_root@1939
    handle_install_registry._build_component_plan@1944
    handle_install_registry._plan_storage_root@1963
    handle_update@2246
    handle_trust@2614
    handle_pack@3043
    handle_install@3069
    handle_repair@3088
    handle_uninstall@3102
    handle_rollback@3114
    handle_store@3135
  responsibility: generic setup lifecycle command implementation
  permanent_owner: U
  disposition: adapt
  tests:
    U02
    U03
    U04
    U05
    U06
    U07
    U08
    U09
    U10
    U11
    U14
    U15
    U16
  dependencies:
    D1
    D3
    D4
    D8
    D11
  rollback: R1
S09
  files:
    tools/package/setup/setup_cli.py
  symbols:
    resolve_instance_manifest_path@348
    _discover_install_context@855
    handle_detect@1853
    handle_manifest_validate@1871
    handle_instance@2776
    handle_migrate_instance@3016
  responsibility: install/instance reference resolution and compatibility command forwarding
  permanent_owner: L
  disposition: adapt
  tests:
    L01
    L02
    L03
    L10
  dependencies:
    D2
    D9
  rollback: R1
S10
  files:
    tools/package/setup/setup_cli.py
  symbols:
    _governance_status_payload@828
    handle_governance@2752
    handle_save@2946
    handle_migrate_save@2985
    _legacy_main@3249
    main@3702
    main.appshell_product_bootstrap@3707
  responsibility: product governance/save commands and setup application entrypoint
  permanent_owner: P
  disposition: retain
  tests:
    P01
    P02
    P05
  dependencies:
    D2
    D3
    D9
  rollback: R0

I01
  files:
    tools/package/libraries/install/install_validator.py
  symbols:
    _as_map@39
    _as_list@43
    _norm@47
    _read_json@51
    _normalize_value@61
    write_json@76
    deterministic_fingerprint@85
    sha256_file@93
    stable_install_id@103
    _semver_tuple@107
    _semver_min@121
    _semver_max@129
    _stable_relpath@137
    _effective_install_root@145
    normalize_protocol_range@161
    normalize_contract_range@177
    merge_protocol_ranges@195
    merge_contract_ranges@211
    build_product_build_descriptor@229
    collect_manifest_product_descriptors@257
    normalize_install_manifest@296
    _manifest_required_fields@326
    _registry_path_from_manifest@354
    _run_descriptor_command@362
    compare_required_product_builds@391
    compare_required_contract_ranges@420
    validate_install_manifest@468
    evaluate_install_manifest_load@578
  responsibility: product/install reference normalization and validation
  permanent_owner: L
  disposition: move
  tests:
    U01
    L01
    L04
  dependencies:
    D2
    D3
  rollback: R1
I02
  files:
    tools/package/libraries/install/install_validator.py
  symbols:
    default_install_registry_path@620
    _empty_install_registry@639
    load_install_registry@651
    save_install_registry@681
    build_install_registry_entry@703
    registry_add_install@721
    registry_remove_install@771
    verify_install_registry@788
  responsibility: installed-state registry persistence
  permanent_owner: U
  disposition: move
  tests:
    U09
    U15
  dependencies:
    D1
    D8
  rollback: R1
I03
  files:
    runtime/package/install_discovery_engine.py
  symbols:
    _token@20
    _norm@24
    _norm_rel@28
    _as_map@32
    _normalize_tree@36
    _fingerprint@51
    _value_after@57
    _resolve_path@69
    _read_json@78
    _load_install_manifest@89
    _platform_family@99
    install_registry_candidate_paths@114
    load_runtime_install_registry@169
    _cli_install_root@222
    _env_install_root@229
    _cli_install_id@236
    _env_install_id@243
    _registry_rows_by_candidate@250
    _entry_matches_executable@261
    _build_refusal@271
    _complete_payload@308
    discover_install@346
  responsibility: neutral install-reference discovery and precedence
  permanent_owner: L
  disposition: move
  tests:
    L01
    L02
  dependencies:
    D2
  rollback: R1

R01
  files:
    tools/release/update_resolver.py
  symbols:
    _token@62
    _norm@66
    _norm_rel@70
    _as_map@74
    _as_list@78
    _sorted_unique_strings@82
    _normalize_tree@86
    _canonical_release_resolution_policy_id@101
    _stable_bool@106
    canonicalize_release_resolution_policy@113
    _builtin_release_resolution_policy_rows@126
    load_release_resolution_policy_registry@165
    select_release_resolution_policy@169
    _descriptor_artifact_id@195
    _semver_key@207
    _component_descriptor_sort_key@235
    _write_json@247
    _read_json@256
    _platform_matrix_row@265
    _signature_row@279
    _update_component_row@293
    _verification_step_row@311
    canonicalize_release_index@326
    _release_index_signing_payload@383
    canonicalize_update_plan@391
    load_release_index@443
    write_release_index@447
    infer_release_index_path@451
    release_index_hash@459
    release_index_signed_hash@463
    component_managed_paths@467
    resolve_release_index_platform_entry@507
    resolve_release_artifact_root@540
    load_install_transaction_log@548
    append_install_transaction@579
    select_rollback_transaction@604
    _normalize_current_component_rows@623
    _protocol_overlap@660
    _descriptor_upgrade_row@674
    _descriptor_add_row@692
    _descriptor_remove_row@709
    _verification_steps@725
    _descriptor_matches_target@783
    _descriptor_matches_trust_policy@816
    _select_exact_candidate@826
    _candidate_rank_key@850
    _selected_component_set_hash@861
    _resolve_release_component_candidates@869
    resolve_update_plan@1016
  responsibility: generic release-index, update-plan and rollback-transaction resolution
  permanent_owner: U
  disposition: move
  tests:
    U07
    U08
    U09
  dependencies:
    D1
    D11
  rollback: R1
R02
  files:
    tools/release/component_graph_resolver.py
  symbols:
    _token@49
    _norm@53
    _as_map@57
    _as_list@61
    _sorted_unique_strings@65
    _normalize_tree@69
    deterministic_fingerprint@84
    _normalize_filters@90
    canonicalize_component_descriptor@106
    canonicalize_component_edge@131
    canonicalize_component_graph@145
    canonicalize_install_plan@179
    _canonical_install_profile_id@218
    canonicalize_install_profile@223
    _read_json@238
    load_component_graph_registry@247
    load_install_profile_registry@251
    select_component_graph@255
    load_default_component_graph@287
    select_install_profile@296
    _matches_filters@322
    _provider_declarations_for_component@363
    _candidate_components_for_selector@385
    _sorted_reason_rows@409
    _sorted_optional_rows@417
    _verification_steps@434
    resolve_component_graph@448
    build_default_component_install_plan@682
    platform_targets_for_tag@823
  responsibility: generic component/install-plan resolution
  permanent_owner: U
  disposition: move
  tests:
    U02
    U07
  dependencies:
    D1
    D3
  rollback: R1
R03
  files:
    tools/release/component_graph_resolver.py
  symbols:
    validate_instance_against_install_plan@762
  responsibility: instance-to-install-plan validation
  permanent_owner: L
  disposition: move
  tests:
    L01
    L04
  dependencies:
    D2
  rollback: R1
R04
  files:
    tools/release/release_manifest_engine.py
  symbols:
    _token@58
    _as_map@62
    _as_list@66
    _norm_rel@70
    _read_json@74
    _sha256_file@94
    _descriptor_build_id_cross_check@574
    cross_check_release_manifest_build_ids@614
    load_signature_blocks@678
    verify_signature_blocks@688
    infer_dist_root_from_manifest_path@708
    load_release_manifest@863
    verify_release_manifest@870
  responsibility: generic release-manifest loading and verification
  permanent_owner: U
  disposition: move
  tests:
    U10
    U11
  dependencies:
    D1
    D11
  rollback: R1
R05
  files:
    tools/release/release_manifest_engine.py
  symbols:
    _write_canonical_json@85
    _directory_tree_hash@104
    _semver_without_build@117
    _artifact_entry@124
    _signature_entry@148
    build_mock_signature_block@168
    _normalized_signature_rows@190
    _manifest_hash_payload@217
    _manifest_fingerprint_payload@226
    _descriptor_json@234
    _descriptor_sidecar_path@249
    _load_descriptor_sidecar@255
    _looks_like_python_script@265
    _run_descriptor@275
    _pack_compat_hash_for_dir@312
    _pack_metadata_for_dir@332
    _binary_entry@355
    _auxiliary_binary_entry@386
    _binary_paths@399
    _binary_paths.normalize@416
    _pack_dirs@420
    _simple_file_entries@434
    _bundle_entries@455
    _manifest_entries@479
    _dist_manifest_payload@514
    _release_semver@521
    _semantic_contract_registry_hash@539
    _optional_hash@567
    _install_manifest_for_root@698
    build_release_manifest@718
    write_release_manifest@852
  responsibility: Dominium release authoring and projection tooling
  permanent_owner: D
  disposition: retain
  tests:
    D01
    P01
    P05
  dependencies:
    D3
    D11
  rollback: R0
R06
  files:
    tools/release/component_graph_common.py
  symbols:
    _token@47
    _norm@51
    _norm_rel@55
    _equivalent_rel@59
    _equivalent_abs@63
    _as_map@67
    _read_json@71
    _write_json@80
    _write_text@89
    _sha256_file@97
    _release_component_hash@108
    _stability@112
    _pack_lock@127
    _profile_bundle@131
    _pack_descriptor_rows@135
    _component_rows@159
    _edge_rows@190
    build_component_graph_registry_payload@226
    build_arch_registry_payload@265
    build_os_registry_payload@284
    build_component_graph_report@303
    render_component_graph_baseline@337
    write_component_graph_outputs@385
    component_graph_violations@397
  responsibility: component graph generator, report and baseline tooling
  permanent_owner: D
  disposition: retain
  tests:
    D01
  dependencies:
    D3
  rollback: R0
R07
  files:
    tools/release/install_profile_common.py
  symbols:
    _token@35
    _norm@39
    _norm_rel@43
    _equivalent_rel@47
    _equivalent_abs@51
    _as_map@55
    _write_json@59
    _write_text@68
    _stability@76
    _profile_rows@91
    build_install_profile_registry_payload@217
    build_install_profile_report@230
    render_install_profile_baseline@270
    write_install_profile_outputs@313
    install_profile_violations@324
  responsibility: install-profile authoring and baseline tooling
  permanent_owner: D
  disposition: retain
  tests:
    D01
  dependencies:
    D3
  rollback: R0
R08
  files:
    tools/release/release_index_policy_common.py
  symbols:
    _token@47
    _norm@51
    _norm_rel@55
    _as_map@59
    _write_json@63
    _write_text@72
    _stability@80
    _policy_row@102
    build_release_resolution_policy_registry_payload@119
    _bundle_root@176
    _load_install_manifest@197
    _base_release_index@202
    _descriptor_variant@213
    _fixture_release_index@231
    _resolve_fixture@274
    build_release_index_policy_fixture_cases@296
    _git_tags@329
    _changelog_files@344
    _rollback_fields_roundtrip@358
    _selected_descriptor@386
    _fixture_summary@394
    build_release_index_policy_report@446
    render_release_index_policy_baseline@520
    write_release_index_policy_outputs@579
    release_index_policy_violations@594
  responsibility: product release-policy fixtures, projection and reports
  permanent_owner: D
  disposition: retain
  tests:
    D01
    P05
  dependencies:
    D11
  rollback: R0
R09
  files:
    tools/release/release_manifest_common.py
  symbols:
    _token@29
    _as_map@33
    _required_file_violations@37
    build_release_manifest_report@59
    release_manifest_violations@192
  responsibility: release validation report tooling
  permanent_owner: D
  disposition: retain
  tests:
    D01
  dependencies:
    D11
  rollback: R0
R10
  files:
    tools/release/update_model_common.py
  symbols:
    _token@50
    _norm@54
    _norm_rel@58
    _equivalent_rel@62
    _equivalent_abs@66
    _as_map@70
    _as_list@74
    _read_json@78
    _write_json@87
    _write_text@96
    _sha256_file@104
    _bundle_root@114
    _existing_bundle_root@118
    _install_manifest@130
    _platform_os_id@134
    _release_artifact_map@146
    _actualize_graph_components@155
    build_release_index_payload@280
    build_update_model_report@365
    render_update_model_baseline@412
    write_update_model_outputs@459
    update_model_violations@471
  responsibility: Dominium update-model authoring and evidence generation
  permanent_owner: D
  disposition: retain
  tests:
    D01
    U07
  dependencies:
    D3
    D11
  rollback: R0
R11
  files:
    tools/release/__init__.py
  symbols:
    __getattr__@78
    __dir__@89
  responsibility: lazy compatibility export facade spanning product, USK and ULK APIs
  permanent_owner: U
  disposition: adapt
  tests:
    X01
    L10
  dependencies:
    D1
    D2
    D9
  rollback: R1

C01
  files:
    tools/package/libraries/store/content_store.py
  symbols:
    _ensure_dir@56
    _normalize_slashes@61
    _normalize_value@68
    canonical_json_text@83
    canonical_sha256@92
    deterministic_fingerprint@96
    pretty_write_json@102
    load_json@109
    copy_dir@114
    sha256_file@120
    _tree_entries@128
    _tree_descriptor@146
    _store_root_manifest_payload@150
    initialize_store_root@161
    load_store_root_manifest@186
    _category_token@193
    store_artifact_root@202
    embedded_artifact_root@206
    artifact_payload_path@210
    _artifact_manifest_payload@216
    store_get_artifact@355
    _verify_json_artifact@374
    _verify_tree_artifact@379
    store_verify@385
    load_artifact_manifest@406
    index_file_tree@631
  responsibility: content-addressed store identity, layout, reads and verification
  permanent_owner: U
  disposition: move
  tests:
    U12
    U13
  dependencies:
    D1
    D10
  rollback: R1
C02
  files:
    tools/package/libraries/store/content_store.py
  symbols:
    _write_json_artifact@241
    _copy_tree@273
    _write_tree_artifact@282
    store_add_artifact@311
    store_add_tree_artifact@327
    embed_json_artifact@334
    embed_tree_artifact@349
  responsibility: artifact publication and embedding
  permanent_owner: U
  disposition: adapt
  tests:
    U12
    U16
  dependencies:
    D1
    D8
  rollback: R1
C03
  files:
    tools/package/libraries/store/content_store.py
  symbols:
    manifest_ref_path@413
    resolve_locator_path@421
    build_pack_lock_payload@437
    build_profile_bundle_payload@515
    build_store_locator@548
    build_install_ref@556
    resolve_instance_artifact_root@571
    load_instance_json_artifact@588
    load_instance_artifact_manifest@601
    artifact_ref@611
  responsibility: artifact/install/profile/instance reference contracts
  permanent_owner: L
  disposition: move
  tests:
    L01
    L04
  dependencies:
    D2
    D10
  rollback: R1
C04
  files:
    tools/package/libraries/store/reachability_engine.py
  symbols:
    _token@42
    _norm@46
    _norm_rel@50
    _layout_path@54
    _rel_from@63
    _as_map@76
    _as_list@80
    _read_json@84
    _sha256_file@93
    _tree_entries@101
    _tree_artifact_hash@119
    _json_artifact_hash@123
    _is_sha256_token@128
    store_artifact_token@133
    parse_artifact_token@137
    _artifact_root@145
    _artifact_root_exists@149
    scan_store_artifacts@153
    _quarantined_tokens@176
    _resolve_locator@192
    _store_root_from_install_manifest_path@204
    _install_source_row@210
    _discover_install_sources@223
    _sorted_manifest_paths@262
    _artifact_tokens_from_lock_payload@274
    _artifact_token_from_direct_store_path@286
    _artifact_tokens_from_install_manifest@308
    _artifact_tokens_from_instance_manifest@328
    _artifact_tokens_from_save_manifest@356
    _artifact_tokens_from_release_manifest@364
    _artifact_tokens_from_release_index@378
    _artifact_tokens_from_bundle_manifest@398
    _manifest_source_rows@413
    _load_lock_payload@487
    build_store_reachability_report@495
  responsibility: governed manifest reachability graph
  permanent_owner: U
  disposition: move
  tests:
    U13
    U14
  dependencies:
    D1
    D10
  rollback: R1
C05
  files:
    runtime/storage/gc_engine.py
  symbols:
    deterministic_fingerprint@50
    canonicalize_gc_policy@56
    canonicalize_gc_report@69
    load_gc_policy_registry@84
    select_gc_policy@101
    resolve_store_root_from_install@109
    _portable_mode_for_store@122
    _manifest_error@135
    _quarantined_tokens@140
    verify_store_root@155
  responsibility: store verification and GC policy selection
  permanent_owner: U
  disposition: move
  tests:
    U12
    U14
  dependencies:
    D1
  rollback: R1
C06
  files:
    runtime/storage/gc_engine.py
  symbols:
    _quarantine_root@222
    run_store_gc@226
  responsibility: mutating quarantine/deletion GC execution
  permanent_owner: U
  disposition: adapt
  tests:
    U14
    U15
  dependencies:
    D1
    D8
  rollback: R1
C07
  files:
    tools/package/libraries/store/store_gc_common.py
  symbols:
    _token@62
    _norm@66
    _norm_rel@70
    _as_map@74
    _as_list@78
    _write_json@82
    _write_text@91
    _read_text@99
    _stability_payload@107
    _gc_policy_row@129
    build_gc_policy_registry@152
    write_gc_policy_registry@185
    _simple_artifact_payload@190
    _store_path_rel@203
    build_store_gc_fixture@211
    build_store_verify_report@495
    build_store_gc_report@527
    render_store_verify_report@663
    render_store_gc_baseline@695
    write_store_verify_outputs@753
    write_store_gc_outputs@776
    store_gc_violations@793
  responsibility: fixture, baseline and report generation
  permanent_owner: D
  disposition: retain
  tests:
    D01
    U14
  dependencies:
    D1
  rollback: R0
C08
  files:
    tools/package/libraries/store/tool_run_store_gc.py
    tools/package/libraries/store/tool_store_verify.py
  symbols:
    main@30
    main@30
  responsibility: developer baseline/report CLIs
  permanent_owner: D
  disposition: retain
  tests:
    D01
  dependencies:
    none
  rollback: R0

L01
  files:
    tools/package/launcher/launcher_cli.py
  symbols:
    now_timestamp@83
    ensure_dir@89
    load_json@95
    write_json@100
    normalize_path@107
    _active_vpath_context@113
    safe_rel@122
    resolve_install_root@132
    resolve_install_manifest_from_instance@141
    sorted_unique@157
    install_product_builds@163
    instance_required_product_builds@172
    instance_required_contract_ranges@181
    refusal_payload@190
    build_compat_report@201
    log_path@240
    append_log@244
    resolve_repo_root@253
    resolve_ops_cli@257
    resolve_share_cli@261
    run_script@265
    list_install_manifests@279
    normalize_install_entry@321
    list_instance_manifests@347
    normalize_instance_entry@382
    discover_profiles@400
    profile_recommendations@449
    resolve_state_root@460
    load_state@472
    write_state@484
    resolve_data_root@491
    resolve_lockfile@499
    resolve_pack_lock@507
    resolve_profile_bundle@517
    resolve_pack_payloads@525
    _copy_tree_deterministic@541
    preview_verified_pack_set@552
    _provider_resolution_projection@607
    load_lockfile@629
    collect_required_capabilities@638
    collect_required_packs@651
    pack_roots@672
    pack_location@688
    pack_source_for_root@698
    build_pack_status@711
    perform_preflight@739
    resolve_instance_selection@1435
    resolve_requested_save_id@1466
    resolve_install_selection@1485
  responsibility: neutral refs, discovery, profiles, preferences, preflight and client behavior
  permanent_owner: L
  disposition: move
  tests:
    L01
    L02
    L03
    L04
    L10
  dependencies:
    D2
    D8
    D10
  rollback: R1
L02
  files:
    tools/package/launcher/launcher_cli.py
  symbols:
    run_with_resolved_manifests@1498
    run_launcher_action@1545
    main@1560
  responsibility: nominal launch operation, terminal logging and neutral CLI entrypoint
  permanent_owner: L
  disposition: adapt
  tests:
    L05
    L06
    L07
    L08
    L09
    L10
    L11
  dependencies:
    D2
    D7
    D8
    D9
  rollback: R1
L03
  files:
    tools/package/launcher/launch.py
  symbols:
    _norm@48
    _repo_root@52
    _launcher_defaults@58
    _verify_pack_root_via_appshell@84
    _refusal@90
    _read_json@114
    _find_dist_roots@124
    _default_dist_root@136
    _list_saves@151
    _load_latest_run_meta@172
    _validate_session_vs_dist@196
    cmd_list_builds@300
    cmd_list_saves@319
    cmd_instances_list@326
    cmd_install_status@359
    cmd_run@445
    cmd_compat_status@592
    cmd_create_session@746
    _legacy_main@788
    appshell_product_bootstrap@911
    _normalize_ux_args@917
    main@926
  responsibility: Dominium-specific defaults, compatibility, session creation and launch interpretation
  permanent_owner: P
  disposition: adapt
  tests:
    P01
    P03
    P05
    L05
    L10
  dependencies:
    D2
    D3
    D9
  rollback: R0
D01
  files:
    tools/package/setup/build.py
  symbols:
    _repo_root@30
    _as_text@36
    _forbidden_pipeline_tokens@50
    main@62
  responsibility: Dominium distribution build command
  permanent_owner: D
  disposition: retain
  tests:
    D01
    P01
  dependencies:
    D3
  rollback: R0
```

### Native implementation rows

```text
N01
  files:
    apps/setup/cli/setup_cli_main.c
  symbols:
    dom_app_ui_request_init@163
    dom_app_ui_mode_name@172
    dom_app_ui_parse_value@185
    dom_app_parse_ui_arg@217
    dom_app_ui_mode_from_env@274
    dom_app_select_ui_mode@287
    print_version@301
    setup_default_sku_for_product@306
    setup_build_sku_value@329
    print_build_info@338
    control_is_ascii_space@394
    control_trim@399
    control_is_valid_key@424
    control_sort_keys@443
    control_free_caps@457
    control_caps_init@475
    control_caps_enable_key@555
    control_caps_is_enabled@573
    print_control_caps@581
    enable_control_list@597
    setup_print_help@626
    setup_is_abs_path@659
    setup_file_exists@674
    setup_get_cwd@688
    setup_normalize_path@697
    setup_pop_dir@710
    setup_join_search_path@746
    setup_find_upward@762
    setup_resolve_control_registry@786
    setup_append_quoted@811
    setup_resolve_ops_script@849
    setup_run_ops@864
    setup_resolve_share_script@899
    setup_run_share@914
    setup_args_has_prefix@949
    setup_resolve_setup_script@965
    setup_run_setup_cli@984
    setup_path_sep@1029
    setup_mkdir@1038
    setup_join_path@1058
    setup_prepare@1082
    setup_run_tui@1110
    setup_run_gui@1115
    setup_main@1120
    main@1451
  responsibility: native product CLI/UI and Python bridge
  permanent_owner: P
  disposition: adapt
  tests:
    P02
    L10
  dependencies:
    D1
    D9
  rollback: R3
N02
  files:
    apps/setup/lifecycle/dsk_setup_core.c
  symbols:
    dsk_setup_version@7
    dsk_setup_status@12
  responsibility: product setup facade status ABI
  permanent_owner: P
  disposition: retain
  tests:
    P02
  dependencies:
    D9
  rollback: R0
N03
  files:
    apps/setup/tui/dsu_tui_stub.c
  symbols:
    dsu_normalize_path@10
    dsu_file_exists@23
    dsu_append_quoted@37
    dsu_dir_from_argv0@75
    dsu_resolve_setup_script@102
    dsu_run_setup_cli@127
    dsu_tui_run@163
    main@168
  responsibility: product TUI adapter
  permanent_owner: P
  disposition: adapt
  tests:
    P02
    L10
  dependencies:
    D1
    D9
  rollback: R3
N04
  files:
    runtime/platform/win32/setup/dsu_gui_stub.c
  symbols:
    dsu_normalize_path@10
    dsu_file_exists@23
    dsu_append_quoted@37
    dsu_dir_from_argv0@75
    dsu_resolve_setup_script@102
    dsu_run_setup_cli@127
    dsu_gui_run@163
    main@168
  responsibility: active setup GUI adapter
  permanent_owner: P
  disposition: adapt
  tests:
    P02
    P06
  dependencies:
    D1
    D9
  rollback: R3
N05
  files:
    runtime/platform/win32/setup/setup_app_win32.cpp
  symbols:
    wWinMain@11
    WinMain@31
  responsibility: active branded Win32 setup shell
  permanent_owner: P
  disposition: retain
  tests:
    P02
    P06
  dependencies:
    D9
  rollback: R0

N06
  files:
    apps/launcher/cli/launcher_cli_main.c
  symbols:
    print_version@36
    print_build_info@41
    print_control_caps@48
    enable_control_list@70
    launcher_print_help@99
    launcher_is_abs_path@149
    launcher_file_exists@164
    launcher_get_cwd@178
    launcher_normalize_path@187
    launcher_pop_dir@200
    launcher_join_path@236
    launcher_find_upward@252
    launcher_resolve_control_registry@276
    launcher_parse_ui_scale@301
    launcher_parse_palette@316
    launcher_parse_log_level@332
    launcher_append_quoted@352
    launcher_resolve_ops_script@390
    launcher_run_ops@405
    launcher_resolve_share_script@440
    launcher_run_share@455
    launcher_resolve_bugreport_script@490
    launcher_run_bugreport@505
    launcher_resolve_launcher_script@540
    launcher_run_launcher_cli@555
    launcher_apply_accessibility@590
    launcher_backend_name_for@626
    launcher_print_capabilities@639
    launcher_main@688
    main@1179
  responsibility: native branded launcher CLI and client bridge
  permanent_owner: P
  disposition: adapt
  tests:
    P02
    L10
  dependencies:
    D2
    D9
  rollback: R3
N07
  files:
    apps/launcher/cli/launcher_ui_shell.c
  symbols:
    launcher_ui_text@112
    launcher_ui_menu_text@120
    launcher_palette_name@130
    launcher_log_level_name@135
    launcher_parse_bool_text@145
    launcher_parse_log_level_text@165
    launcher_parse_u32_text@185
    launcher_settings_apply_kv@200
    launcher_ui_settings_init@283
    launcher_ui_settings_format_lines@307
    launcher_ui_execute_command@388
    launcher_renderer_list_init@537
    launcher_renderer_default@561
    launcher_settings_set_renderer@585
    launcher_env_or_default@603
    launcher_ui_collect_diagnostics_lines@612
    launcher_ui_collect_diagnostics@637
    launcher_ui_ends_with@646
    launcher_ui_file_exists@661
    launcher_split_roots@675
    launcher_count_manifest_recursive@708
    launcher_count_profiles@778
    launcher_count_pack_manifests@824
    launcher_ui_collect_loading@893
    launcher_ui_state_init@997
    launcher_ui_cycle_renderer@1029
    launcher_ui_apply_action@1048
    launcher_ui_action_from_token@1129
    launcher_gui_draw_text@1152
    launcher_gui_draw_menu@1166
    launcher_gui_render@1193
    launcher_ui_run_tui@1300
    launcher_ui_run_gui@1539
  responsibility: launcher presentation, accessibility, settings and diagnostics
  permanent_owner: P
  disposition: retain
  tests:
    P02
  dependencies:
    D2
    D9
  rollback: R0
N08
  files:
    apps/launcher/lifecycle/launcher_authority.c
  symbols:
    launcher_entitlements_clear@12
    launcher_entitlements_grant@20
    launcher_entitlements_has@28
    launcher_entitlements_can_issue@36
    launcher_authority_select_profile@53
    launcher_authority_default_profile@67
    launcher_authority_issue_token@84
  responsibility: Dominium authority and entitlement policy
  permanent_owner: P
  disposition: retain
  tests:
    P04
  dependencies:
    none
  rollback: R0
N09
  files:
    apps/launcher/lifecycle/launcher_config_stub.c
  symbols:
    launcher_config_load@8
    launcher_config_save@17
  responsibility: placeholder preference persistence
  permanent_owner: L
  disposition: delete
  tests:
    L03
    X04
  dependencies:
    D2
    D8
    D9
  rollback: R3
N10
  files:
    apps/launcher/lifecycle/launcher_core.c
  symbols:
    launcher_init@6
    launcher_run@12
    launcher_shutdown@17
  responsibility: placeholder launcher lifecycle
  permanent_owner: L
  disposition: delete
  tests:
    L09
    L10
    X04
  dependencies:
    D2
    D9
  rollback: R3
N11
  files:
    apps/launcher/lifecycle/launcher_mods_stub.c
  symbols:
    launcher_mods_scan@8
    launcher_mods_get@14
    launcher_mods_count@23
    launcher_mods_set_enabled@28
    launcher_mods_resolve_order@35
  responsibility: placeholder pack/mod preference API
  permanent_owner: L
  disposition: delete
  tests:
    L03
    L04
    X04
  dependencies:
    D2
    D10
  rollback: R3
N12
  files:
    apps/launcher/lifecycle/launcher_process_stub.c
  symbols:
    launcher_process_spawn@8
    launcher_process_poll@22
    launcher_process_kill@28
    launcher_process_read_stdout@34
  responsibility: placeholder process supervision API
  permanent_owner: L
  disposition: delete
  tests:
    L06
    L07
    L08
    L09
    X04
  dependencies:
    D2
    D7
    D8
  rollback: R3
N13
  files:
    apps/launcher/lifecycle/launcher_profile_stub.c
  symbols:
    launcher_profile_load_all@8
    launcher_profile_get@13
    launcher_profile_count@19
    launcher_profile_save@24
    launcher_profile_set_active@30
    launcher_profile_get_active@36
  responsibility: placeholder profile persistence API
  permanent_owner: L
  disposition: delete
  tests:
    L03
    X04
  dependencies:
    D2
    D8
  rollback: R3
N14
  files:
    apps/launcher/tui/launcher_tui_stub.c
  symbols:
    main@6
  responsibility: placeholder product TUI target
  permanent_owner: P
  disposition: adapt
  tests:
    P02
  dependencies:
    D2
    D9
  rollback: R3
N15
  files:
    runtime/platform/win32/launcher/launcher_gui_stub.c
  symbols:
    main@6
  responsibility: placeholder product GUI target
  permanent_owner: P
  disposition: adapt
  tests:
    P02
    P06
  dependencies:
    D2
    D9
  rollback: R3
N16
  files:
    runtime/platform/win32/launcher/launcher_app_win32.cpp
  symbols:
    wWinMain@11
    WinMain@31
  responsibility: active branded Win32 launcher shell
  permanent_owner: P
  disposition: retain
  tests:
    P02
    P06
  dependencies:
    D2
    D9
  rollback: R0

N17
  files:
    runtime/platform/win32/setup/win32/dsu_gui_stub.c
  symbols:
    dsu_normalize_path@10
    dsu_file_exists@23
    dsu_append_quoted@37
    dsu_dir_from_argv0@75
    dsu_resolve_setup_script@102
    dsu_run_setup_cli@127
    dsu_gui_run@163
    main@168
  responsibility: unbuilt divergent duplicate setup GUI
  permanent_owner: X
  disposition: delete
  tests:
    X04
  dependencies:
    D4
    D9
  rollback: R4
N18
  files:
    runtime/platform/win32/setup/win32/setup_app_win32.cpp
  symbols:
    wWinMain@11
  responsibility: unbuilt divergent duplicate setup Win32 shell
  permanent_owner: X
  disposition: delete
  tests:
    X04
  dependencies:
    D4
    D9
  rollback: R4
N19
  files:
    runtime/platform/win32/launcher/win32/launcher_gui_stub.c
  symbols:
    main@6
  responsibility: unbuilt byte-identical duplicate launcher GUI stub
  permanent_owner: X
  disposition: delete
  tests:
    X04
  dependencies:
    D4
    D9
  rollback: R4
N20
  files:
    runtime/platform/win32/launcher/win32/launcher_app_win32.cpp
  symbols:
    wWinMain@11
  responsibility: unbuilt divergent duplicate launcher Win32 shell
  permanent_owner: X
  disposition: delete
  tests:
    X04
  dependencies:
    D4
    D9
  rollback: R4
```

### Contract/header rows

```text
H01
  files:
    apps/setup/include/dsk/dsk_setup.h
  symbols:
    dsk_setup_version@11
    dsk_setup_status@12
  responsibility: product facade ABI
  permanent_owner: P
  disposition: retain
  tests:
    P02
  dependencies:
    D9
  rollback: R0
H02
  files:
    apps/setup/include/dsu/dsu_frontend.h
  symbols:
    dsu_gui_run@11
    dsu_tui_run@12
  responsibility: product frontend ABI
  permanent_owner: P
  disposition: adapt
  tests:
    P02
  dependencies:
    D9
  rollback: R3
H03
  files:
    apps/setup/include/dsu/_internal/dom_setup/dom_setup_plugin.h
  symbols:
    Dominium_GetSetupPlugin@64 plus hook vtable fields@25-53
  responsibility: generic setup hook shape with product callbacks
  permanent_owner: U
  disposition: adapt
  tests:
    U03
    X04
  dependencies:
    D1
    D9
  rollback: R3
H04
  files:
    apps/setup/include/dsu/_internal/dom_setup/dom_setup_config.h
  symbols:
    parse_setup_cli@58
    load_setup_config_file@68
    apply_cli_overrides@76
    resolve_setup_defaults@86
    run_install@96
    run_repair@106
    run_uninstall@116
    run_list@126
    run_info@136
  responsibility: unimplemented and unreferenced old setup API
  permanent_owner: X
  disposition: delete
  tests:
    X04
  dependencies:
    D4
    D9
  rollback: R4

H05
  files:
    apps/launcher/cli/launcher_ui_shell.h
  symbols:
    launcher_ui_settings_init@35
    launcher_ui_settings_format_lines@36
    launcher_ui_execute_command@43
    launcher_ui_run_tui@50
    launcher_ui_run_gui@55
  responsibility: product UI contract
  permanent_owner: P
  disposition: retain
  tests:
    P02
  dependencies:
    D9
  rollback: R0
H06
  files:
    apps/launcher/include/launcher/launcher_authority.h
  symbols:
    launcher_entitlements_clear@31
    launcher_entitlements_grant@32
    launcher_entitlements_has@33
    launcher_entitlements_can_issue@35
    launcher_authority_select_profile@36
    launcher_authority_default_profile@38
    launcher_authority_issue_token@41
  responsibility: product entitlement contract
  permanent_owner: P
  disposition: retain
  tests:
    P04
  dependencies:
    none
  rollback: R0
H07
  files:
    apps/launcher/include/launcher/launcher_config.h
    launcher_mods.h
    launcher_process.h
    launcher_profile.h
    launcher.h
  symbols:
    launcher_config_load@52
    launcher_config_save@65
    launcher_mods_scan@37
    launcher_mods_get@42
    launcher_mods_count@47
    launcher_mods_set_enabled@52
    launcher_mods_resolve_order@57
    launcher_process_spawn@38
    launcher_process_poll@43
    launcher_process_kill@48
    launcher_process_read_stdout@53
    launcher_profile_load_all@36
    launcher_profile_get@41
    launcher_profile_count@46
    launcher_profile_save@51
    launcher_profile_set_active@56
    launcher_profile_get_active@61
    launcher_init@30
    launcher_run@35
    launcher_shutdown@39
  responsibility: current public generic launcher ABI
  permanent_owner: L
  disposition: adapt
  tests:
    L03
    L06
    L07
    L08
    L09
    L10
    X04
  dependencies:
    D2
    D7
    D8
    D9
  rollback: R3
H08
  files:
    apps/launcher/include/launcher/launcher_ext.h
  symbols:
    launcher_ext_load_all@38
    launcher_ext_unload_all@42 plus vtable@26-32
  responsibility: generic launcher extension contract candidate
  permanent_owner: L
  disposition: adapt
  tests:
    L10
    X02
    X04
  dependencies:
    D2
    D9
  rollback: R3
H09
  files:
    apps/launcher/include/launcher/_internal/launcher_internal/**
  symbols:
    init_launcher_context@32
    get_launcher_context@37
    db_load@64
    db_save@68
    db_get_installs@74
    db_add_or_update_install@78
    db_get_profiles@84
    db_add_profile@88
    db_get_manual_paths@94
    db_add_manual_path@98
    db_set_plugin_kv@104
    db_get_plugin_kv@109
    discover_installs@26
    find_install_by_id@31
    find_install_by_root@36
    launcher_log_info@22
    launcher_log_warn@26
    launcher_log_error@30
    Dominium_GetLauncherPlugin@84
    launcher_plugins_load@24
    launcher_plugins_unload@28
    launcher_plugins_register_builtin@32
    launcher_plugins_list@36
    start_instance@59
    stop_instance@71
    get_instance@76
    list_instances@81
    query_runtime_capabilities@86
    launcher_run_cli@21
    launcher_run_gui@21
    launcher_run_tui@21
  responsibility: unimplemented generic design vocabulary for refs, persistence, clients and supervision
  permanent_owner: L
  disposition: adapt
  tests:
    L01
    L03
    L06
    L07
    L08
    L09
    L10
    X04
  dependencies:
    D2
    D7
    D8
    D9
  rollback: R3
H10
  files:
    apps/launcher/include/launcher/_internal/dom_launcher/**
  symbols:
    LauncherSettings@82
    db_load@103
    db_save@107
    init_launcher_context@33
    get_launcher_context@39
    discover_installs@27
    merge_discovered_installs@30
    get_state@58
    state_initialize@61
    state_save@64
    launcher_run_cli@27
    launcher_run_gui@28
    launcher_run_tui@28
  responsibility: unreferenced product-specific shadow model
  permanent_owner: X
  disposition: delete
  tests:
    X04
  dependencies:
    D3
    D4
    D9
  rollback: R4
H11
  files:
    apps/launcher/include/launcher/launcher_app.hpp
  symbols:
    LauncherApp@25
    ~LauncherApp@30
    run@36
    run_list_products@41
    run_run_game@46
    run_run_tool@51
    run_manifest_info@56
    run_tui@61
    run_gui@66
  responsibility: unimplemented old product app class
  permanent_owner: X
  disposition: delete
  tests:
    X04
  dependencies:
    D4
    D9
  rollback: R4
```

## File-level move/retain/delete map

```toml
[[file_map]]
source = "tools/package/setup/setup_cli.py"
action = "adapt"
destination = ["USK lifecycle modules", "ULK ref client", "thin Dominium setup adapter"]
note = "Never bulk-move; split S01-S10."

[[file_map]]
source = "tools/package/libraries/install/install_validator.py"
action = "move"
destination = ["ULK refs/validation", "USK installed-state registry"]

[[file_map]]
source = "runtime/package/install_discovery_engine.py"
action = "move"
destination = ["ULK install discovery"]

[[file_map]]
source = "tools/release/update_resolver.py"
action = "move"
destination = ["USK update and rollback resolution"]

[[file_map]]
source = "tools/release/component_graph_resolver.py"
action = "move"
destination = ["USK install planning", "ULK instance-plan validator"]

[[file_map]]
source = "tools/release/*_common.py"
action = "retain"
destination = ["Dominium development/release tooling"]
note = "Make these consumers of USK schemas; do not move product release authoring into USK."

[[file_map]]
source = "tools/package/libraries/store/content_store.py"
action = "adapt"
destination = ["USK store core", "ULK artifact-reference helpers"]

[[file_map]]
source = "tools/package/libraries/store/reachability_engine.py"
action = "move"
destination = ["USK reachability"]

[[file_map]]
source = "runtime/storage/gc_engine.py"
action = "adapt"
destination = ["USK transactional GC"]

[[file_map]]
source = "tools/package/launcher/launcher_cli.py"
action = "adapt"
destination = ["ULK neutral client/preflight/session implementation"]
note = "Current run success must not be preserved as a terminal launch success."

[[file_map]]
source = "tools/package/launcher/launch.py"
action = "retain"
destination = ["Dominium product launch adapter"]

[[file_map]]
source = "apps/setup/**"
action = "retain"
destination = ["Dominium product presentation"]
note = "Replace internal lifecycle calls with USK client contracts."

[[file_map]]
source = "apps/launcher/cli/**"
action = "retain"
destination = ["Dominium product presentation"]
note = "Replace internal lifecycle calls with ULK client contracts."

[[file_map]]
source = "apps/launcher/lifecycle/launcher_authority.c"
action = "retain"
destination = ["Dominium product policy"]

[[file_map]]
source = "apps/launcher/lifecycle/*_stub.c"
action = "delete"
after_equivalence = true
replacement = "ULK process/profile/preference/client implementation"

[[file_map]]
source = "runtime/platform/win32/{setup,launcher}/win32/**"
action = "delete"
after_equivalence = true
note = "Unbuilt duplicate shadows; preserve in quarantine until build/reference proof."

[[file_map]]
source = "release/updates/**"
action = "retain"
destination = ["Dominium release and support policy"]

[[file_map]]
source = "release/packaging/setup/scripts/**"
action = "retain"
destination = ["Dominium development and platform packaging"]
note = "Platform adapters consume USK artifacts; they are not USK runtime code."

[[file_map]]
source = "archive/legacy/setup_core_setup/setup/**;archive/legacy/launcher_core_launcher/launcher/**"
action = "delete"
after_equivalence = true
note = "Mine characterization semantics first; archive authority remains transitional/noncanonical."
```

## Exact recommended characterization inventory

```text
U01
  test: tests/characterization/universal/usk_manifest_contract_tests.py::test_install_manifest_canonical_bytes_refs_and_cross_platform_hash
  characterization: Golden bytes, identity, protocol/contract ranges, product hook inputs, path-separator
    invariance.
U02
  test: tests/characterization/universal/usk_plan_tests.py::test_plan_is_deterministic_and_side_effect_free
  characterization: Repeat plan byte-for-byte; assert no filesystem or registry mutation.
U03
  test: tests/characterization/universal/usk_install_transaction_tests.py::test_fresh_install_atomic_commit
  characterization: Final root absent through stage; complete manifest/state/store/log visible together after
    commit.
U04
  test: tests/characterization/universal/usk_install_transaction_tests.py::test_failure_injection_restores_install_and_preexisting_data_exactly
  characterization: Inject before/after every write, pack copy, rename and fallback-copy step; compare complete
    tree hashes and metadata.
U05
  test: tests/characterization/universal/usk_repair_transaction_tests.py::test_repair_failure_restores_exact_tree_and_retains_terminal_rollback
  characterization: Covers current lost-ROLLBACK defect.
U06
  test: tests/characterization/universal/usk_uninstall_transaction_tests.py::test_uninstall_success_and_failure_preserve_policy_and_terminal_log
  characterization: Covers embedded/external data roots, remove-data, failed commit, and data-root terminal log.
U07
  test: tests/characterization/universal/usk_update_tests.py::test_check_plan_apply_require_confirmation_and_never_download_silently
  characterization: Assert policy/channel injection and no network side effect.
U08
  test: tests/characterization/universal/usk_update_tests.py::test_update_failure_and_restart_recover_exact_prior_or_target_state
  characterization: Inject every managed-path and manifest-write failure; forbid mixed component sets.
U09
  test: tests/characterization/universal/usk_rollback_tests.py::test_select_restore_and_restart_rollback_transaction
  characterization: Assert transaction identity, exact tree restoration and recoverable interrupted rollback.
U10
  test: tests/characterization/universal/usk_registry_tests.py::test_multi_install_registry_atomic_sorted_and_recoverable
  characterization: Concurrent/add/remove/corrupt-write cases.
U11
  test: tests/characterization/universal/usk_package_verify_tests.py::test_package_lock_manifest_trust_and_offline_verification
  characterization: Includes yanked, unsigned, invalid signature, protocol mismatch and deterministic refusal.
U12
  test: tests/characterization/universal/usk_store_publication_tests.py::test_store_publication_atomic_hash_checked_concurrent_and_idempotent
  characterization: Expected-hash mismatch, partial directory, concurrent identical writers and crash before
    manifest.
U13
  test: tests/characterization/universal/usk_store_reachability_tests.py::test_reachability_follows_every_governed_manifest_and_nested_reference
  characterization: Install, instance, save, lock, profile, release manifest/index and bundle.
U14
  test: tests/characterization/universal/usk_store_gc_tests.py::test_gc_none_safe_aggressive_portable_and_conflict_are_transactional
  characterization: No partial quarantine/deletion on later conflict or failure.
U15
  test: tests/characterization/universal/usk_operation_journal_tests.py::test_each_operation_has_one_terminal_outcome_and_replays_after_crash
  characterization: PLAN/STAGE/COMMIT/ROLLBACK, operation ID, deterministic order and external uninstall log.
U16
  test: tests/characterization/universal/usk_extraction_bounds_tests.py::test_staging_rejects_traversal_symlink_escape_quota_and_partial_payload
  characterization: Required before accepting a universal bounded extraction contract.

L01
  test: tests/characterization/universal/ulk_reference_tests.py::test_product_install_instance_profile_artifact_refs_roundtrip_and_refuse_invalid
  characterization: No path-as-identity coercion.
L02
  test: tests/characterization/universal/ulk_discovery_tests.py::test_install_discovery_precedence_and_ambiguity
  characterization: CLI, environment, ID, executable adjacency and registry order.
L03
  test: tests/characterization/universal/ulk_profile_preference_tests.py::test_profile_instance_and_preferences_persist_atomically_and_recover
  characterization: Replaces native profile/config stubs.
L04
  test: tests/characterization/universal/ulk_preflight_tests.py::test_full_degraded_frozen_inspect_and_refuse_matrix
  characterization: Packs, saves, contracts, capabilities, trust and instance kind.
L05
  test: tests/characterization/universal/ulk_launch_plan_tests.py::test_launch_plan_determinism_and_staleness
  characterization: Changing any referenced manifest invalidates a prior plan.
L06
  test: tests/characterization/universal/ulk_process_tests.py::test_spawn_success_nonzero_missing_executable_and_signal_terminal_outcomes
  characterization: Proves a successful `run` actually starts a process.
L07
  test: tests/characterization/universal/ulk_process_tests.py::test_process_identity_cwd_environment_and_containment
  characterization: Exact argv, no shell interpolation, stable process identity.
L08
  test: tests/characterization/universal/ulk_process_tests.py::test_bounded_stdout_stderr_timeout_and_cancellation
  characterization: Backpressure, truncation disclosure and process-tree containment.
L09
  test: tests/characterization/universal/ulk_session_journal_tests.py::test_operation_attempt_execution_session_identity_and_crash_recovery
  characterization: Exactly one terminal outcome per attempt.
L10
  test: tests/characterization/universal/ulk_client_parity_tests.py::test_cli_c_api_and_dominium_facade_emit_equivalent_requests_and_results
  characterization: Preserves compatibility surfaces while changing owner.
L11
  test: tests/characterization/universal/ulk_concurrency_tests.py::test_duplicate_and_concurrent_attempt_policy
  characterization: Idempotency, cancellation races and journal ordering.

P01
  test: tests/characterization/dominium/product_recipe_tests.py::test_dominium_recipe_golden_binaries_packs_descriptors_and_defaults
  characterization: Product identity remains outside USK.
P02
  test: tests/characterization/dominium/setup_launcher_ui_parity_tests.py::test_cli_tui_gui_actions_and_refusals_are_equivalent
  characterization: Covers active native façades.
P03
  test: tests/characterization/dominium/launch_adapter_tests.py::test_dominium_session_to_ulk_process_spec
  characterization: Executable, args, cwd, environment, save/profile/instance refs.
P04
  test: tests/characterization/dominium/launcher_authority_tests.py::test_entitlement_profile_and_token_mapping
  characterization: Retains current product authority behavior.
P05
  test: tests/characterization/dominium/release_policy_tests.py::test_channel_support_downgrade_trust_and_no_silent_update_policy
  characterization: Product policy injection into USK.
P06
  test: tests/characterization/dominium/platform_packaging_smoke_tests.py::test_supported_legacy_platform_adapters_invoke_same_provider_contract
  characterization: Windows/Linux/macOS packaging boundary.

X01
  test: tests/characterization/convergence/local_provider_differential_tests.py::test_local_and_provider_outputs_trees_refusals_and_logs_match
  characterization: Mandatory before routing defaults to providers.
X02
  test: tests/characterization/convergence/provider_purity_tests.py::test_provider_has_no_dominium_import_ids_paths_or_default_policy
  characterization: Mandatory multi-consumer purity proof.
X03
  test: tests/characterization/convergence/provider_rollback_tests.py::test_feature_flag_returns_to_local_engine_with_dual_readable_state
  characterization: Mandatory before provider default-on.
X04
  test: tests/characterization/convergence/deletion_gate_tests.py::test_candidate_has_no_build_reference_runtime_import_exported_abi_or_unique_behavior
  characterization: Mandatory before any delete row.
D01
  test: tests/characterization/dominium/release_tooling_tests.py::test_generators_consume_provider_schemas_without_owning_runtime_policy
  characterization: Keeps development tooling separate.
```

Existing coverage partially maps to U03/U04/U05/U10, L02/L04, U12 and product flows at:

- `tests/setup/setup_install_tests.py:76,104,128,153,177,240`
- `tests/setup/install_manifest_tests.py:91,118,133,170`
- `tests/launcher/launcher_cli_tests.py:464,498,539,585,623,684,750,820,864`
- `tests/operations/content_store_tests.py:140,160,177,225,298`

The update simulation in `tools/release/mvp/update_sim_common.py:449-872` and STORE-GC baseline generator in
`tools/package/libraries/store/store_gc_common.py:211-793` are useful evidence generators, but neither is an
active failure-injection characterization suite.

## Migration order

1. Freeze the above characterization corpus and golden state/log schemas.
2. Publish neutral USK/ULK identity, refusal, operation, journal and reference contracts.
3. Extract read-only USK verification/planning and ULK reference/discovery first.
4. Extract store reads/reachability; redesign atomic publication and transactional GC before routing writes.
5. Implement USK transactions with durable recovery, then dual-run install/repair/update/uninstall/rollback.
6. Implement ULK launch plans, process backend, attempts, sessions, containment and bounded I/O.
7. Adapt Dominium recipes, `launch.py`, native CLI/TUI/GUI and packaging façades.
8. Prove a second non-Dominium consumer and provider-purity test.
9. Default provider routing on with one-release local fallback and dual-readable state.
10. Only then apply conditional delete rows.

This ordering preserves Dominium’s product anchors and release/control-plane substrate while extracting behavior, not files wholesale.

## Verdict

This report ratifies the ownership and convergence strategy, not a code transplant. `read_only = true` and
`implementation_moved = false` remain binding until the named provider contracts, characterization tests,
second-consumer proof, reversible product adapters, and conditional deletion gates are independently satisfied.
