# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

add_library(facman_preferences_static STATIC fl_preferences.cpp)
target_include_directories(facman_preferences_static PUBLIC
  ${CMAKE_CURRENT_SOURCE_DIR}
  ${PROJECT_SOURCE_DIR}/runtime/base
  ${PROJECT_SOURCE_DIR}/runtime/core
  ${PROJECT_SOURCE_DIR}/runtime/core/json
  ${PROJECT_SOURCE_DIR}/runtime/platform
  ${PROJECT_SOURCE_DIR}/runtime/transaction)
target_compile_features(facman_preferences_static PUBLIC cxx_std_17)
target_link_libraries(facman_preferences_static PUBLIC
  facman_core_static facman_platform_static facman_transaction_static facman_base_static)
add_library(facman::preferences ALIAS facman_preferences_static)
facman_apply_policies(facman_preferences_static)
