# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

add_library(flaunch_runtime_static STATIC
  fl_runtime_component.cpp fl_runtime_extract.c fl_runtime_locator.c fl_runtime_manifest.c fl_runtime_verify.cpp)
target_include_directories(flaunch_runtime_static PUBLIC ${CMAKE_CURRENT_SOURCE_DIR} PRIVATE ${PROJECT_SOURCE_DIR}/runtime/base)
target_compile_features(flaunch_runtime_static PUBLIC cxx_std_17)
target_link_libraries(flaunch_runtime_static PRIVATE facman_base_static)
add_library(facman::package ALIAS flaunch_runtime_static)
facman_apply_policies(flaunch_runtime_static)
