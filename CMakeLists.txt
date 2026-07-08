cmake_minimum_required(VERSION 3.16)
project(facman LANGUAGES C CXX)

option(FLAUNCH_BUILD_NATIVE_APPS "Build native CLI/TUI/daemon scaffolds" ON)
set(FLAUNCH_UNIVERSAL_SETUP_ROOT
  "${CMAKE_CURRENT_SOURCE_DIR}/../universal-setup"
  CACHE PATH "Path to the universal-setup repository"
)
set(FLAUNCH_UNIVERSAL_LAUNCHER_ROOT
  "${CMAKE_CURRENT_SOURCE_DIR}/../universal-launcher"
  CACHE PATH "Path to the universal-launcher repository"
)

if(NOT TARGET usk_static)
  if(EXISTS "${FLAUNCH_UNIVERSAL_SETUP_ROOT}/CMakeLists.txt")
    add_subdirectory("${FLAUNCH_UNIVERSAL_SETUP_ROOT}" "${CMAKE_CURRENT_BINARY_DIR}/universal-setup")
  else()
    message(FATAL_ERROR "universal-setup is required; set FLAUNCH_UNIVERSAL_SETUP_ROOT")
  endif()
endif()

if(NOT TARGET ulk_static)
  if(EXISTS "${FLAUNCH_UNIVERSAL_LAUNCHER_ROOT}/CMakeLists.txt")
    add_subdirectory("${FLAUNCH_UNIVERSAL_LAUNCHER_ROOT}" "${CMAKE_CURRENT_BINARY_DIR}/universal-launcher")
  else()
    message(FATAL_ERROR "universal-launcher is required; set FLAUNCH_UNIVERSAL_LAUNCHER_ROOT")
  endif()
endif()

set(FLAUNCH_RUNTIME_SOURCES
  runtime/package/fl_runtime_component.c
  runtime/package/fl_runtime_extract.c
  runtime/package/fl_runtime_locator.c
  runtime/package/fl_runtime_manifest.c
  runtime/package/fl_runtime_verify.c
)

set(FLAUNCH_CLIENT_SOURCES
  runtime/client/fl_command_client.c
  runtime/client/fl_command_client_cabi.c
  runtime/client/fl_command_client_daemon.c
  runtime/client/fl_command_client_json.c
)

add_library(flaunch_runtime_static STATIC ${FLAUNCH_RUNTIME_SOURCES})
target_include_directories(flaunch_runtime_static PUBLIC runtime/package)

add_library(flaunch_client_static STATIC ${FLAUNCH_CLIENT_SOURCES})
target_include_directories(flaunch_client_static PUBLIC runtime/client include)

add_library(flb_factorio_static STATIC runtime/factorio/binding/flb_api.c)
target_include_directories(flb_factorio_static PUBLIC include)
target_link_libraries(flb_factorio_static PUBLIC ulk_static)

add_library(flb_factorio_shared SHARED runtime/factorio/binding/flb_api.c)
target_include_directories(flb_factorio_shared PUBLIC include)
target_link_libraries(flb_factorio_shared PUBLIC ulk_shared)
set_target_properties(flb_factorio_shared PROPERTIES OUTPUT_NAME flb_factorio WINDOWS_EXPORT_ALL_SYMBOLS ON)

add_library(flb_factorio ALIAS flb_factorio_static)

if(FLAUNCH_BUILD_NATIVE_APPS)
  add_executable(facman_cli
    apps/cli/main.c
    apps/cli/json_mode.c
    apps/cli/command_dispatch.cpp
  )
  target_compile_features(facman_cli PRIVATE cxx_std_17)
  target_link_libraries(facman_cli PRIVATE flaunch_client_static flaunch_runtime_static ulk_static flb_factorio_static)
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
