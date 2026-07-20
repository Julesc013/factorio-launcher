# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

add_library(flb_factorio_launch_static STATIC
  launch/flb_factorio_execution.cpp launch/flb_factorio_launch_plan.cpp)
target_compile_features(flb_factorio_launch_static PUBLIC cxx_std_17)
target_include_directories(flb_factorio_launch_static PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/launch)
target_link_libraries(flb_factorio_launch_static PUBLIC
  facman_base_static facman_core_static facman_platform_static)

add_library(flb_factorio_discovery_static STATIC
  discovery/discovery_service.cpp discovery/flb_factorio_discovery.cpp
  discovery/provider_explicit.cpp discovery/provider_linux.cpp discovery/provider_macos.cpp
  discovery/provider_windows.cpp discovery/steam_vdf.cpp)
target_compile_features(flb_factorio_discovery_static PUBLIC cxx_std_17)
target_include_directories(flb_factorio_discovery_static PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/discovery)
target_link_libraries(flb_factorio_discovery_static PUBLIC facman_core_static facman_platform_static)
if(WIN32)
  target_link_libraries(flb_factorio_discovery_static PUBLIC Advapi32)
endif()

add_library(flb_factorio_install_validation_static STATIC
  install_validation/flb_factorio_setup_recipe.cpp)
target_compile_features(flb_factorio_install_validation_static PUBLIC cxx_std_17)
target_include_directories(flb_factorio_install_validation_static PUBLIC
  ${CMAKE_CURRENT_SOURCE_DIR}/install_validation)
target_link_libraries(flb_factorio_install_validation_static PUBLIC facman_core_static)

add_library(flb_factorio_install_model_static STATIC
  installation/flb_factorio_install_model.cpp)
target_compile_features(flb_factorio_install_model_static PUBLIC cxx_std_17)
target_include_directories(flb_factorio_install_model_static PUBLIC
  ${CMAKE_CURRENT_SOURCE_DIR}/installation)
target_link_libraries(flb_factorio_install_model_static PUBLIC
  facman_base_static facman_core_static facman_platform_static
  flb_factorio_discovery_static)

add_library(flb_factorio_diagnostics_static STATIC diagnostics/flb_factorio_diagnostics.cpp)
target_compile_features(flb_factorio_diagnostics_static PUBLIC cxx_std_17)
target_include_directories(flb_factorio_diagnostics_static PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/diagnostics)
target_link_libraries(flb_factorio_diagnostics_static PUBLIC facman_transaction_static facman_workspace_static)

add_library(flb_factorio_mods_static STATIC mods/flb_factorio_mods.cpp)
target_compile_features(flb_factorio_mods_static PUBLIC cxx_std_17)
target_include_directories(flb_factorio_mods_static PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/mods)
target_link_libraries(flb_factorio_mods_static PUBLIC
  facman_archive_static facman_base_static facman_core_static facman_workspace_static)

add_library(flb_factorio_modsets_static
  modsets/flb_factorio_modsets.cpp modsets/flb_factorio_modset_operations.cpp
  modsets/flb_factorio_modset_solver.cpp)
target_compile_features(flb_factorio_modsets_static PUBLIC cxx_std_17)
target_include_directories(flb_factorio_modsets_static PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/modsets ${CMAKE_CURRENT_SOURCE_DIR}/mods)
target_link_libraries(flb_factorio_modsets_static PUBLIC flb_factorio_mods_static facman_transaction_static facman_workspace_static)

add_library(flb_factorio_saves_static saves/flb_factorio_save_operations.cpp saves/flb_factorio_save_index.cpp)
target_compile_features(flb_factorio_saves_static PUBLIC cxx_std_17)
target_include_directories(flb_factorio_saves_static PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/saves ${CMAKE_CURRENT_SOURCE_DIR}/modsets)
target_link_libraries(flb_factorio_saves_static PUBLIC
  facman_archive_static facman_base_static facman_transaction_static facman_workspace_static
  flb_factorio_launch_static flb_factorio_modsets_static)

add_library(flb_factorio_instance_static
  instance/flb_factorio_instance_lifecycle.cpp
  instance/flb_factorio_local_data_import.cpp)
target_compile_features(flb_factorio_instance_static PUBLIC cxx_std_17)
target_include_directories(flb_factorio_instance_static PUBLIC
  ${CMAKE_CURRENT_SOURCE_DIR}/instance ${CMAKE_CURRENT_SOURCE_DIR}/launch
  ${CMAKE_CURRENT_SOURCE_DIR}/modsets ${CMAKE_CURRENT_SOURCE_DIR}/snapshots)
target_link_libraries(flb_factorio_instance_static PUBLIC
  facman_archive_static facman_base_static facman_platform_static facman_transaction_static facman_workspace_static
  flb_factorio_launch_static flb_factorio_modsets_static flb_factorio_snapshots_static)

add_library(flb_factorio_snapshots_static snapshots/flb_factorio_snapshots.cpp)
target_compile_features(flb_factorio_snapshots_static PUBLIC cxx_std_17)
target_include_directories(flb_factorio_snapshots_static PUBLIC
  ${CMAKE_CURRENT_SOURCE_DIR}/snapshots ${CMAKE_CURRENT_SOURCE_DIR}/launch)
target_link_libraries(flb_factorio_snapshots_static PUBLIC
  facman_archive_static facman_base_static facman_transaction_static facman_workspace_static
  flb_factorio_launch_static)

add_library(flb_factorio_profiles_static profiles/flb_factorio_profiles.cpp)
target_compile_features(flb_factorio_profiles_static PUBLIC cxx_std_17)
target_include_directories(flb_factorio_profiles_static PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/profiles)
target_link_libraries(flb_factorio_profiles_static PUBLIC
  facman_base_static facman_transaction_static facman_workspace_static)

