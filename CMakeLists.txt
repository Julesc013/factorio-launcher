cmake_minimum_required(VERSION 3.16)
project(facman LANGUAGES C CXX)

option(FLAUNCH_BUILD_NATIVE_APPS "Build native CLI/TUI/daemon scaffolds" ON)
option(FLAUNCH_BUILD_TESTS "Build FacMan native tests" ON)
option(FLAUNCH_ENABLE_SANITIZERS "Enable ASan and UBSan for native proof builds" OFF)

if(FLAUNCH_ENABLE_SANITIZERS)
  if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
    add_compile_options(-fsanitize=address,undefined -fno-omit-frame-pointer)
    add_link_options(-fsanitize=address,undefined)
  else()
    message(FATAL_ERROR "FLAUNCH_ENABLE_SANITIZERS requires GCC or Clang")
  endif()
endif()

# Product/application static libraries are also linked into the public shared
# binding. Keep one cross-platform object model so ELF shared links do not
# depend on a platform-specific target ordering accident.
set(CMAKE_POSITION_INDEPENDENT_CODE ON)

function(flaunch_append_env_candidate out_var env_name suffix)
  if(DEFINED ENV{${env_name}} AND NOT "$ENV{${env_name}}" STREQUAL "")
    file(TO_CMAKE_PATH "$ENV{${env_name}}" env_path)
    list(APPEND ${out_var} "${env_path}${suffix}")
    set(${out_var} "${${out_var}}" PARENT_SCOPE)
  endif()
endfunction()

function(flaunch_find_repo_root out_var repo_name specific_env)
  set(candidates)
  flaunch_append_env_candidate(candidates "${specific_env}" "")
  flaunch_append_env_candidate(candidates "FLAUNCH_UNIVERSAL_ROOT" "/${repo_name}")
  flaunch_append_env_candidate(candidates "FLAUNCH_WORKSPACE_ROOT" "/Universal/${repo_name}")
  flaunch_append_env_candidate(candidates "FLAUNCH_WORKSPACE_ROOT" "/${repo_name}")
  list(APPEND candidates
    "${CMAKE_CURRENT_SOURCE_DIR}/external/${repo_name}"
    "${CMAKE_CURRENT_SOURCE_DIR}/../${repo_name}"
    "${CMAKE_CURRENT_SOURCE_DIR}/../../Universal/${repo_name}"
    "${CMAKE_CURRENT_SOURCE_DIR}/../../${repo_name}"
    "${CMAKE_CURRENT_SOURCE_DIR}/../../../Universal/${repo_name}"
    "${CMAKE_CURRENT_SOURCE_DIR}/../../../${repo_name}"
  )

  foreach(candidate IN LISTS candidates)
    if(EXISTS "${candidate}/CMakeLists.txt")
      set(${out_var} "${candidate}" PARENT_SCOPE)
      return()
    endif()
  endforeach()

  list(GET candidates 0 fallback)
  set(${out_var} "${fallback}" PARENT_SCOPE)
endfunction()

function(flaunch_select_repo_root cache_var repo_name specific_env)
  if(NOT DEFINED ${cache_var} OR NOT EXISTS "${${cache_var}}/CMakeLists.txt")
    flaunch_find_repo_root(selected_path "${repo_name}" "${specific_env}")
    if(DEFINED ${cache_var} AND NOT "${${cache_var}}" STREQUAL "" AND NOT EXISTS "${${cache_var}}/CMakeLists.txt")
      message(STATUS "Ignoring unavailable ${repo_name} path: ${${cache_var}}")
    endif()
    set(${cache_var} "${selected_path}" CACHE PATH "Path to the ${repo_name} repository" FORCE)
  endif()
endfunction()

flaunch_select_repo_root(
  FLAUNCH_UNIVERSAL_SETUP_ROOT
  "universal-setup"
  "FLAUNCH_UNIVERSAL_SETUP_ROOT"
)
flaunch_select_repo_root(
  FLAUNCH_UNIVERSAL_LAUNCHER_ROOT
  "universal-launcher"
  "FLAUNCH_UNIVERSAL_LAUNCHER_ROOT"
)

if(FLAUNCH_BUILD_TESTS)
  enable_testing()
endif()

add_library(miniz_static STATIC external/miniz/miniz.c)
target_include_directories(miniz_static PUBLIC external/miniz)

