# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

# Product resource custody is below both resource parsing and runtime verification.
add_library(facman_package_identity_static STATIC
  fl_product_resource_identity.cpp fl_product_resource_windows.cpp fl_product_resource_unix.cpp
  fl_process_image.cpp fl_runtime_component.cpp)
target_include_directories(facman_package_identity_static PUBLIC ${CMAKE_CURRENT_SOURCE_DIR})
target_compile_features(facman_package_identity_static PUBLIC cxx_std_17)
target_link_libraries(facman_package_identity_static PUBLIC
  facman_base_static facman_core_static facman_platform_static)
facman_apply_policies(facman_package_identity_static)

add_library(flaunch_runtime_static STATIC
  fl_runtime_extract.c fl_runtime_locator.c fl_runtime_manifest.c fl_runtime_verify.cpp)
target_include_directories(flaunch_runtime_static PUBLIC ${CMAKE_CURRENT_SOURCE_DIR} PRIVATE
  ${PROJECT_SOURCE_DIR}/runtime/base
  ${PROJECT_SOURCE_DIR}/runtime/core/json)
target_compile_features(flaunch_runtime_static PUBLIC cxx_std_17)
target_link_libraries(flaunch_runtime_static PRIVATE
  facman_package_identity_static facman_resources_static)
add_library(facman::package ALIAS flaunch_runtime_static)
facman_apply_policies(flaunch_runtime_static)
