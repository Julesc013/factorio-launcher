# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

add_library(facman_archive_static STATIC
  fl_archive_platform.cpp fl_archive_policy.cpp fl_archive_reader.cpp fl_archive_writer.cpp)
target_include_directories(facman_archive_static PUBLIC ${CMAKE_CURRENT_SOURCE_DIR})
target_compile_features(facman_archive_static PUBLIC cxx_std_17)
target_link_libraries(facman_archive_static PUBLIC facman_base_static facman_platform_static miniz_static)
add_library(facman::archive ALIAS facman_archive_static)
facman_apply_policies(facman_archive_static)