if(NOT TARGET usk_static)
  if(EXISTS "${FLAUNCH_UNIVERSAL_SETUP_ROOT}/CMakeLists.txt")
    add_subdirectory("${FLAUNCH_UNIVERSAL_SETUP_ROOT}" "${CMAKE_CURRENT_BINARY_DIR}/universal-setup")
  else()
    message(FATAL_ERROR "universal-setup is required. Tried ${FLAUNCH_UNIVERSAL_SETUP_ROOT}. Set -DFLAUNCH_UNIVERSAL_SETUP_ROOT=..., FLAUNCH_UNIVERSAL_ROOT, or FLAUNCH_WORKSPACE_ROOT.")
  endif()
endif()

if(NOT TARGET ulk_static)
  if(EXISTS "${FLAUNCH_UNIVERSAL_LAUNCHER_ROOT}/CMakeLists.txt")
    add_subdirectory("${FLAUNCH_UNIVERSAL_LAUNCHER_ROOT}" "${CMAKE_CURRENT_BINARY_DIR}/universal-launcher")
  else()
    message(FATAL_ERROR "universal-launcher is required. Tried ${FLAUNCH_UNIVERSAL_LAUNCHER_ROOT}. Set -DFLAUNCH_UNIVERSAL_LAUNCHER_ROOT=..., FLAUNCH_UNIVERSAL_ROOT, or FLAUNCH_WORKSPACE_ROOT.")
  endif()
endif()

set(FLAUNCH_RUNTIME_SOURCES
  runtime/package/fl_runtime_component.cpp
  runtime/package/fl_runtime_extract.c
  runtime/package/fl_runtime_locator.c
  runtime/package/fl_runtime_manifest.c
  runtime/package/fl_runtime_verify.cpp
)

set(FLAUNCH_CLIENT_SOURCES
  runtime/client/fl_command_client.c
  runtime/client/fl_command_client_cabi.c
  runtime/client/fl_command_client_cabi_execute.c
  runtime/client/fl_command_client_daemon.c
  runtime/client/fl_command_client_json.c
)

add_library(flaunch_runtime_static STATIC ${FLAUNCH_RUNTIME_SOURCES})
target_include_directories(flaunch_runtime_static PUBLIC runtime/package)
target_compile_features(flaunch_runtime_static PUBLIC cxx_std_17)

add_library(facman_base_static STATIC
  runtime/base/fl_local_operation_lock.cpp
  runtime/base/fl_path_safety.cpp
  runtime/base/fl_sha256.cpp
)
target_include_directories(facman_base_static PUBLIC runtime/base)
target_compile_features(facman_base_static PUBLIC cxx_std_17)

add_library(facman_archive_static STATIC
  runtime/archive/fl_archive_platform.cpp
  runtime/archive/fl_archive_policy.cpp
  runtime/archive/fl_archive_reader.cpp
  runtime/archive/fl_archive_writer.cpp
)
target_include_directories(facman_archive_static PUBLIC runtime/archive)
target_compile_features(facman_archive_static PUBLIC cxx_std_17)
target_link_libraries(facman_archive_static PUBLIC facman_base_static miniz_static)

add_library(facman_transaction_static STATIC runtime/transaction/fl_transaction.cpp)
target_include_directories(facman_transaction_static PUBLIC runtime/transaction runtime/archive runtime/base)
target_compile_features(facman_transaction_static PUBLIC cxx_std_17)
target_link_libraries(facman_transaction_static PUBLIC facman_archive_static facman_base_static)

add_library(flaunch_client_static STATIC ${FLAUNCH_CLIENT_SOURCES})
target_include_directories(flaunch_client_static PUBLIC
  runtime/client
  include
  "${FLAUNCH_UNIVERSAL_LAUNCHER_ROOT}/include"
)

add_library(flb_factorio_launch_static STATIC runtime/factorio/launch/flb_factorio_launch_plan.cpp)
target_compile_features(flb_factorio_launch_static PUBLIC cxx_std_17)
target_include_directories(flb_factorio_launch_static PUBLIC runtime/factorio/launch)
target_link_libraries(flb_factorio_launch_static PUBLIC facman_base_static)

add_library(flb_factorio_discovery_static STATIC runtime/factorio/discovery/flb_factorio_discovery.cpp)
target_compile_features(flb_factorio_discovery_static PUBLIC cxx_std_17)
target_include_directories(flb_factorio_discovery_static PUBLIC runtime/factorio/discovery)
if(WIN32)
  target_link_libraries(flb_factorio_discovery_static PUBLIC Advapi32)
endif()

