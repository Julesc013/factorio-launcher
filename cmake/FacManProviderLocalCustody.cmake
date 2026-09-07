# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

set(FACMAN_PROVIDER_LOCAL_SOURCE_CUSTODY_FILE "" CACHE FILEPATH
  "External reviewed local USK source custody; never stable or installed identity")
set(FACMAN_PROVIDER_LOCAL_SOURCE_CUSTODY_SHA256 "" CACHE STRING
  "Exact reviewed bytes of the source-only candidate custody")
set(FACMAN_PROVIDER_LOCAL_SOURCE_CUSTODY_TIMEOUT "45" CACHE STRING
  "Finite local checkpoint observation timeout in seconds; positive and at most 7200")
set(_FACMAN_LOCAL_CUSTODY_CHECKER
  "${CMAKE_CURRENT_LIST_DIR}/../tools/provider_local_source_custody.py")

function(_facman_validate_local_source_mode)
  if(NOT FACMAN_PROVIDER_LOCAL_SOURCE_CUSTODY_FILE
      AND NOT FACMAN_PROVIDER_LOCAL_SOURCE_CUSTODY_SHA256)
    return()
  endif()
  if(NOT FACMAN_PROVIDER_LOCAL_SOURCE_CUSTODY_FILE
      OR NOT FACMAN_PROVIDER_LOCAL_SOURCE_CUSTODY_SHA256
      OR NOT FACMAN_PROVIDER_MODE STREQUAL "source"
      OR NOT FACMAN_PROVIDER_SOURCE_LINKAGE STREQUAL "static"
      OR NOT FACMAN_PROVIDER_SDK_CONSUMPTION_CANDIDATE
      OR FACMAN_PROVIDER_CONFORMANCE_ONLY
      OR NOT FACMAN_PROVIDER_LOCK_KIND STREQUAL "sdk_candidate")
    message(FATAL_ERROR
      "Local checkpoint custody requires explicit source-static SDK-candidate mode and both custody inputs")
  endif()
endfunction()

function(_facman_local_source_checkpoint out_local repo_root commit tree remote source_ref)
  set(${out_local} FALSE PARENT_SCOPE)
  _facman_validate_local_source_mode()
  if(NOT FACMAN_PROVIDER_LOCAL_SOURCE_CUSTODY_FILE
      OR NOT remote STREQUAL "https://github.com/Julesc013/universal-setup.git")
    return()
  endif()
  if(NOT FACMAN_PROVIDER_LOCAL_SOURCE_CUSTODY_TIMEOUT MATCHES "^[0-9]+([.][0-9]+)?$"
      OR FACMAN_PROVIDER_LOCAL_SOURCE_CUSTODY_TIMEOUT LESS_EQUAL 0
      OR FACMAN_PROVIDER_LOCAL_SOURCE_CUSTODY_TIMEOUT GREATER 7200)
    message(FATAL_ERROR "Local checkpoint timeout must be finite, positive and at most 7200 seconds")
  endif()
  find_package(Python3 COMPONENTS Interpreter REQUIRED)
  execute_process(
    COMMAND "${Python3_EXECUTABLE}" "${_FACMAN_LOCAL_CUSTODY_CHECKER}"
      --custody "${FACMAN_PROVIDER_LOCAL_SOURCE_CUSTODY_FILE}"
      --sha256 "${FACMAN_PROVIDER_LOCAL_SOURCE_CUSTODY_SHA256}"
      --root "${repo_root}" --commit "${commit}" --tree "${tree}"
      --remote "${remote}" --ref "${source_ref}"
    RESULT_VARIABLE custody_result OUTPUT_VARIABLE custody_output
    ERROR_VARIABLE custody_error OUTPUT_STRIP_TRAILING_WHITESPACE
    TIMEOUT "${FACMAN_PROVIDER_LOCAL_SOURCE_CUSTODY_TIMEOUT}")
  if(NOT custody_result STREQUAL "0"
      OR NOT custody_output STREQUAL "reviewed_local_checkpoint")
    message(FATAL_ERROR "Local source checkpoint refused (${custody_result}): ${custody_error}")
  endif()
  set(${out_local} TRUE PARENT_SCOPE)
endfunction()
