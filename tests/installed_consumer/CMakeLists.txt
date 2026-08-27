# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

cmake_minimum_required(VERSION 3.20)
project(facman_installed_consumer LANGUAGES C)

option(
  FACMAN_CONSUMER_SANITIZERS
  "Link the relocated SDK consumer with the parent build's sanitizer runtime"
  OFF)

find_package(FacMan 0.1 CONFIG REQUIRED)

add_executable(facman_sdk_consumer main.c)
target_link_libraries(facman_sdk_consumer PRIVATE FacMan::flb)

add_executable(facman_sdk_legacy_consumer legacy_main.c)
target_include_directories(facman_sdk_legacy_consumer PRIVATE ${CMAKE_CURRENT_SOURCE_DIR})
target_link_libraries(facman_sdk_legacy_consumer PRIVATE FacMan::flb)

if(FACMAN_CONSUMER_SANITIZERS)
  if(NOT CMAKE_C_COMPILER_ID MATCHES "GNU|Clang")
    message(FATAL_ERROR "FACMAN_CONSUMER_SANITIZERS requires GCC or Clang")
  endif()
  foreach(target IN ITEMS facman_sdk_consumer facman_sdk_legacy_consumer)
    target_compile_options(${target} PRIVATE -fsanitize=address,undefined -fno-omit-frame-pointer)
    target_link_options(${target} PRIVATE -fsanitize=address,undefined)
  endforeach()
endif()