add_library(flb_factorio_diagnostics_static STATIC runtime/factorio/diagnostics/flb_factorio_diagnostics.cpp)
target_compile_features(flb_factorio_diagnostics_static PUBLIC cxx_std_17)
target_include_directories(flb_factorio_diagnostics_static PUBLIC runtime/factorio/diagnostics)
target_link_libraries(flb_factorio_diagnostics_static PUBLIC facman_transaction_static)

add_library(flb_factorio_mods_static STATIC runtime/factorio/mods/flb_factorio_mods.cpp)
target_compile_features(flb_factorio_mods_static PUBLIC cxx_std_17)
target_include_directories(flb_factorio_mods_static PUBLIC runtime/factorio/mods)
target_link_libraries(flb_factorio_mods_static PUBLIC facman_archive_static facman_base_static)

add_library(flb_factorio_modsets_static STATIC
  runtime/factorio/modsets/flb_factorio_modsets.cpp
  runtime/factorio/modsets/flb_factorio_modset_operations.cpp
)
target_compile_features(flb_factorio_modsets_static PUBLIC cxx_std_17)
target_include_directories(flb_factorio_modsets_static PUBLIC runtime/factorio/modsets runtime/factorio/mods)
target_link_libraries(flb_factorio_modsets_static PUBLIC flb_factorio_mods_static facman_transaction_static)

add_library(flb_factorio_saves_static
  runtime/factorio/saves/flb_factorio_save_operations.cpp
)
target_compile_features(flb_factorio_saves_static PUBLIC cxx_std_17)
target_include_directories(flb_factorio_saves_static PUBLIC
  runtime/factorio/saves
  runtime/factorio/modsets
)
target_link_libraries(flb_factorio_saves_static PUBLIC
  facman_archive_static
  facman_base_static
  facman_transaction_static
  flb_factorio_launch_static
  flb_factorio_modsets_static
)
target_include_directories(flaunch_runtime_static PRIVATE runtime/base)
target_link_libraries(flaunch_runtime_static PRIVATE facman_base_static)

add_library(flb_factorio_application_static STATIC runtime/factorio/application/flb_factorio_application.cpp)
target_compile_features(flb_factorio_application_static PUBLIC cxx_std_17)
target_include_directories(flb_factorio_application_static PUBLIC runtime/factorio/application)
target_link_libraries(flb_factorio_application_static PUBLIC
  facman_base_static
  flb_factorio_discovery_static
  flb_factorio_diagnostics_static
  flb_factorio_launch_static
  flb_factorio_modsets_static
  flb_factorio_saves_static
  ulk_static
)

add_library(flb_factorio_static STATIC runtime/factorio/binding/flb_api.c)
target_include_directories(flb_factorio_static PUBLIC include)
target_link_libraries(flb_factorio_static PUBLIC ulk_static flb_factorio_application_static)

add_library(flb_factorio_shared SHARED runtime/factorio/binding/flb_api.c)
target_include_directories(flb_factorio_shared PUBLIC include)
target_compile_definitions(flb_factorio_shared PRIVATE FLB_BUILD_SHARED)
target_link_libraries(flb_factorio_shared PUBLIC ulk_shared flb_factorio_application_static)
set_target_properties(flb_factorio_shared PROPERTIES OUTPUT_NAME flb_factorio WINDOWS_EXPORT_ALL_SYMBOLS ON)

add_library(flb_factorio ALIAS flb_factorio_static)

if(FLAUNCH_BUILD_NATIVE_APPS)
  add_executable(facman_cli
    apps/cli/main.c
    apps/cli/json_mode.c
    apps/cli/command_dispatch.cpp
  )
  if(WIN32)
    target_sources(facman_cli PRIVATE apps/cli/facman.manifest)
  endif()
  target_compile_features(facman_cli PRIVATE cxx_std_17)
  target_link_libraries(facman_cli PRIVATE facman_base_static flaunch_client_static flaunch_runtime_static ulk_static usk_static flb_factorio_static flb_factorio_launch_static flb_factorio_discovery_static flb_factorio_diagnostics_static flb_factorio_modsets_static flb_factorio_saves_static)
  set_target_properties(facman_cli PROPERTIES OUTPUT_NAME facman)

  add_executable(facman_tui
    apps/tui/tui_main.c
    apps/tui/tui_command_client.c
    apps/tui/tui_views.c
  )
  target_link_libraries(facman_tui PRIVATE flaunch_client_static flaunch_runtime_static ulk_static)
  set_target_properties(facman_tui PROPERTIES OUTPUT_NAME facman-tui)

  add_executable(facman_daemon
    apps/daemon/main.c
    apps/daemon/cancellation.c
    apps/daemon/platform_named_pipe_windows.c
    apps/daemon/platform_unix_socket.c
    apps/daemon/progress_events.c
    apps/daemon/rpc_json.c
  )
  target_link_libraries(facman_daemon PRIVATE flaunch_runtime_static ulk_static usk_static flb_factorio_static)
  set_target_properties(facman_daemon PROPERTIES OUTPUT_NAME facmand)
