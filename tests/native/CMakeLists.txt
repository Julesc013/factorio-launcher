# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

find_package(Threads REQUIRED)

function(facman_native_test target source labels)
  add_executable(${target} ${source})
  add_test(NAME ${target} COMMAND ${target})
  set_tests_properties(${target} PROPERTIES LABELS "${labels}")
  facman_apply_policies(${target})
endfunction()

facman_native_test(miniz_dependency_smoke miniz_dependency_smoke.c "fast-unit;contract")
target_link_libraries(miniz_dependency_smoke PRIVATE miniz_static)
facman_native_test(fl_json_core_smoke fl_json_core_smoke.cpp "fast-unit;contract")
target_compile_features(fl_json_core_smoke PRIVATE cxx_std_17)
target_link_libraries(fl_json_core_smoke PRIVATE facman_core_static)
facman_native_test(facman_operation_permit_smoke facman_operation_permit_smoke.cpp "fast-unit;contract;security")
target_compile_features(facman_operation_permit_smoke PRIVATE cxx_std_17)
target_link_libraries(facman_operation_permit_smoke PRIVATE facman_permit_static Threads::Threads)
facman_native_test(facman_application_types_smoke facman_application_types_smoke.cpp "fast-unit;contract")
target_compile_features(facman_application_types_smoke PRIVATE cxx_std_17)
target_link_libraries(facman_application_types_smoke PRIVATE flb_factorio_application_static)
facman_native_test(flb_factorio_discovery_smoke flb_factorio_discovery_smoke.cpp "fast-unit;security;integration")
target_compile_features(flb_factorio_discovery_smoke PRIVATE cxx_std_17)
target_link_libraries(flb_factorio_discovery_smoke PRIVATE flb_factorio_discovery_static)
facman_native_test(flb_factorio_install_model_smoke flb_factorio_install_model_smoke.cpp "fast-unit;contract;security")
target_compile_features(flb_factorio_install_model_smoke PRIVATE cxx_std_17)
target_link_libraries(flb_factorio_install_model_smoke PRIVATE flb_factorio_install_model_static facman_core_static)
facman_native_test(flb_factorio_instance_model_smoke flb_factorio_instance_model_smoke.cpp "fast-unit;contract;security;filesystem")
target_compile_features(flb_factorio_instance_model_smoke PRIVATE cxx_std_17)
target_link_libraries(flb_factorio_instance_model_smoke PRIVATE flb_factorio_instance_static facman_core_static)
facman_native_test(flb_factorio_launch_permit_smoke flb_factorio_launch_permit_smoke.cpp "fast-unit;contract;security;filesystem")
target_compile_features(flb_factorio_launch_permit_smoke PRIVATE cxx_std_17)
target_compile_definitions(flb_factorio_launch_permit_smoke PRIVATE
  FACMAN_TEST_SOURCE_ROOT="${PROJECT_SOURCE_DIR}"
  FACMAN_TEST_TEMP_ROOT="${CMAKE_CURRENT_BINARY_DIR}/launch-permit-smoke")
target_link_libraries(flb_factorio_launch_permit_smoke PRIVATE flb_factorio_instance_static facman_permit_static)
facman_native_test(facman_hermetic_play_candidate_smoke facman_hermetic_play_candidate_smoke.cpp "fast-unit;contract;security;filesystem;platform")
target_compile_features(facman_hermetic_play_candidate_smoke PRIVATE cxx_std_17)
target_compile_definitions(facman_hermetic_play_candidate_smoke PRIVATE
  FACMAN_TEST_SOURCE_ROOT="${PROJECT_SOURCE_DIR}"
  FACMAN_TEST_TEMP_ROOT="${CMAKE_CURRENT_BINARY_DIR}/candidate-smoke")
target_link_libraries(facman_hermetic_play_candidate_smoke PRIVATE
  flb_factorio_launch_static facman_permit_static facman_platform_static)
add_executable(facman_gate4c_verdict_harness gate4c_verdict_harness.cpp)
target_compile_features(facman_gate4c_verdict_harness PRIVATE cxx_std_17)
target_compile_definitions(facman_gate4c_verdict_harness PRIVATE
  FACMAN_TEST_SOURCE_ROOT="${PROJECT_SOURCE_DIR}")
