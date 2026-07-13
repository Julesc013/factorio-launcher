# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

cmake_minimum_required(VERSION 3.20)
project(facman_installed_consumer LANGUAGES C)

find_package(FacMan 0.1 CONFIG REQUIRED)

add_executable(facman_sdk_consumer main.c)
target_link_libraries(facman_sdk_consumer PRIVATE FacMan::flb)

add_executable(facman_sdk_legacy_consumer legacy_main.c)
target_include_directories(facman_sdk_legacy_consumer PRIVATE ${CMAKE_CURRENT_SOURCE_DIR})
target_link_libraries(facman_sdk_legacy_consumer PRIVATE FacMan::flb)