add_library(flb_factorio_server_static server/flb_factorio_server_plan.cpp)
target_compile_features(flb_factorio_server_static PUBLIC cxx_std_17)
target_include_directories(flb_factorio_server_static PUBLIC
  ${CMAKE_CURRENT_SOURCE_DIR}/server ${CMAKE_CURRENT_SOURCE_DIR}/saves ${CMAKE_CURRENT_SOURCE_DIR}/modsets)
target_link_libraries(flb_factorio_server_static PUBLIC
  facman_archive_static facman_base_static facman_transaction_static facman_workspace_static
  flb_factorio_saves_static flb_factorio_modsets_static)

add_library(facman_factorio_model INTERFACE)
target_link_libraries(facman_factorio_model INTERFACE
  flb_factorio_discovery_static flb_factorio_diagnostics_static flb_factorio_launch_static
  flb_factorio_install_model_static flb_factorio_install_validation_static
  flb_factorio_mods_static flb_factorio_modsets_static flb_factorio_saves_static flb_factorio_instance_static
  flb_factorio_snapshots_static)
target_link_libraries(facman_factorio_model INTERFACE flb_factorio_profiles_static)
target_link_libraries(facman_factorio_model INTERFACE flb_factorio_server_static)
add_library(facman::factorio_model ALIAS facman_factorio_model)

add_library(flb_factorio_application_static STATIC
  application/application_configuration.cpp application/application_context.cpp
  application/command_admission.cpp application/command_dispatch.cpp application/command_result.cpp
  application/flb_factorio_application.cpp application/setup_gateway.cpp application/handlers/diagnostics.cpp
  application/handlers/doctor.cpp application/handlers/installs.cpp application/handlers/instances.cpp
  application/handlers/intelligence.cpp
  application/handlers/launch.cpp application/handlers/mods.cpp application/handlers/modsets.cpp
  application/handlers/preferences.cpp application/handlers/product.cpp application/handlers/recovery.cpp application/handlers/saves.cpp
  application/handlers/snapshots.cpp
  application/handlers/profiles.cpp application/modules/installation_module.cpp
  application/modules/launch_module.cpp
  application/handlers/setup.cpp application/handlers/unavailable.cpp application/handlers/utility.cpp)
target_compile_features(flb_factorio_application_static PUBLIC cxx_std_17)
target_include_directories(flb_factorio_application_static PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/application)
target_compile_definitions(flb_factorio_application_static PRIVATE FACMAN_WITH_SETUP=$<BOOL:${FACMAN_WITH_SETUP}>)
target_link_libraries(flb_factorio_application_static PUBLIC
  facman_base_static facman_workspace_static facman_preferences_static facman_factorio_model flaunch_runtime_static ulk_static)
if(FACMAN_WITH_SETUP)
  target_link_libraries(flb_factorio_application_static PUBLIC usk_static)
endif()
add_library(facman::factorio_application ALIAS flb_factorio_application_static)

add_library(flb_factorio_static STATIC binding/flb_api.c)
target_include_directories(flb_factorio_static
  PUBLIC
    $<BUILD_INTERFACE:${PROJECT_SOURCE_DIR}/include>
    $<BUILD_INTERFACE:${FLAUNCH_UNIVERSAL_LAUNCHER_ROOT}/include>
    $<INSTALL_INTERFACE:include>
  PRIVATE ${PROJECT_SOURCE_DIR}/runtime/core/generated)
target_compile_definitions(flb_factorio_static PRIVATE FACMAN_WITH_SETUP=$<BOOL:${FACMAN_WITH_SETUP}>)
target_link_libraries(flb_factorio_static PRIVATE ulk_static flb_factorio_application_static)

add_library(flb_factorio_shared SHARED binding/flb_api.c)
target_include_directories(flb_factorio_shared
  PUBLIC
    $<BUILD_INTERFACE:${PROJECT_SOURCE_DIR}/include>
    $<BUILD_INTERFACE:${FLAUNCH_UNIVERSAL_LAUNCHER_ROOT}/include>
    $<INSTALL_INTERFACE:include>
  PRIVATE ${PROJECT_SOURCE_DIR}/runtime/core/generated)
target_compile_definitions(flb_factorio_shared
  PRIVATE FLB_BUILD_SHARED FACMAN_WITH_SETUP=$<BOOL:${FACMAN_WITH_SETUP}>
  INTERFACE FLB_USE_SHARED)
target_link_libraries(flb_factorio_shared PRIVATE
  $<BUILD_INTERFACE:ulk_shared>
  $<BUILD_INTERFACE:flb_factorio_application_static>)
set_property(TARGET flb_factorio_shared PROPERTY INTERFACE_LINK_LIBRARIES "")
set_target_properties(flb_factorio_shared PROPERTIES
  EXPORT_NAME flb
  OUTPUT_NAME flb_factorio
  VERSION ${PROJECT_VERSION}
  SOVERSION 1
  WINDOWS_EXPORT_ALL_SYMBOLS ON)

add_library(flb_factorio ALIAS flb_factorio_static)
add_library(facman::binding ALIAS flb_factorio_static)
foreach(target IN ITEMS
    flb_factorio_launch_static flb_factorio_discovery_static flb_factorio_diagnostics_static
    flb_factorio_install_model_static flb_factorio_install_validation_static
    flb_factorio_mods_static flb_factorio_modsets_static flb_factorio_saves_static flb_factorio_instance_static
    flb_factorio_snapshots_static
    flb_factorio_profiles_static
    flb_factorio_server_static
    flb_factorio_application_static flb_factorio_static flb_factorio_shared)
  facman_apply_policies(${target})
endforeach()