target_link_libraries(facman_gate4c_verdict_harness PRIVATE
  flb_factorio_instance_static flb_factorio_launch_static
  facman_permit_static facman_platform_static)
facman_apply_policies(facman_gate4c_verdict_harness)
add_test(
  NAME facman_gate4c_verdict_harness_canonical_smoke
  COMMAND facman_gate4c_verdict_harness --self-test-observation-digest)
set_tests_properties(
  facman_gate4c_verdict_harness_canonical_smoke
  PROPERTIES LABELS "fast-unit;contract;security")
facman_native_test(flb_factorio_setup_recipe_smoke flb_factorio_setup_recipe_smoke.cpp "fast-unit;security;contract")
target_compile_features(flb_factorio_setup_recipe_smoke PRIVATE cxx_std_17)
target_link_libraries(flb_factorio_setup_recipe_smoke PRIVATE flb_factorio_install_validation_static)
if(FACMAN_WITH_SETUP)
  facman_native_test(flb_setup_gateway_smoke flb_setup_gateway_smoke.cpp "filesystem;security;integration")
  target_compile_features(flb_setup_gateway_smoke PRIVATE cxx_std_17)
  target_link_libraries(flb_setup_gateway_smoke PRIVATE flb_factorio_application_static)
  facman_native_test(
    m1_three_repository_system_proof
    m1_three_repository_system_proof.cpp
    "contract;filesystem;integration;transaction")
  target_sources(m1_three_repository_system_proof PRIVATE
    m1_system_proof_fixture.cpp
    m1_system_proof_launcher.cpp)
  target_compile_features(m1_three_repository_system_proof PRIVATE cxx_std_17)
  target_link_libraries(m1_three_repository_system_proof PRIVATE
    flb_factorio_application_static
    usk_lifecycle_static
    ulk_static)
endif()
add_executable(facman_process_probe facman_process_probe.cpp)
target_compile_features(facman_process_probe PRIVATE cxx_std_17)
facman_apply_policies(facman_process_probe)
facman_native_test(facman_execution_foundation_smoke facman_execution_foundation_smoke.cpp "fast-unit;platform;integration;filesystem")
target_compile_features(facman_execution_foundation_smoke PRIVATE cxx_std_17)
target_link_libraries(facman_execution_foundation_smoke PRIVATE
  flb_factorio_launch_static facman_base_static facman_platform_static)
target_compile_definitions(facman_execution_foundation_smoke PRIVATE
  FACMAN_TEST_PROCESS_PROBE_PATH="$<TARGET_FILE:facman_process_probe>")
add_dependencies(facman_execution_foundation_smoke facman_process_probe)
if(TARGET facman_cli)
  facman_native_test(facman_workspace_resolver_smoke facman_workspace_resolver_smoke.cpp "fast-unit;platform;frontend")
  target_compile_features(facman_workspace_resolver_smoke PRIVATE cxx_std_17)
  target_link_libraries(facman_workspace_resolver_smoke PRIVATE facman_client_static)
  facman_native_test(facman_client_smoke facman_client_smoke.cpp "fast-unit;integration")
  target_compile_features(facman_client_smoke PRIVATE cxx_std_17)
  target_link_libraries(facman_client_smoke PRIVATE facman_client_static Threads::Threads)
  target_compile_definitions(facman_client_smoke PRIVATE
    FACMAN_TEST_CLI_PATH="$<TARGET_FILE:facman_cli>"
    FACMAN_TEST_PROCESS_PROBE_PATH="$<TARGET_FILE:facman_process_probe>")
  add_dependencies(facman_client_smoke facman_cli facman_process_probe)
endif()
if(TARGET facman_tui_static)
  facman_native_test(facman_tui_smoke facman_tui_smoke.cpp "fast-unit;integration;frontend")
  target_compile_features(facman_tui_smoke PRIVATE cxx_std_17)
  target_link_libraries(facman_tui_smoke PRIVATE facman_tui_static)
