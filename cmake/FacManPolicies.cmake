# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

add_library(facman_warnings INTERFACE)
add_library(facman_hardening INTERFACE)
add_library(facman_sanitizers INTERFACE)
add_library(facman_coverage INTERFACE)

if(FACMAN_ENABLE_CLANG_TIDY)
  find_program(FACMAN_CLANG_TIDY_EXE NAMES clang-tidy REQUIRED)
  set(CMAKE_C_CLANG_TIDY "${FACMAN_CLANG_TIDY_EXE}" CACHE STRING "C clang-tidy command" FORCE)
  set(CMAKE_CXX_CLANG_TIDY "${FACMAN_CLANG_TIDY_EXE}" CACHE STRING "C++ clang-tidy command" FORCE)
endif()

if(MSVC)
  # C4996 rejects portable C/POSIX APIs such as getenv in favor of MSVC-only
  # replacements. Keep the cross-platform API and enforce every other /W4
  # diagnostic through /WX in CI.
  # /FS serializes compiler PDB writes for multi-source targets. Without it,
  # parallel MSBuild can fail nondeterministically with C1041 while several
  # cl.exe processes update the target program database.
  target_compile_options(facman_warnings INTERFACE /W4 /wd4996 /FS)
  target_compile_options(facman_hardening INTERFACE /guard:cf)
  target_link_options(facman_hardening INTERFACE /guard:cf /DYNAMICBASE)
  if(FACMAN_WARNINGS_AS_ERRORS)
    target_compile_options(facman_warnings INTERFACE /WX)
  endif()
else()
  target_compile_options(facman_warnings INTERFACE -Wall -Wextra -Wpedantic)
  target_compile_options(facman_hardening INTERFACE -fstack-protector-strong)
  if(FACMAN_WARNINGS_AS_ERRORS)
    target_compile_options(facman_warnings INTERFACE -Werror)
  endif()
  if(FACMAN_ENABLE_SANITIZERS)
    target_compile_options(facman_sanitizers INTERFACE -fsanitize=address,undefined -fno-omit-frame-pointer)
    target_link_options(facman_sanitizers INTERFACE -fsanitize=address,undefined)
  endif()
  if(FACMAN_ENABLE_COVERAGE)
    target_compile_options(facman_coverage INTERFACE --coverage)
    target_link_options(facman_coverage INTERFACE --coverage)
  endif()
endif()

function(facman_apply_policies target)
  target_link_libraries(${target} PRIVATE facman_warnings facman_hardening facman_sanitizers facman_coverage)
endfunction()

function(facman_add_libfuzzer target source)
  if(NOT FACMAN_ENABLE_LIBFUZZER)
    return()
  endif()
  if(NOT CMAKE_CXX_COMPILER_ID MATCHES "Clang")
    message(FATAL_ERROR "FACMAN_ENABLE_LIBFUZZER requires Clang")
  endif()
  add_executable(${target} ${source})
  target_compile_features(${target} PRIVATE cxx_std_17)
  target_compile_options(${target} PRIVATE -fsanitize=fuzzer,address,undefined -fno-omit-frame-pointer)
  target_link_options(${target} PRIVATE -fsanitize=fuzzer,address,undefined)
endfunction()
