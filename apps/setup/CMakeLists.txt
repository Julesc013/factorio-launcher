# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

add_executable(facman_setup main.cpp facman_setup.manifest)
target_compile_features(facman_setup PRIVATE cxx_std_17)
target_include_directories(facman_setup PRIVATE ${PROJECT_SOURCE_DIR}/runtime/core/generated)
target_link_libraries(facman_setup PRIVATE facman_self_setup_static facman_platform_static)
set_target_properties(facman_setup PROPERTIES OUTPUT_NAME FacManSetup)
add_executable(facman::setup ALIAS facman_setup)
facman_apply_policies(facman_setup)

install(TARGETS facman_setup
  RUNTIME DESTINATION bin
  COMPONENT SelfSetup)
