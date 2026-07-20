# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

add_executable(facman_cli main.c command_dispatch.cpp)
if(WIN32)
  target_sources(facman_cli PRIVATE facman.manifest)
endif()
target_compile_features(facman_cli PRIVATE cxx_std_17)
target_compile_definitions(facman_cli PRIVATE
  FACMAN_BUILD_SOURCE_REVISION="${FACMAN_SOURCE_REVISION}"
  FACMAN_BUILD_CONFIGURATION="$<CONFIG>")
target_include_directories(facman_cli PRIVATE ${PROJECT_SOURCE_DIR}/runtime/core/generated)
target_link_libraries(facman_cli PRIVATE facman_client_static)
set_target_properties(facman_cli PROPERTIES OUTPUT_NAME facman)
add_executable(facman::cli ALIAS facman_cli)
facman_apply_policies(facman_cli)
