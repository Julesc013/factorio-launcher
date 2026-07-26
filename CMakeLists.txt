cmake_minimum_required(VERSION 3.20)
project(facman VERSION 0.1.0 LANGUAGES C CXX)

execute_process(
  COMMAND git rev-parse HEAD
  WORKING_DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}"
  OUTPUT_VARIABLE FACMAN_SOURCE_REVISION
  OUTPUT_STRIP_TRAILING_WHITESPACE
  ERROR_QUIET)
if(NOT FACMAN_SOURCE_REVISION)
  set(FACMAN_SOURCE_REVISION "unknown")
endif()

include(cmake/FacManOptions.cmake)
include(cmake/FacManPolicies.cmake)

set(CMAKE_POSITION_INDEPENDENT_CODE ON)
set(CMAKE_RUNTIME_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR})
set(CMAKE_LIBRARY_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR})
set(CMAKE_ARCHIVE_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR})

function(facman_append_env_candidate out_var env_name suffix)
  if(DEFINED ENV{${env_name}} AND NOT "$ENV{${env_name}}" STREQUAL "")
    file(TO_CMAKE_PATH "$ENV{${env_name}}" env_path)
    list(APPEND ${out_var} "${env_path}${suffix}")
    set(${out_var} "${${out_var}}" PARENT_SCOPE)
  endif()
endfunction()

function(facman_find_repo_root out_var repo_name specific_env)
  set(candidates)
  facman_append_env_candidate(candidates "${specific_env}" "")
  facman_append_env_candidate(candidates "FLAUNCH_UNIVERSAL_ROOT" "/${repo_name}")
  facman_append_env_candidate(candidates "FLAUNCH_WORKSPACE_ROOT" "/Universal/${repo_name}")
  facman_append_env_candidate(candidates "FLAUNCH_WORKSPACE_ROOT" "/${repo_name}")
  list(APPEND candidates
    "${CMAKE_CURRENT_SOURCE_DIR}/external/${repo_name}"
    "${CMAKE_CURRENT_SOURCE_DIR}/../${repo_name}"
    "${CMAKE_CURRENT_SOURCE_DIR}/../../Universal/${repo_name}"
    "${CMAKE_CURRENT_SOURCE_DIR}/../../${repo_name}"
    "${CMAKE_CURRENT_SOURCE_DIR}/../../../Universal/${repo_name}"
    "${CMAKE_CURRENT_SOURCE_DIR}/../../../${repo_name}")
  foreach(candidate IN LISTS candidates)
    if(EXISTS "${candidate}/CMakeLists.txt")
      set(${out_var} "${candidate}" PARENT_SCOPE)
      return()
    endif()
  endforeach()
  list(GET candidates 0 fallback)
  set(${out_var} "${fallback}" PARENT_SCOPE)
endfunction()

function(facman_select_repo_root cache_var repo_name specific_env)
  if(NOT DEFINED ${cache_var} OR NOT EXISTS "${${cache_var}}/CMakeLists.txt")
    facman_find_repo_root(selected_path "${repo_name}" "${specific_env}")
    if(DEFINED ${cache_var} AND NOT "${${cache_var}}" STREQUAL "" AND NOT EXISTS "${${cache_var}}/CMakeLists.txt")
      message(STATUS "Ignoring unavailable ${repo_name} path: ${${cache_var}}")
    endif()
    set(${cache_var} "${selected_path}" CACHE PATH "Path to the ${repo_name} repository" FORCE)
  endif()
endfunction()

facman_select_repo_root(FLAUNCH_UNIVERSAL_SETUP_ROOT "universal-setup" "FLAUNCH_UNIVERSAL_SETUP_ROOT")
facman_select_repo_root(FLAUNCH_UNIVERSAL_LAUNCHER_ROOT "universal-launcher" "FLAUNCH_UNIVERSAL_LAUNCHER_ROOT")

function(facman_git_revision out_var repo_root label)
  execute_process(
    COMMAND git rev-parse HEAD
    WORKING_DIRECTORY "${repo_root}"
    OUTPUT_VARIABLE revision
    OUTPUT_STRIP_TRAILING_WHITESPACE
    ERROR_QUIET
    RESULT_VARIABLE result)
  if(NOT result EQUAL 0 OR NOT revision MATCHES "^[0-9a-fA-F]+$")
    message(FATAL_ERROR "Cannot resolve ${label} Git revision at ${repo_root}")
  endif()
  string(TOLOWER "${revision}" revision)
  set(${out_var} "${revision}" PARENT_SCOPE)
