# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

add_library(facman_frontend_session_static STATIC
  frontend_session.cpp)
target_compile_features(facman_frontend_session_static PUBLIC cxx_std_17)
target_include_directories(facman_frontend_session_static PUBLIC
  ${CMAKE_CURRENT_SOURCE_DIR})
target_link_libraries(facman_frontend_session_static PUBLIC
  facman_client_static)
facman_apply_policies(facman_frontend_session_static)
add_library(facman::frontend_session ALIAS facman_frontend_session_static)