endif()
facman_native_test(fl_platform_io_smoke fl_platform_io_smoke.cpp "filesystem;platform")
target_compile_features(fl_platform_io_smoke PRIVATE cxx_std_17)
target_link_libraries(fl_platform_io_smoke PRIVATE facman_platform_static)
facman_native_test(facman_preferences_smoke facman_preferences_smoke.cpp "filesystem;transaction;integration")
target_compile_features(facman_preferences_smoke PRIVATE cxx_std_17)
target_link_libraries(facman_preferences_smoke PRIVATE facman_preferences_static)
facman_native_test(facman_snapshot_policy_smoke facman_snapshot_policy_smoke.cpp "fast-unit;policy;performance")
target_compile_features(facman_snapshot_policy_smoke PRIVATE cxx_std_17)
target_link_libraries(facman_snapshot_policy_smoke PRIVATE flb_factorio_snapshots_static)
facman_native_test(fl_workspace_store_smoke fl_workspace_store_smoke.cpp "filesystem;integration")
target_compile_definitions(fl_workspace_store_smoke PRIVATE FACMAN_TEST_SOURCE_ROOT="${PROJECT_SOURCE_DIR}")
target_compile_features(fl_workspace_store_smoke PRIVATE cxx_std_17)
target_link_libraries(fl_workspace_store_smoke PRIVATE facman_workspace_static facman_transaction_static)
facman_native_test(fl_transaction_session_smoke fl_transaction_session_smoke.cpp "transaction;integration")
target_compile_features(fl_transaction_session_smoke PRIVATE cxx_std_17)
target_link_libraries(fl_transaction_session_smoke PRIVATE facman_transaction_static)
facman_native_test(fl_archive_core_smoke fl_archive_core_smoke.cpp "archive;integration")
if(WIN32)
  target_sources(fl_archive_core_smoke PRIVATE ${PROJECT_SOURCE_DIR}/apps/cli/facman.manifest)
endif()
target_compile_features(fl_archive_core_smoke PRIVATE cxx_std_17)
target_link_libraries(fl_archive_core_smoke PRIVATE facman_archive_static)

foreach(target IN ITEMS fl_archive_probe fl_archive_metadata_fuzz fl_archive_plan_fuzz)
  add_executable(${target} ${target}.cpp)
  target_compile_features(${target} PRIVATE cxx_std_17)
  target_link_libraries(${target} PRIVATE facman_archive_static)
  facman_apply_policies(${target})
endforeach()

add_executable(fl_json_fuzz fl_json_fuzz.cpp)
target_compile_features(fl_json_fuzz PRIVATE cxx_std_17)
target_link_libraries(fl_json_fuzz PRIVATE facman_core_static)
facman_apply_policies(fl_json_fuzz)

add_executable(facman_operation_permit_fuzz
  facman_operation_permit_fuzz.cpp
  facman_operation_permit_libfuzzer.cpp)
target_compile_features(facman_operation_permit_fuzz PRIVATE cxx_std_17)
target_link_libraries(facman_operation_permit_fuzz PRIVATE facman_permit_static)
facman_apply_policies(facman_operation_permit_fuzz)

facman_native_test(flb_command_bridge_smoke flb_command_bridge_smoke.c "contract;integration")
target_compile_definitions(flb_command_bridge_smoke PRIVATE FACMAN_WITH_SETUP=$<BOOL:${FACMAN_WITH_SETUP}>)
target_link_libraries(flb_command_bridge_smoke PRIVATE flaunch_client_static flb_factorio_static)
facman_native_test(fl_path_safety_smoke fl_path_safety_smoke.cpp "filesystem;fast-unit")
target_compile_features(fl_path_safety_smoke PRIVATE cxx_std_17)
target_link_libraries(fl_path_safety_smoke PRIVATE facman_base_static Threads::Threads)
facman_native_test(facman_isolation_lock_smoke facman_isolation_lock_smoke.cpp "platform;integration")
target_compile_features(facman_isolation_lock_smoke PRIVATE cxx_std_17)
target_link_libraries(facman_isolation_lock_smoke PRIVATE flb_factorio_launch_static facman_base_static)
facman_native_test(facman_diagnostic_traversal_smoke facman_diagnostic_traversal_smoke.cpp "filesystem;integration")
if(WIN32)
  target_sources(facman_diagnostic_traversal_smoke PRIVATE ${PROJECT_SOURCE_DIR}/apps/cli/facman.manifest)