endfunction()

function(facman_workspace_lock_pin out_var component_id)
  file(STRINGS
    "${CMAKE_CURRENT_SOURCE_DIR}/release/index/workspace_lock.v1.toml"
    lock_lines)
  set(active_component "")
  set(locked_pin "")
  foreach(line IN LISTS lock_lines)
    if(line MATCHES "^id = \"([^\"]+)\"$")
      set(active_component "${CMAKE_MATCH_1}")
    elseif(
      active_component STREQUAL component_id
      AND line MATCHES "^pin = \"([0-9a-f]+)\"$")
      set(locked_pin "${CMAKE_MATCH_1}")
      break()
    endif()
  endforeach()
  if(NOT locked_pin)
    message(FATAL_ERROR "Workspace lock has no pin for ${component_id}")
  endif()
  set(${out_var} "${locked_pin}" PARENT_SCOPE)
endfunction()

facman_git_revision(
  FACMAN_UNIVERSAL_LAUNCHER_REVISION
  "${FLAUNCH_UNIVERSAL_LAUNCHER_ROOT}"
  "Universal Launcher")
facman_git_revision(
  FACMAN_UNIVERSAL_SETUP_REVISION
  "${FLAUNCH_UNIVERSAL_SETUP_ROOT}"
  "Universal Setup")
facman_workspace_lock_pin(FACMAN_LOCKED_UNIVERSAL_LAUNCHER_REVISION universal_launcher)
facman_workspace_lock_pin(FACMAN_LOCKED_UNIVERSAL_SETUP_REVISION universal_setup)
if(NOT FACMAN_UNIVERSAL_LAUNCHER_REVISION STREQUAL FACMAN_LOCKED_UNIVERSAL_LAUNCHER_REVISION)
  message(FATAL_ERROR
    "Universal Launcher checkout ${FACMAN_UNIVERSAL_LAUNCHER_REVISION} "
    "does not match workspace lock ${FACMAN_LOCKED_UNIVERSAL_LAUNCHER_REVISION}")
endif()
if(NOT FACMAN_UNIVERSAL_SETUP_REVISION STREQUAL FACMAN_LOCKED_UNIVERSAL_SETUP_REVISION)
  message(FATAL_ERROR
    "Universal Setup checkout ${FACMAN_UNIVERSAL_SETUP_REVISION} "
    "does not match workspace lock ${FACMAN_LOCKED_UNIVERSAL_SETUP_REVISION}")
endif()

set(FACMAN_GENERATED_INCLUDE_DIR "${CMAKE_CURRENT_BINARY_DIR}/generated/include")
file(MAKE_DIRECTORY "${FACMAN_GENERATED_INCLUDE_DIR}/facman")
configure_file(
  cmake/FacManBuildIdentity.hpp.in
  "${FACMAN_GENERATED_INCLUDE_DIR}/facman/build_identity.hpp"
  @ONLY)

if(FACMAN_BUILD_TESTS)
  enable_testing()
endif()

add_subdirectory(external)
add_subdirectory(runtime/core)
add_subdirectory(runtime/platform)
add_subdirectory(runtime/base)
add_subdirectory(runtime/workspace)
add_subdirectory(runtime/archive)
add_subdirectory(runtime/transaction)
add_subdirectory(runtime/preferences)
add_subdirectory(runtime/package)

if(FACMAN_WITH_SETUP AND NOT TARGET usk_static)
  if(EXISTS "${FLAUNCH_UNIVERSAL_SETUP_ROOT}/CMakeLists.txt")
    add_subdirectory("${FLAUNCH_UNIVERSAL_SETUP_ROOT}" "${CMAKE_CURRENT_BINARY_DIR}/universal-setup")
  else()
    message(FATAL_ERROR "universal-setup is required when FACMAN_WITH_SETUP=ON")
  endif()
endif()
if(NOT TARGET ulk_static)
  if(EXISTS "${FLAUNCH_UNIVERSAL_LAUNCHER_ROOT}/CMakeLists.txt")
    add_subdirectory("${FLAUNCH_UNIVERSAL_LAUNCHER_ROOT}" "${CMAKE_CURRENT_BINARY_DIR}/universal-launcher")
  else()
    message(FATAL_ERROR "universal-launcher is required")
  endif()
endif()

add_subdirectory(runtime/factorio)
add_subdirectory(runtime/client)
add_subdirectory(apps)
if(FACMAN_BUILD_TESTS)
  add_subdirectory(tests/native)
endif()

include(cmake/FacManInstall.cmake)
