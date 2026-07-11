# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

add_library(facman_platform_static STATIC fl_file_io.cpp fl_system_services.cpp)
target_include_directories(facman_platform_static PUBLIC ${CMAKE_CURRENT_SOURCE_DIR} ${PROJECT_SOURCE_DIR}/runtime/core)
target_compile_features(facman_platform_static PUBLIC cxx_std_17)
if(WIN32)
  target_link_libraries(facman_platform_static PUBLIC Bcrypt)
endif()
add_library(facman::platform ALIAS facman_platform_static)
facman_apply_policies(facman_platform_static)
