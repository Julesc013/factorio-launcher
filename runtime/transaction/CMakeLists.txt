# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

add_library(facman_transaction_static STATIC fl_transaction.cpp)
target_include_directories(facman_transaction_static PUBLIC
  ${CMAKE_CURRENT_SOURCE_DIR} ${PROJECT_SOURCE_DIR}/runtime/archive ${PROJECT_SOURCE_DIR}/runtime/base)
target_compile_features(facman_transaction_static PUBLIC cxx_std_17)
target_link_libraries(facman_transaction_static PUBLIC facman_archive_static facman_base_static facman_workspace_static)
facman_apply_policies(facman_transaction_static)
