# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

add_library(facman_base_static STATIC fl_local_operation_lock.cpp fl_path_safety.cpp fl_sha256.cpp)
target_include_directories(facman_base_static PUBLIC ${CMAKE_CURRENT_SOURCE_DIR})
target_include_directories(facman_base_static PRIVATE ${PROJECT_SOURCE_DIR}/runtime/platform)
target_compile_features(facman_base_static PUBLIC cxx_std_17)
facman_apply_policies(facman_base_static)

if(FACMAN_ENABLE_COVERAGE AND NOT MSVC)
  # Atomic coverage counters make unoptimized SHA-256 compression expensive.
  # Keep instrumentation and the product's finite package-read budget intact.
  set_property(SOURCE fl_sha256.cpp APPEND PROPERTY COMPILE_OPTIONS -O2)
endif()
