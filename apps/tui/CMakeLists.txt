# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

add_library(facman_tui_static STATIC
  linear_renderer.cpp
  terminal_capabilities.cpp
  terminal_text.cpp
  tui_command_client.cpp
  tui_guided_forms.cpp
  tui_host.cpp
  tui_product_model.cpp
  tui_product_renderer.cpp
  tui_product_shell.cpp
  tui_views.cpp)
target_compile_features(facman_tui_static PUBLIC cxx_std_17)
target_include_directories(facman_tui_static PUBLIC
  ${CMAKE_CURRENT_SOURCE_DIR}
  ${PROJECT_SOURCE_DIR}/runtime/core/generated)
target_link_libraries(facman_tui_static PUBLIC
  facman_frontend_session_static
  facman_client_static)
facman_apply_policies(facman_tui_static)
add_library(facman::tui ALIAS facman_tui_static)

if(FACMAN_BUILD_TUI_COMPAT)
  add_executable(facman_tui tui_main.cpp)
  if(WIN32)
    target_sources(facman_tui PRIVATE ${PROJECT_SOURCE_DIR}/apps/cli/facman.manifest)
  endif()
  target_compile_features(facman_tui PRIVATE cxx_std_17)
  target_link_libraries(facman_tui PRIVATE facman_tui_static)
  set_target_properties(facman_tui PROPERTIES OUTPUT_NAME facman-tui)
  facman_apply_policies(facman_tui)
endif()
