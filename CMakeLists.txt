cmake_minimum_required(VERSION 3.16)
project(factorio_launcher LANGUAGES C CXX)

option(FLAUNCH_BUILD_NATIVE_APPS "Build native CLI/TUI/daemon scaffolds" ON)

set(FLAUNCH_RUNTIME_SOURCES
  source/runtime/fl_runtime_component.c
  source/runtime/fl_runtime_extract.c
  source/runtime/fl_runtime_locator.c
  source/runtime/fl_runtime_manifest.c
  source/runtime/fl_runtime_verify.c
)

set(FLAUNCH_CLIENT_SOURCES
  source/client/fl_command_client.c
  source/client/fl_command_client_cabi.c
  source/client/fl_command_client_daemon.c
  source/client/fl_command_client_json.c
)

add_library(flaunch_runtime_static STATIC ${FLAUNCH_RUNTIME_SOURCES})
target_include_directories(flaunch_runtime_static PUBLIC source/runtime)

add_library(flaunch_client_static STATIC ${FLAUNCH_CLIENT_SOURCES})
target_include_directories(flaunch_client_static PUBLIC source/client include)

add_library(usk_static STATIC source/usk/kernel/usk_api.c)
target_include_directories(usk_static PUBLIC include)

add_library(usk_shared SHARED source/usk/kernel/usk_api.c)
target_include_directories(usk_shared PUBLIC include)
set_target_properties(usk_shared PROPERTIES OUTPUT_NAME usk WINDOWS_EXPORT_ALL_SYMBOLS ON)

add_library(ulk_static STATIC source/ulk/kernel/ulk_api.c)
target_include_directories(ulk_static PUBLIC include)

add_library(ulk_shared SHARED source/ulk/kernel/ulk_api.c)
target_include_directories(ulk_shared PUBLIC include)
set_target_properties(ulk_shared PROPERTIES OUTPUT_NAME ulk WINDOWS_EXPORT_ALL_SYMBOLS ON)

add_library(flb_factorio_static STATIC source/factorio/binding/flb_api.c)
target_include_directories(flb_factorio_static PUBLIC include)
target_link_libraries(flb_factorio_static PUBLIC ulk_static)

add_library(flb_factorio_shared SHARED source/factorio/binding/flb_api.c)
target_include_directories(flb_factorio_shared PUBLIC include)
target_link_libraries(flb_factorio_shared PUBLIC ulk_shared)
set_target_properties(flb_factorio_shared PROPERTIES OUTPUT_NAME flb_factorio WINDOWS_EXPORT_ALL_SYMBOLS ON)

add_library(ulk ALIAS ulk_static)
add_library(usk ALIAS usk_static)
add_library(flb_factorio ALIAS flb_factorio_static)

if(FLAUNCH_BUILD_NATIVE_APPS)
  add_executable(flaunch_cli
    source/apps/factorio_cli/main.c
    source/apps/factorio_cli/json_mode.c
    source/apps/factorio_cli/command_dispatch.c
  )
  target_link_libraries(flaunch_cli PRIVATE flaunch_client_static flaunch_runtime_static ulk_static flb_factorio_static)
  set_target_properties(flaunch_cli PROPERTIES OUTPUT_NAME flaunch)

  add_executable(flaunch_tui
    source/apps/factorio_tui/tui_main.c
    source/apps/factorio_tui/tui_command_client.c
    source/apps/factorio_tui/tui_views.c
  )
  target_link_libraries(flaunch_tui PRIVATE flaunch_client_static flaunch_runtime_static ulk_static)
  set_target_properties(flaunch_tui PROPERTIES OUTPUT_NAME flaunch-tui)

  add_executable(flaunch_daemon
    source/apps/factorio_daemon/main.c
    source/apps/factorio_daemon/cancellation.c
    source/apps/factorio_daemon/platform_named_pipe_windows.c
    source/apps/factorio_daemon/platform_unix_socket.c
    source/apps/factorio_daemon/progress_events.c
    source/apps/factorio_daemon/rpc_json.c
  )
  target_link_libraries(flaunch_daemon PRIVATE flaunch_runtime_static ulk_static usk_static flb_factorio_static)
  set_target_properties(flaunch_daemon PROPERTIES OUTPUT_NAME flaunchd)
endif()
