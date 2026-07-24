# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

set(FACMAN_PLATFORM_SOURCES fl_file_io.cpp fl_process_supervisor.cpp fl_system_services.cpp)
if(WIN32)
  list(APPEND FACMAN_PLATFORM_SOURCES
    fl_process_supervisor_windows.cpp fl_random_windows.cpp windows/fl_user_paths_windows.cpp)
elseif(APPLE)
  list(APPEND FACMAN_PLATFORM_SOURCES
    fl_process_supervisor_posix.cpp fl_random_macos.cpp macos/fl_user_paths_macos.cpp)
elseif(CMAKE_SYSTEM_NAME STREQUAL "Linux")
  list(APPEND FACMAN_PLATFORM_SOURCES
    fl_process_supervisor_posix.cpp fl_random_linux.cpp linux/fl_user_paths_linux.cpp)
else()
  message(FATAL_ERROR "FacMan secure randomness is not implemented for ${CMAKE_SYSTEM_NAME}")
endif()
add_library(facman_platform_static STATIC ${FACMAN_PLATFORM_SOURCES})
target_include_directories(facman_platform_static PUBLIC ${CMAKE_CURRENT_SOURCE_DIR} ${PROJECT_SOURCE_DIR}/runtime/core)
target_compile_features(facman_platform_static PUBLIC cxx_std_17)
if(WIN32)
  target_link_libraries(facman_platform_static PUBLIC
    Advapi32 Bcrypt Shell32 Ole32)
endif()
find_package(Threads REQUIRED)
target_link_libraries(facman_platform_static PUBLIC Threads::Threads)
add_library(facman::platform ALIAS facman_platform_static)
facman_apply_policies(facman_platform_static)
