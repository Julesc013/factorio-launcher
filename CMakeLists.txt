cmake_minimum_required(VERSION 3.20)
project(facman VERSION 0.1.0 LANGUAGES C CXX)

execute_process(
  COMMAND git rev-parse HEAD
  WORKING_DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}"
  OUTPUT_VARIABLE FACMAN_SOURCE_REVISION
  OUTPUT_STRIP_TRAILING_WHITESPACE
  ERROR_VARIABLE FACMAN_SOURCE_REVISION_ERROR
  RESULT_VARIABLE FACMAN_SOURCE_REVISION_RESULT)
string(LENGTH "${FACMAN_SOURCE_REVISION}" FACMAN_SOURCE_REVISION_LENGTH)
if(
  NOT FACMAN_SOURCE_REVISION_RESULT EQUAL 0
  OR NOT FACMAN_SOURCE_REVISION MATCHES "^[0-9a-fA-F]+$"
  OR NOT FACMAN_SOURCE_REVISION_LENGTH EQUAL 40)
  message(FATAL_ERROR
    "Cannot resolve the exact Factorio Launcher Git revision: "
    "${FACMAN_SOURCE_REVISION_ERROR}")
endif()
string(TOLOWER "${FACMAN_SOURCE_REVISION}" FACMAN_SOURCE_REVISION)
execute_process(
  COMMAND git status --porcelain=v1 --untracked-files=normal
  WORKING_DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}"
  OUTPUT_VARIABLE FACMAN_SOURCE_STATUS
  OUTPUT_STRIP_TRAILING_WHITESPACE
  ERROR_VARIABLE FACMAN_SOURCE_STATUS_ERROR
  RESULT_VARIABLE FACMAN_SOURCE_STATUS_RESULT)
if(NOT FACMAN_SOURCE_STATUS_RESULT EQUAL 0)
  message(FATAL_ERROR
    "Cannot inspect Factorio Launcher source status: "
    "${FACMAN_SOURCE_STATUS_ERROR}")
endif()
if(FACMAN_SOURCE_STATUS)
  set(FACMAN_SOURCE_DIRTY true)
else()
  set(FACMAN_SOURCE_DIRTY false)
endif()

include(cmake/FacManOptions.cmake)
include(cmake/FacManPolicies.cmake)

set(CMAKE_POSITION_INDEPENDENT_CODE ON)
set(CMAKE_RUNTIME_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR})
set(CMAKE_LIBRARY_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR})
set(CMAKE_ARCHIVE_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR})

include(cmake/FacManProviders.cmake)
facman_configure_providers()

if(FACMAN_PROVIDER_CONFORMANCE_ONLY)
  set(FACMAN_PROVIDER_CONFORMANCE_IDENTITY true)
else()
  set(FACMAN_PROVIDER_CONFORMANCE_IDENTITY false)
endif()
if(FACMAN_PROVIDER_SDK_CONSUMPTION_CANDIDATE)
  set(FACMAN_PROVIDER_SDK_CANDIDATE_IDENTITY true)
else()
  set(FACMAN_PROVIDER_SDK_CANDIDATE_IDENTITY false)
endif()
if(FACMAN_PROVIDER_RELEASE_IDENTITY_COHERENT)
  set(FACMAN_PROVIDER_RELEASE_IDENTITY_COHERENCE true)
else()
  set(FACMAN_PROVIDER_RELEASE_IDENTITY_COHERENCE false)
endif()

string(CONCAT FACMAN_BUILD_IDENTITY
  "facman=${FACMAN_SOURCE_REVISION};"
  "universal_launcher=${FACMAN_UNIVERSAL_LAUNCHER_REVISION};"
  "universal_setup=${FACMAN_UNIVERSAL_SETUP_REVISION};"
  "provider_mode=${FACMAN_PROVIDER_MODE};"
  "provider_source_linkage=${FACMAN_PROVIDER_SOURCE_LINKAGE};"
  "provider_lock_kind=${FACMAN_PROVIDER_LOCK_KIND};"
  "provider_conformance_only=${FACMAN_PROVIDER_CONFORMANCE_IDENTITY};"
  "provider_sdk_consumption_candidate=${FACMAN_PROVIDER_SDK_CANDIDATE_IDENTITY};"
  "provider_candidate_differs_from_tracked=${FACMAN_PROVIDER_CANDIDATE_DIFFERS_FROM_TRACKED};"
  "provider_consumption_classification=${FACMAN_PROVIDER_CONSUMPTION_CLASSIFICATION};"
  "provider_release_identity_coherent=${FACMAN_PROVIDER_RELEASE_IDENTITY_COHERENCE};"
  "source_dirty=${FACMAN_SOURCE_DIRTY}")
file(WRITE "${CMAKE_CURRENT_BINARY_DIR}/facman-build-identity.v1.txt"
  "${FACMAN_BUILD_IDENTITY}\n")
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

add_subdirectory(runtime/factorio)
add_subdirectory(runtime/client)
add_subdirectory(apps)
if(FACMAN_BUILD_TESTS)
  add_subdirectory(tests/native)
endif()

include(cmake/FacManInstall.cmake)