endif()
target_compile_features(facman_diagnostic_traversal_smoke PRIVATE cxx_std_17)
target_link_libraries(facman_diagnostic_traversal_smoke PRIVATE flb_factorio_diagnostics_static)

add_executable(facman_isolation_probe facman_isolation_probe.cpp)
if(WIN32)
  target_sources(facman_isolation_probe PRIVATE ${PROJECT_SOURCE_DIR}/apps/cli/facman.manifest)
endif()
target_compile_features(facman_isolation_probe PRIVATE cxx_std_17)
target_link_libraries(facman_isolation_probe PRIVATE flb_factorio_launch_static facman_base_static Threads::Threads)
facman_apply_policies(facman_isolation_probe)

facman_native_test(facman_abi_layout_smoke facman_abi_layout_smoke.cpp "contract;platform")
target_compile_features(facman_abi_layout_smoke PRIVATE cxx_std_17)
target_link_libraries(facman_abi_layout_smoke PRIVATE flb_factorio_static facman_client_static)
facman_native_test(
  m2_wu6_launcher_handoff_smoke
  m2_wu6_launcher_handoff_smoke.c
  "contract;integration;setup")
target_link_libraries(m2_wu6_launcher_handoff_smoke PRIVATE ulk_static)

find_package(Python3 COMPONENTS Interpreter REQUIRED)
set(FACMAN_ABI_SYMBOL_ARGS)
if(FACMAN_ENABLE_SANITIZERS AND CMAKE_SYSTEM_NAME STREQUAL "Linux")
  list(APPEND FACMAN_ABI_SYMBOL_ARGS --symbols-only)
endif()
add_test(NAME facman_abi_symbol_smoke
  COMMAND ${Python3_EXECUTABLE} ${PROJECT_SOURCE_DIR}/tools/abi_symbol_check.py
    --library $<TARGET_FILE:flb_factorio_shared> ${FACMAN_ABI_SYMBOL_ARGS})
set_tests_properties(facman_abi_symbol_smoke PROPERTIES LABELS "contract;platform")

add_test(NAME facman_installed_sdk_smoke
  COMMAND ${Python3_EXECUTABLE} ${PROJECT_SOURCE_DIR}/tools/installed_sdk_smoke.py
    --cmake ${CMAKE_COMMAND}
    --build-dir ${CMAKE_BINARY_DIR}
    --source-dir ${PROJECT_SOURCE_DIR}/tests/installed_consumer
    --config $<CONFIG>)
set_tests_properties(facman_installed_sdk_smoke PROPERTIES LABELS "contract;package-runtime;platform")

facman_add_libfuzzer(fl_archive_libfuzzer fl_archive_libfuzzer.cpp)
if(TARGET fl_archive_libfuzzer)
  target_compile_options(facman_archive_static PRIVATE -fsanitize=fuzzer-no-link,address,undefined)
  target_link_libraries(fl_archive_libfuzzer PRIVATE facman_archive_static)
endif()
facman_add_libfuzzer(fl_json_libfuzzer fl_json_libfuzzer.cpp)
if(TARGET fl_json_libfuzzer)
  target_link_libraries(fl_json_libfuzzer PRIVATE facman_core_static)
endif()
facman_add_libfuzzer(facman_operation_permit_libfuzzer facman_operation_permit_libfuzzer.cpp)
if(TARGET facman_operation_permit_libfuzzer)
  target_compile_options(facman_permit_static PRIVATE -fsanitize=fuzzer-no-link,address,undefined)
  target_link_libraries(facman_operation_permit_libfuzzer PRIVATE facman_permit_static)
endif()

foreach(external_test IN ITEMS usk_command_graph_smoke usk_package_verify_smoke ulk_command_graph_smoke)
  if(TEST ${external_test})
    set_tests_properties(${external_test} PROPERTIES LABELS "contract;integration")
  endif()
endforeach()
