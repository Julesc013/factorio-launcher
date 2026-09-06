# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

add_library(facman_windows_integration_static STATIC
  windows_integration.cpp windows_integration_win32.cpp)
target_compile_features(facman_windows_integration_static PUBLIC cxx_std_17)
target_include_directories(facman_windows_integration_static PUBLIC ${CMAKE_CURRENT_SOURCE_DIR})
target_link_libraries(facman_windows_integration_static PUBLIC
  facman_core_static Advapi32 KtmW32 Ole32 Shell32)
facman_apply_policies(facman_windows_integration_static)

add_executable(facman_setup main.cpp facman_setup.manifest)
target_compile_features(facman_setup PRIVATE cxx_std_17)
target_include_directories(facman_setup PRIVATE ${PROJECT_SOURCE_DIR}/runtime/core/generated)
target_link_libraries(facman_setup PRIVATE
  facman_windows_integration_static
  facman_self_setup_static
  facman_platform_static
  Advapi32
  Ole32
  Shell32
)
set_target_properties(facman_setup PROPERTIES OUTPUT_NAME FacManSetup)
add_executable(facman::setup ALIAS facman_setup)
facman_apply_policies(facman_setup)

install(TARGETS facman_setup
  RUNTIME DESTINATION bin
  COMPONENT SelfSetup)