endif()

if(FLAUNCH_BUILD_TESTS)
  find_package(Threads REQUIRED)

  add_executable(miniz_dependency_smoke tests/native/miniz_dependency_smoke.c)
  target_link_libraries(miniz_dependency_smoke PRIVATE miniz_static)
  add_test(NAME miniz_dependency_smoke COMMAND miniz_dependency_smoke)

  add_executable(fl_archive_core_smoke tests/native/fl_archive_core_smoke.cpp)
  if(WIN32)
    target_sources(fl_archive_core_smoke PRIVATE apps/cli/facman.manifest)
  endif()
  target_compile_features(fl_archive_core_smoke PRIVATE cxx_std_17)
  target_link_libraries(fl_archive_core_smoke PRIVATE facman_archive_static)
  add_test(NAME fl_archive_core_smoke COMMAND fl_archive_core_smoke)

  add_executable(fl_archive_probe tests/native/fl_archive_probe.cpp)
  target_compile_features(fl_archive_probe PRIVATE cxx_std_17)
  target_link_libraries(fl_archive_probe PRIVATE facman_archive_static)

  add_executable(fl_archive_metadata_fuzz tests/native/fl_archive_metadata_fuzz.cpp)
  target_compile_features(fl_archive_metadata_fuzz PRIVATE cxx_std_17)
  target_link_libraries(fl_archive_metadata_fuzz PRIVATE facman_archive_static)

  add_executable(fl_archive_plan_fuzz tests/native/fl_archive_plan_fuzz.cpp)
  target_compile_features(fl_archive_plan_fuzz PRIVATE cxx_std_17)
  target_link_libraries(fl_archive_plan_fuzz PRIVATE facman_archive_static)

  add_executable(flb_command_bridge_smoke tests/native/flb_command_bridge_smoke.c)
  target_link_libraries(flb_command_bridge_smoke PRIVATE flaunch_client_static flb_factorio_static)
  add_test(NAME flb_command_bridge_smoke COMMAND flb_command_bridge_smoke)

  add_executable(fl_path_safety_smoke tests/native/fl_path_safety_smoke.cpp)
  target_compile_features(fl_path_safety_smoke PRIVATE cxx_std_17)
  target_link_libraries(fl_path_safety_smoke PRIVATE facman_base_static Threads::Threads)
  add_test(NAME fl_path_safety_smoke COMMAND fl_path_safety_smoke)

  add_executable(facman_isolation_lock_smoke tests/native/facman_isolation_lock_smoke.cpp)
  target_compile_features(facman_isolation_lock_smoke PRIVATE cxx_std_17)
  target_link_libraries(facman_isolation_lock_smoke PRIVATE flb_factorio_launch_static facman_base_static)
  add_test(NAME facman_isolation_lock_smoke COMMAND facman_isolation_lock_smoke)

  add_executable(facman_diagnostic_traversal_smoke tests/native/facman_diagnostic_traversal_smoke.cpp)
  if(WIN32)
    target_sources(facman_diagnostic_traversal_smoke PRIVATE apps/cli/facman.manifest)
  endif()
  target_compile_features(facman_diagnostic_traversal_smoke PRIVATE cxx_std_17)
  target_link_libraries(facman_diagnostic_traversal_smoke PRIVATE flb_factorio_diagnostics_static)
  add_test(NAME facman_diagnostic_traversal_smoke COMMAND facman_diagnostic_traversal_smoke)

  add_executable(facman_isolation_probe tests/native/facman_isolation_probe.cpp)
  if(WIN32)
    target_sources(facman_isolation_probe PRIVATE apps/cli/facman.manifest)
  endif()
  target_compile_features(facman_isolation_probe PRIVATE cxx_std_17)
  target_link_libraries(
    facman_isolation_probe
    PRIVATE
      flb_factorio_launch_static
      facman_base_static
      Threads::Threads
  )
endif()
