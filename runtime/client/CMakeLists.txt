# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

add_library(flaunch_client_static STATIC
  fl_command_client.c fl_command_client_cabi.c fl_command_client_cabi_execute.c
  fl_command_client_daemon.c fl_command_client_json.c)
target_include_directories(flaunch_client_static PUBLIC
  ${CMAKE_CURRENT_SOURCE_DIR} ${PROJECT_SOURCE_DIR}/include ${FLAUNCH_UNIVERSAL_LAUNCHER_ROOT}/include)
facman_apply_policies(flaunch_client_static)

set(FACMAN_CLIENT_SOURCES facman_client.cpp)
if(WIN32)
  list(APPEND FACMAN_CLIENT_SOURCES facman_process_windows.cpp)
else()
  list(APPEND FACMAN_CLIENT_SOURCES facman_process_posix.cpp)
endif()
add_library(facman_client_static STATIC ${FACMAN_CLIENT_SOURCES})
target_compile_features(facman_client_static PUBLIC cxx_std_17)
target_include_directories(facman_client_static PUBLIC ${CMAKE_CURRENT_SOURCE_DIR})
target_link_libraries(facman_client_static PUBLIC
  facman_core_static flaunch_client_static flaunch_runtime_static flb_factorio_static)
add_library(facman::client ALIAS facman_client_static)
facman_apply_policies(facman_client_static)
