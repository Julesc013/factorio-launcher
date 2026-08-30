# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

add_library(facman_self_setup_static STATIC facman_self_setup.cpp)
target_include_directories(facman_self_setup_static PUBLIC ${CMAKE_CURRENT_SOURCE_DIR})
target_compile_features(facman_self_setup_static PUBLIC cxx_std_17)
target_compile_definitions(facman_self_setup_static PRIVATE
  FACMAN_SELF_SETUP_PROVIDER_REVISION="${FACMAN_UNIVERSAL_SETUP_REVISION}")
target_link_libraries(facman_self_setup_static PUBLIC
  facman_base_static
  facman_core_static
  facman_platform_static
  FacManProvider::Setup)
add_library(facman::self_setup ALIAS facman_self_setup_static)
facman_apply_policies(facman_self_setup_static)
