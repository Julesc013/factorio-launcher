# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

include(CMakeParseArguments)

set(FACMAN_PROVIDER_MODE "source" CACHE STRING
  "Provider consumption mode: source, installed_static, or installed_shared")
set_property(CACHE FACMAN_PROVIDER_MODE PROPERTY STRINGS
  source installed_static installed_shared)
set(_FACMAN_PROVIDER_MODES source installed_static installed_shared)
if(NOT FACMAN_PROVIDER_MODE IN_LIST _FACMAN_PROVIDER_MODES)
  message(FATAL_ERROR
    "FACMAN_PROVIDER_MODE must be exactly source, installed_static, or installed_shared; got '${FACMAN_PROVIDER_MODE}'")
endif()

set(_FACMAN_TRACKED_PROVIDER_LOCK
  "${CMAKE_CURRENT_SOURCE_DIR}/release/index/workspace_lock.v1.toml")
set(FACMAN_PROVIDER_LOCK_FILE "${_FACMAN_TRACKED_PROVIDER_LOCK}" CACHE FILEPATH
  "Exact provider source lock (tracked lock unless conformance-only mode is explicit)")
option(FACMAN_PROVIDER_CONFORMANCE_ONLY
  "Use an out-of-tree candidate provider lock without adopting it" OFF)
set(_FACMAN_PROVIDER_AUTHORITY_KEYS
  credentials
  factorio_execution
  observer_capture
  permit_issuance
  product_execution
  provider_adoption
  publication
  route_promotion
  setup_mutation
  signing)
set(_FACMAN_PROVIDER_TOOLCHAIN_KEYS
  c_compiler_id
  c_compiler_target
  c_compiler_version
  cmake
  configuration
  cxx_compiler_id
  cxx_compiler_target
  cxx_compiler_version
  generator
  generator_platform
  generator_toolset
  msvc_runtime_library
  pointer_bits
  processor
  sysroot
  system)

function(_facman_real_existing_path out_var path kind label)
  if(NOT IS_ABSOLUTE "${path}")
    message(FATAL_ERROR "${label} must be an absolute path: '${path}'")
  endif()
  if(kind STREQUAL "DIRECTORY" AND NOT IS_DIRECTORY "${path}")
    message(FATAL_ERROR "${label} is not a directory: '${path}'")
  elseif(kind STREQUAL "FILE" AND NOT EXISTS "${path}")
    message(FATAL_ERROR "${label} is not a file: '${path}'")
  endif()
  file(REAL_PATH "${path}" real_path)
  set(${out_var} "${real_path}" PARENT_SCOPE)
endfunction()

function(_facman_require_within_root out_var path root label)
  _facman_real_existing_path(real_root "${root}" DIRECTORY "${label} SDK root")
  if(IS_DIRECTORY "${path}")
    _facman_real_existing_path(real_path "${path}" DIRECTORY "${label}")
  else()
    _facman_real_existing_path(real_path "${path}" FILE "${label}")
  endif()
  file(RELATIVE_PATH relative_path "${real_root}" "${real_path}")
  file(TO_CMAKE_PATH "${relative_path}" relative_path)
  if(IS_ABSOLUTE "${relative_path}" OR relative_path MATCHES "^\\.\\.(/|$)")
    message(FATAL_ERROR "${label} escapes its explicit SDK root: '${real_path}'")
  endif()
  set(${out_var} "${real_path}" PARENT_SCOPE)
endfunction()

function(_facman_require_sha value length label)
  string(LENGTH "${value}" actual_length)
  if(NOT actual_length EQUAL length OR NOT value MATCHES "^[0-9a-f]+$")
    message(FATAL_ERROR "${label} must be a lowercase ${length}-character hexadecimal digest")
  endif()
endfunction()

function(_facman_load_lock_component prefix lock_file component_id)
  file(STRINGS "${lock_file}" lock_lines)
  list(APPEND lock_lines "[[component]]")
  set(in_component FALSE)
  set(found FALSE)
  set(component_fields ID SOURCE PIN TREE REMOTE REQUIRED_REF)
  foreach(name IN LISTS component_fields)
    set(record_${name} "")
    set(record_seen_${name} FALSE)
  endforeach()
  foreach(raw_line IN LISTS lock_lines)
    string(STRIP "${raw_line}" line)
    if(line STREQUAL "[[component]]")
      if(in_component AND record_ID STREQUAL component_id)
        if(found)
          message(FATAL_ERROR
            "Provider lock '${lock_file}' contains duplicate ${component_id} components")
        endif()
        set(found TRUE)
        foreach(name IN LISTS component_fields)
          set(found_${name} "${record_${name}}")
        endforeach()
      endif()
      set(in_component TRUE)
      foreach(name IN LISTS component_fields)
        set(record_${name} "")
        set(record_seen_${name} FALSE)
      endforeach()
    elseif(in_component AND line MATCHES
        "^(id|source|pin|tree|remote|required_ref) = \"([^\"]+)\"$")
      string(TOUPPER "${CMAKE_MATCH_1}" key)
      if(record_seen_${key})
        message(FATAL_ERROR
          "Provider lock '${lock_file}' contains duplicate recognized component field '${CMAKE_MATCH_1}'")
      endif()
      set(record_seen_${key} TRUE)
      set(record_${key} "${CMAKE_MATCH_2}")
    elseif(in_component AND line MATCHES
        "^(id|source|pin|tree|remote|required_ref)[ \\t]*=")
      message(FATAL_ERROR
        "Provider lock '${lock_file}' contains malformed recognized component field '${line}'")
    endif()
  endforeach()
  if(NOT found OR NOT found_SOURCE OR NOT found_PIN OR NOT found_REMOTE
      OR NOT found_REQUIRED_REF)
    message(FATAL_ERROR
      "Provider lock '${lock_file}' has no complete ${component_id} component")
  endif()
  _facman_require_sha("${found_PIN}" 40 "${component_id} source pin")
  if(found_TREE)
    _facman_require_sha("${found_TREE}" 40 "${component_id} source tree")
  endif()
  set(${prefix}_SOURCE "${found_SOURCE}" PARENT_SCOPE)
  set(${prefix}_PIN "${found_PIN}" PARENT_SCOPE)
  set(${prefix}_TREE "${found_TREE}" PARENT_SCOPE)
  set(${prefix}_REMOTE "${found_REMOTE}" PARENT_SCOPE)
  set(${prefix}_REQUIRED_REF "${found_REQUIRED_REF}" PARENT_SCOPE)
endfunction()

function(_facman_validate_provider_lock out_kind out_file)
  if(NOT FACMAN_PROVIDER_CONFORMANCE_ONLY)
    set(CMAKE_SKIP_INSTALL_RULES OFF CACHE BOOL
      "Install rules are enabled outside provider conformance-only configurations" FORCE)
  endif()
  _facman_real_existing_path(tracked_lock "${_FACMAN_TRACKED_PROVIDER_LOCK}" FILE
    "tracked provider lock")
  _facman_real_existing_path(selected_lock "${FACMAN_PROVIDER_LOCK_FILE}" FILE
    "FACMAN_PROVIDER_LOCK_FILE")
  file(REAL_PATH "${CMAKE_CURRENT_SOURCE_DIR}" source_root)
  if(selected_lock STREQUAL tracked_lock)
    if(FACMAN_PROVIDER_CONFORMANCE_ONLY)
      message(FATAL_ERROR
        "FACMAN_PROVIDER_CONFORMANCE_ONLY requires a non-default candidate lock")
    endif()
    file(STRINGS "${selected_lock}" schema_line REGEX "^schema = ")
    if(NOT schema_line STREQUAL "schema = \"flaunch.workspace_lock.v1\"")
      message(FATAL_ERROR "Tracked provider lock has an unexpected schema")
    endif()
    set(FACMAN_PROVIDER_CANDIDATE_DIFFERS_FROM_TRACKED false PARENT_SCOPE)
    set(${out_kind} "tracked" PARENT_SCOPE)
  else()
    if(NOT FACMAN_PROVIDER_CONFORMANCE_ONLY)
      message(FATAL_ERROR
        "A non-default FACMAN_PROVIDER_LOCK_FILE is accepted only with FACMAN_PROVIDER_CONFORMANCE_ONLY=ON")
    endif()
    file(RELATIVE_PATH lock_from_source "${source_root}" "${selected_lock}")
    file(TO_CMAKE_PATH "${lock_from_source}" lock_from_source)
    if(NOT IS_ABSOLUTE "${lock_from_source}" AND NOT lock_from_source MATCHES "^\\.\\.(/|$)")
      message(FATAL_ERROR "The conformance candidate lock must be outside the FacMan source tree")
    endif()
    file(STRINGS "${selected_lock}" candidate_lines)
    set(candidate_section root)
    set(schema_count 0)
    set(candidate_id_count 0)
    set(conformance_count 0)
    set(candidate_count 0)
    set(release_count 0)
    set(tracked_lock_mutated_count 0)
    set(candidate_differs_count 0)
    set(component_count 0)
    set(authority_section FALSE)
    set(authority_table_count 0)
    set(authority_seen)
    foreach(raw_line IN LISTS candidate_lines)
      string(STRIP "${raw_line}" line)
      if(candidate_section STREQUAL "root"
          AND line STREQUAL "schema = \"facman.provider_conformance_lock.v1\"")
        math(EXPR schema_count "${schema_count} + 1")
      elseif(candidate_section STREQUAL "root"
          AND line STREQUAL "id = \"facman_provider_conformance_candidate_v1\"")
        math(EXPR candidate_id_count "${candidate_id_count} + 1")
      elseif(candidate_section STREQUAL "root"
          AND line STREQUAL "conformance_only = true")
        math(EXPR conformance_count "${conformance_count} + 1")
      elseif(candidate_section STREQUAL "root"
          AND line STREQUAL "candidate_not_adopted = true")
        math(EXPR candidate_count "${candidate_count} + 1")
      elseif(candidate_section STREQUAL "root"
          AND line STREQUAL "release_eligible = false")
        math(EXPR release_count "${release_count} + 1")
      elseif(candidate_section STREQUAL "root"
          AND line STREQUAL "tracked_lock_mutated = false")
        math(EXPR tracked_lock_mutated_count
          "${tracked_lock_mutated_count} + 1")
      elseif(candidate_section STREQUAL "root" AND line MATCHES
          "^candidate_differs_from_tracked = (true|false)$")
        set(candidate_differs_declared "${CMAKE_MATCH_1}")
        math(EXPR candidate_differs_count "${candidate_differs_count} + 1")
      elseif(line STREQUAL "[[component]]")
        math(EXPR component_count "${component_count} + 1")
        set(candidate_section component)
        set(authority_section FALSE)
      elseif(line STREQUAL "[authority]")
        math(EXPR authority_table_count "${authority_table_count} + 1")
        if(authority_table_count GREATER 1)
          message(FATAL_ERROR
            "Conformance candidate lock contains duplicate authority tables")
        endif()
        set(candidate_section authority)
        set(authority_section TRUE)
      elseif(line MATCHES "^\\[")
        set(candidate_section other)
        set(authority_section FALSE)
      elseif(authority_section AND line MATCHES "^([A-Za-z0-9_]+) = (true|false)$")
        set(authority_name "${CMAKE_MATCH_1}")
        set(authority_value "${CMAKE_MATCH_2}")
        list(FIND _FACMAN_PROVIDER_AUTHORITY_KEYS "${authority_name}"
          authority_expected_index)
        if(authority_expected_index EQUAL -1)
          message(FATAL_ERROR
            "Conformance candidate lock contains unknown authority '${authority_name}'")
        endif()
        list(FIND authority_seen "${authority_name}" authority_seen_index)
        if(NOT authority_seen_index EQUAL -1)
          message(FATAL_ERROR
            "Conformance candidate lock contains duplicate authority '${authority_name}'")
        endif()
        list(APPEND authority_seen "${authority_name}")
        if(NOT authority_value STREQUAL "false")
          message(FATAL_ERROR "Conformance candidate lock grants authority: '${line}'")
        endif()
      elseif(authority_section AND line MATCHES "^[A-Za-z0-9_]+ = ")
        message(FATAL_ERROR
          "Conformance candidate lock has a non-boolean authority field: '${line}'")
      elseif(line MATCHES "^(path|root|directory) = ")
        message(FATAL_ERROR "Conformance candidate lock must not contain checkout paths")
      elseif(candidate_section STREQUAL "root" AND line MATCHES
          "^(schema|id|conformance_only|candidate_not_adopted|release_eligible|tracked_lock_mutated|candidate_differs_from_tracked)[ \\t]*=")
        message(FATAL_ERROR
          "Conformance candidate lock contains contradictory or malformed classification '${line}'")
      endif()
    endforeach()
    if(NOT schema_count EQUAL 1 OR NOT candidate_id_count EQUAL 1
        OR NOT conformance_count EQUAL 1
        OR NOT candidate_count EQUAL 1 OR NOT release_count EQUAL 1
        OR NOT tracked_lock_mutated_count EQUAL 1
        OR NOT candidate_differs_count EQUAL 1)
      message(FATAL_ERROR "Conformance candidate lock is missing its exact fail-closed classification")
    endif()
    if(NOT component_count EQUAL 2)
      message(FATAL_ERROR "Conformance candidate lock must contain exactly two provider components")
    endif()
    if(NOT authority_table_count EQUAL 1)
      message(FATAL_ERROR "Conformance candidate lock must contain one authority table")
    endif()
    foreach(authority_name IN LISTS _FACMAN_PROVIDER_AUTHORITY_KEYS)
      list(FIND authority_seen "${authority_name}" authority_seen_index)
      if(authority_seen_index EQUAL -1)
        message(FATAL_ERROR
          "Conformance candidate lock is missing authority '${authority_name}'")
      endif()
    endforeach()
    _facman_load_lock_component(candidate_ulk "${selected_lock}"
      universal_launcher)
    _facman_load_lock_component(candidate_usk "${selected_lock}"
      universal_setup)
    _facman_load_lock_component(tracked_ulk "${tracked_lock}"
      universal_launcher)
    _facman_load_lock_component(tracked_usk "${tracked_lock}"
      universal_setup)
    if("${candidate_ulk_PIN}" STREQUAL "${tracked_ulk_PIN}"
        AND "${candidate_usk_PIN}" STREQUAL "${tracked_usk_PIN}")
      set(candidate_differs_computed false)
    else()
      set(candidate_differs_computed true)
    endif()
    if(NOT "${candidate_differs_declared}" STREQUAL
        "${candidate_differs_computed}")
      message(FATAL_ERROR
        "Conformance candidate lock candidate_differs_from_tracked disagrees with its exact provider pins")
    endif()
    set(CMAKE_SKIP_INSTALL_RULES ON CACHE BOOL
      "Disabled for provider conformance-only configurations" FORCE)
    set(FACMAN_PROVIDER_CANDIDATE_DIFFERS_FROM_TRACKED
      "${candidate_differs_computed}" PARENT_SCOPE)
    set(${out_kind} "conformance" PARENT_SCOPE)
  endif()
  set(${out_file} "${selected_lock}" PARENT_SCOPE)
endfunction()

function(_facman_load_release_provider prefix provider_id)
  if(ARGC GREATER 2)
    set(lock_file "${ARGV2}")
  else()
    set(lock_file "${CMAKE_CURRENT_SOURCE_DIR}/release/index/providers.lock.v2.toml")
  endif()
  _facman_real_existing_path(lock_file "${lock_file}" FILE
    "release provider lock")
  file(STRINGS "${lock_file}" lock_lines)
  list(APPEND lock_lines "[[provider]]")
  set(in_provider FALSE)
  set(found FALSE)
  set(provider_fields ID REPOSITORY SOURCE_REVISION PACKAGE_VERSION
      PACKAGE_IDENTITY_KIND PACKAGE_DIGEST ABI_VERSION CONTRACT_SET_ID
      CONTRACT_DIGEST CONSUMPTION_MODE)
  foreach(name IN LISTS provider_fields)
    set(value_${name} "")
    set(value_seen_${name} FALSE)
  endforeach()
  foreach(raw_line IN LISTS lock_lines)
    string(STRIP "${raw_line}" line)
    if(line STREQUAL "[[provider]]")
      if(in_provider AND value_ID STREQUAL provider_id)
        if(found)
          message(FATAL_ERROR
            "Release provider lock contains duplicate ${provider_id} records")
        endif()
        set(found TRUE)
        foreach(name IN LISTS provider_fields)
          set(found_value_${name} "${value_${name}}")
        endforeach()
      endif()
      set(in_provider TRUE)
      foreach(name IN LISTS provider_fields)
        set(value_${name} "")
        set(value_seen_${name} FALSE)
      endforeach()
    elseif(in_provider AND line MATCHES "^(id|repository|source_revision|package_version|package_identity_kind|package_digest|abi_version|contract_set_id|contract_digest|consumption_mode) = \"([^\"]+)\"$")
      string(TOUPPER "${CMAKE_MATCH_1}" key)
      if(value_seen_${key})
        message(FATAL_ERROR
          "Release provider lock contains duplicate recognized field '${CMAKE_MATCH_1}'")
      endif()
      set(value_seen_${key} TRUE)
      set(value_${key} "${CMAKE_MATCH_2}")
    elseif(in_provider AND line MATCHES
        "^(id|repository|source_revision|package_version|package_identity_kind|package_digest|abi_version|contract_set_id|contract_digest|consumption_mode)[ \\t]*=")
      message(FATAL_ERROR
        "Release provider lock contains malformed recognized field '${line}'")
    endif()
  endforeach()
  if(NOT found)
    message(FATAL_ERROR "Release provider lock has no ${provider_id} record")
  endif()
  foreach(name IN ITEMS REPOSITORY SOURCE_REVISION PACKAGE_VERSION
      PACKAGE_IDENTITY_KIND PACKAGE_DIGEST ABI_VERSION CONTRACT_SET_ID
      CONTRACT_DIGEST CONSUMPTION_MODE)
    if(NOT found_value_${name})
      message(FATAL_ERROR "Release provider lock ${provider_id} is missing ${name}")
    endif()
    set(${prefix}_${name} "${found_value_${name}}" PARENT_SCOPE)
  endforeach()
  if(NOT "${found_value_PACKAGE_IDENTITY_KIND}" STREQUAL
      "source_composition_identity"
      OR NOT "${found_value_CONSUMPTION_MODE}" STREQUAL "source")
    message(FATAL_ERROR
      "Release provider lock ${provider_id} must remain an exact source-composition identity")
  endif()
  _facman_require_sha("${found_value_SOURCE_REVISION}" 40
    "Release provider lock ${provider_id} source revision")
  _facman_require_sha("${found_value_PACKAGE_DIGEST}" 64
    "Release provider lock ${provider_id} package digest")
  string(SUBSTRING "${found_value_SOURCE_REVISION}" 0 12 source_short)
  if(NOT "${found_value_PACKAGE_VERSION}" STREQUAL "source-${source_short}")
    message(FATAL_ERROR
      "Release provider lock ${provider_id} source package version is not derived from its exact revision")
  endif()
endfunction()

function(_facman_classify_release_source_match out_var label lock_pin release_revision)
  if("${lock_pin}" STREQUAL "${release_revision}")
    set(${out_var} TRUE PARENT_SCOPE)
    return()
  endif()
  if(FACMAN_PROVIDER_CONFORMANCE_ONLY
      AND "${FACMAN_PROVIDER_LOCK_KIND}" STREQUAL "conformance")
    set(${out_var} FALSE PARENT_SCOPE)
    return()
  endif()
  if(FACMAN_PROVIDER_MODE STREQUAL "source"
      AND "${FACMAN_PROVIDER_LOCK_KIND}" STREQUAL "tracked")
    message(STATUS
      "${label} tracked workspace source remains exact, but it differs from the authored release-provider identity; release eligibility remains false")
    set(${out_var} FALSE PARENT_SCOPE)
    return()
  endif()
  message(FATAL_ERROR
    "${label} selected source differs from the authored release-provider identity outside an exact tracked-source build or explicit conformance")
endfunction()

function(_facman_classify_provider_consumption out_var)
  if(FACMAN_PROVIDER_MODE STREQUAL "source")
    set(${out_var} "${FACMAN_PROVIDER_LOCK_KIND}_source" PARENT_SCOPE)
    return()
  endif()
  # Installed SDKs in this WorkUnit are rehearsal inputs. No tracked, adopted
  # package anchor exists yet, even when an SDK happens to name exact source
  # pins. Pin equality therefore cannot promote installed consumption.
  if(NOT FACMAN_PROVIDER_CONFORMANCE_ONLY
      OR NOT "${FACMAN_PROVIDER_LOCK_KIND}" STREQUAL "conformance")
    message(FATAL_ERROR
      "Installed provider modes are conformance-only until a tracked adopted SDK package anchor exists")
  endif()
  set(${out_var} "conformance_rehearsal_${FACMAN_PROVIDER_MODE}" PARENT_SCOPE)
endfunction()

function(_facman_validate_play_evidence_provider_availability available)
  if(FACMAN_BUILD_PLAY_EVIDENCE_TOOLS AND NOT available)
    message(FATAL_ERROR
      "FACMAN_BUILD_PLAY_EVIDENCE_TOOLS requires source-mode private provider targets; refusing silent target omission")
  endif()
endfunction()

function(_facman_explicit_source_root out_var cache_var label)
  set(cache_value "${${cache_var}}")
  set(env_value "$ENV{${cache_var}}")
  if(cache_value AND env_value)
    _facman_real_existing_path(real_cache "${cache_value}" DIRECTORY "${cache_var}")
    _facman_real_existing_path(real_env "${env_value}" DIRECTORY "environment ${cache_var}")
    if(NOT real_cache STREQUAL real_env)
      message(FATAL_ERROR "Conflicting explicit ${label} roots were provided")
    endif()
  elseif(cache_value)
    _facman_real_existing_path(real_cache "${cache_value}" DIRECTORY "${cache_var}")
  elseif(env_value)
    _facman_real_existing_path(real_cache "${env_value}" DIRECTORY "environment ${cache_var}")
  else()
    message(FATAL_ERROR
      "${cache_var} is required in source mode; no sibling or workspace-root fallback is permitted")
  endif()
  if(NOT EXISTS "${real_cache}/CMakeLists.txt")
    message(FATAL_ERROR "${label} root has no CMakeLists.txt: '${real_cache}'")
  endif()
  set(${cache_var} "${real_cache}" CACHE PATH "Explicit ${label} source root" FORCE)
  set(${out_var} "${real_cache}" PARENT_SCOPE)
endfunction()

function(_facman_normalize_git_remote out_var value label)
  string(STRIP "${value}" normalized)
  if(NOT normalized OR normalized MATCHES ";")
    message(FATAL_ERROR "${label} Git remote is empty or list-valued")
  endif()
  if(NOT normalized MATCHES
      "^([A-Za-z][A-Za-z0-9+.-]*)://([^/@?#]+)(/[^?#]+)$")
    message(FATAL_ERROR
      "${label} Git remote must be an absolute credential-free URL")
  endif()
  set(scheme "${CMAKE_MATCH_1}")
  set(host "${CMAKE_MATCH_2}")
  set(path "${CMAKE_MATCH_3}")
  string(TOLOWER "${scheme}" scheme)
  string(TOLOWER "${host}" host)
  if(NOT scheme STREQUAL "https")
    message(FATAL_ERROR "${label} Git remote must use HTTPS")
  endif()
  string(REGEX REPLACE "/+$" "" path "${path}")
  if(NOT path OR path MATCHES "(^|/)\\.\\.?(/|$)" OR path MATCHES "\\\\")
    message(FATAL_ERROR "${label} Git remote contains an unsafe path")
  endif()
  set(${out_var} "https://${host}${path}" PARENT_SCOPE)
endfunction()

function(_facman_git_identity out_commit out_tree repo_root label expected_commit
    expected_tree expected_remote expected_ref)
  execute_process(
    COMMAND git -c "safe.directory=${repo_root}" rev-parse --show-toplevel
    WORKING_DIRECTORY "${repo_root}"
    OUTPUT_VARIABLE git_root OUTPUT_STRIP_TRAILING_WHITESPACE
    ERROR_VARIABLE git_error RESULT_VARIABLE git_result)
  if(NOT git_result EQUAL 0)
    message(FATAL_ERROR "Cannot resolve ${label} Git root: ${git_error}")
  endif()
  file(REAL_PATH "${git_root}" real_git_root)
  file(REAL_PATH "${repo_root}" real_repo_root)
  if(NOT real_git_root STREQUAL real_repo_root)
    message(FATAL_ERROR "${label} path is not the exact Git worktree root")
  endif()
  execute_process(
    COMMAND git -c "safe.directory=${repo_root}" config --get-all remote.origin.url
    WORKING_DIRECTORY "${repo_root}"
    OUTPUT_VARIABLE origin_output OUTPUT_STRIP_TRAILING_WHITESPACE
    ERROR_VARIABLE git_error RESULT_VARIABLE git_result)
  string(ASCII 10 line_feed)
  string(ASCII 13 carriage_return)
  string(REPLACE "${carriage_return}" "" origin_output "${origin_output}")
  string(REPLACE "${line_feed}" ";" origin_urls "${origin_output}")
  list(FILTER origin_urls EXCLUDE REGEX "^$")
  list(LENGTH origin_urls origin_count)
  if(NOT git_result EQUAL 0 OR NOT origin_count EQUAL 1)
    message(FATAL_ERROR
      "${label} must have exactly one readable remote.origin.url: ${git_error}")
  endif()
  list(GET origin_urls 0 origin_url)
  _facman_normalize_git_remote(actual_remote "${origin_url}" "${label}")
  _facman_normalize_git_remote(locked_remote "${expected_remote}"
    "${label} selected lock")
  if(NOT actual_remote STREQUAL locked_remote)
    message(FATAL_ERROR
      "${label} origin '${actual_remote}' does not match selected lock '${locked_remote}'")
  endif()
  if(NOT expected_ref MATCHES "^refs/heads/[A-Za-z0-9._/-]+$"
      OR expected_ref MATCHES "\\.\\." OR expected_ref MATCHES "//")
    message(FATAL_ERROR "${label} selected lock has an unsafe required ref")
  endif()
  string(REGEX REPLACE "^refs/heads/" "" required_branch "${expected_ref}")
  set(required_remote_ref "refs/remotes/origin/${required_branch}")
  execute_process(
    COMMAND git -c "safe.directory=${repo_root}" rev-parse --verify
      "${required_remote_ref}^{commit}"
    WORKING_DIRECTORY "${repo_root}"
    OUTPUT_VARIABLE required_ref_commit OUTPUT_STRIP_TRAILING_WHITESPACE
    ERROR_VARIABLE git_error RESULT_VARIABLE git_result)
  if(NOT git_result EQUAL 0)
    message(FATAL_ERROR
      "${label} canonical origin ref '${required_remote_ref}' is unavailable: ${git_error}")
  endif()
  execute_process(
    COMMAND git -c "safe.directory=${repo_root}" merge-base --is-ancestor
      "${expected_commit}" "${required_ref_commit}"
    WORKING_DIRECTORY "${repo_root}"
    ERROR_VARIABLE git_error RESULT_VARIABLE git_result)
  if(NOT git_result EQUAL 0)
    message(FATAL_ERROR
      "${label} selected commit is not reachable from '${required_remote_ref}': ${git_error}")
  endif()
  execute_process(
    COMMAND git -c "safe.directory=${repo_root}" status --porcelain=v1
      --untracked-files=all --ignore-submodules=none
    WORKING_DIRECTORY "${repo_root}"
    OUTPUT_VARIABLE git_status OUTPUT_STRIP_TRAILING_WHITESPACE
    ERROR_VARIABLE git_error RESULT_VARIABLE git_result)
  if(NOT git_result EQUAL 0)
    message(FATAL_ERROR "Cannot inspect ${label} Git status: ${git_error}")
  endif()
  if(git_status)
    message(FATAL_ERROR
      "${label} checkout is dirty or contains untracked files and cannot satisfy provider custody")
  endif()
  execute_process(
    COMMAND git -c "safe.directory=${repo_root}" rev-parse HEAD
    WORKING_DIRECTORY "${repo_root}"
    OUTPUT_VARIABLE commit OUTPUT_STRIP_TRAILING_WHITESPACE
    ERROR_VARIABLE git_error RESULT_VARIABLE git_result)
  if(NOT git_result EQUAL 0)
    message(FATAL_ERROR "Cannot resolve ${label} Git revision: ${git_error}")
  endif()
  string(TOLOWER "${commit}" commit)
  _facman_require_sha("${commit}" 40 "${label} Git revision")
  if(NOT commit STREQUAL expected_commit)
    message(FATAL_ERROR "${label} checkout ${commit} does not match selected lock ${expected_commit}")
  endif()
  execute_process(
    COMMAND git -c "safe.directory=${repo_root}" rev-parse HEAD^{tree}
    WORKING_DIRECTORY "${repo_root}"
    OUTPUT_VARIABLE tree OUTPUT_STRIP_TRAILING_WHITESPACE
    ERROR_VARIABLE git_error RESULT_VARIABLE git_result)
  if(NOT git_result EQUAL 0)
    message(FATAL_ERROR "Cannot resolve ${label} Git tree: ${git_error}")
  endif()
  string(TOLOWER "${tree}" tree)
  _facman_require_sha("${tree}" 40 "${label} Git tree")
  if(expected_tree AND NOT tree STREQUAL expected_tree)
    message(FATAL_ERROR "${label} tree ${tree} does not match selected lock ${expected_tree}")
  endif()
  set(${out_commit} "${commit}" PARENT_SCOPE)
  set(${out_tree} "${tree}" PARENT_SCOPE)
endfunction()

function(_facman_json_get out_var json label expected_type)
  set(path ${ARGN})
  string(JSON actual_type ERROR_VARIABLE json_error TYPE "${json}" ${path})
  if(NOT json_error STREQUAL "NOTFOUND")
    message(FATAL_ERROR "${label} is missing or malformed: ${json_error}")
  endif()
  if(NOT actual_type STREQUAL expected_type)
    message(FATAL_ERROR "${label} must be JSON ${expected_type}, got ${actual_type}")
  endif()
  string(JSON value GET "${json}" ${path})
  set(${out_var} "${value}" PARENT_SCOPE)
endfunction()

function(_facman_reject_leaking_value value label)
  if(NOT value OR value MATCHES "[/\\\\]" OR value MATCHES "^[A-Za-z]:" OR value MATCHES "\\.\\.")
    message(FATAL_ERROR "${label} is empty or contains a path-like value")
  endif()
endfunction()

function(_facman_resolve_relative_file out_var sdk_root relative_path label)
  if(NOT relative_path
      OR IS_ABSOLUTE "${relative_path}"
      OR relative_path MATCHES "(^|/)\\.\\.?(/|$)"
      OR relative_path MATCHES "\\\\"
      OR relative_path MATCHES "[:;]")
    message(FATAL_ERROR
      "${label} must be a clean forward-slash relative file path")
  endif()
  set(candidate "${sdk_root}/${relative_path}")
  if(NOT EXISTS "${candidate}" AND NOT IS_SYMLINK "${candidate}")
    message(FATAL_ERROR "${label} does not exist: '${relative_path}'")
  endif()
  _facman_require_within_root(resolved "${candidate}" "${sdk_root}" "${label}")
  set(${out_var} "${candidate}" PARENT_SCOPE)
endfunction()

function(_facman_validate_authority_json identity_json label)
  string(JSON authority_count ERROR_VARIABLE authority_error
    LENGTH "${identity_json}" authority)
  list(LENGTH _FACMAN_PROVIDER_AUTHORITY_KEYS expected_authority_count)
  if(NOT authority_error STREQUAL "NOTFOUND"
      OR NOT authority_count EQUAL expected_authority_count)
    message(FATAL_ERROR
      "${label} identity must contain the exact known authority set")
  endif()
  set(authority_seen)
  math(EXPR authority_last "${authority_count} - 1")
  foreach(index RANGE ${authority_last})
    string(JSON authority_name MEMBER "${identity_json}" authority ${index})
    list(FIND _FACMAN_PROVIDER_AUTHORITY_KEYS "${authority_name}"
      authority_expected_index)
    if(authority_expected_index EQUAL -1)
      message(FATAL_ERROR
        "${label} identity contains unknown authority '${authority_name}'")
    endif()
    list(FIND authority_seen "${authority_name}" authority_seen_index)
    if(NOT authority_seen_index EQUAL -1)
      message(FATAL_ERROR
        "${label} identity contains duplicate authority '${authority_name}'")
    endif()
    list(APPEND authority_seen "${authority_name}")
    _facman_json_get(authority_value "${identity_json}"
      "${label} authority.${authority_name}" BOOLEAN authority ${authority_name})
    if(authority_value)
      message(FATAL_ERROR
        "${label} SDK identity grants ${authority_name} authority")
    endif()
    string(REGEX MATCHALL
      "\"${authority_name}\"[ \\t\\r\\n]*:"
      authority_occurrences "${identity_json}")
    list(LENGTH authority_occurrences authority_occurrence_count)
    if(NOT authority_occurrence_count EQUAL 1)
      message(FATAL_ERROR
        "${label} identity contains a duplicate authority key '${authority_name}'")
    endif()
  endforeach()
endfunction()

function(_facman_validate_sdk_inventory out_manifest out_metadata
    sdk_root identity_file identity_json label provider_id expected_mode
    expected_linkage package_name)
  _facman_json_get(metadata_relative "${identity_json}"
    "${label} package.metadata_relative_path" STRING
    package metadata_relative_path)
  _facman_json_get(metadata_sha "${identity_json}"
    "${label} package.metadata_sha256" STRING package metadata_sha256)
  _facman_json_get(manifest_relative "${identity_json}"
    "${label} install.inventory_manifest_relative_path" STRING
    install inventory_manifest_relative_path)
  _facman_json_get(manifest_sha "${identity_json}"
    "${label} install.inventory_manifest_sha256" STRING
    install inventory_manifest_sha256)
  _facman_json_get(inventory_sha "${identity_json}"
    "${label} install.inventory_sha256" STRING install inventory_sha256)
  _facman_json_get(inventory_count "${identity_json}"
    "${label} install.file_count" NUMBER install file_count)
  foreach(digest IN ITEMS metadata_sha manifest_sha inventory_sha)
    _facman_require_sha("${${digest}}" 64 "${label} ${digest}")
  endforeach()

  _facman_resolve_relative_file(metadata_file "${sdk_root}"
    "${metadata_relative}" "${label} package metadata")
  get_filename_component(metadata_name "${metadata_file}" NAME)
  if(NOT "${metadata_name}" STREQUAL "${package_name}Config.cmake")
    message(FATAL_ERROR
      "${label} package metadata path does not name ${package_name}Config.cmake")
  endif()
  if(IS_SYMLINK "${metadata_file}")
    message(FATAL_ERROR "${label} package metadata must not be a symlink")
  endif()
  file(SHA256 "${metadata_file}" live_metadata_sha)
  if(NOT "${live_metadata_sha}" STREQUAL "${metadata_sha}")
    message(FATAL_ERROR
      "${label} package metadata digest does not match its identity")
  endif()

  _facman_resolve_relative_file(manifest_file "${sdk_root}"
    "${manifest_relative}" "${label} inventory manifest")
  if(IS_SYMLINK "${manifest_file}")
    message(FATAL_ERROR "${label} inventory manifest must not be a symlink")
  endif()
  file(SHA256 "${manifest_file}" live_manifest_sha)
  if(NOT "${live_manifest_sha}" STREQUAL "${manifest_sha}")
    message(FATAL_ERROR
      "${label} inventory manifest digest does not match its identity")
  endif()
  file(READ "${manifest_file}" manifest_json)
  _facman_json_get(manifest_schema "${manifest_json}"
    "${label} inventory schema" STRING schema)
  _facman_json_get(manifest_provider "${manifest_json}"
    "${label} inventory provider_id" STRING provider_id)
  _facman_json_get(manifest_mode "${manifest_json}"
    "${label} inventory consumption.mode" STRING consumption mode)
  _facman_json_get(manifest_linkage "${manifest_json}"
    "${label} inventory consumption.linkage" STRING consumption linkage)
  _facman_json_get(manifest_files_sha "${manifest_json}"
    "${label} inventory files_sha256" STRING files_sha256)
  _facman_require_sha("${manifest_files_sha}" 64
    "${label} inventory files_sha256")
  if(NOT "${manifest_schema}" STREQUAL "facman.provider_sdk_inventory.v1"
      OR NOT "${manifest_provider}" STREQUAL "${provider_id}"
      OR NOT "${manifest_mode}" STREQUAL "${expected_mode}"
      OR NOT "${manifest_linkage}" STREQUAL "${expected_linkage}"
      OR NOT "${manifest_files_sha}" STREQUAL "${inventory_sha}")
    message(FATAL_ERROR
      "${label} inventory manifest identity is inconsistent with its sidecar")
  endif()

  file(RELATIVE_PATH identity_relative "${sdk_root}" "${identity_file}")
  file(TO_CMAKE_PATH "${identity_relative}" identity_relative)
  set(expected_excludes "${identity_relative}" "${manifest_relative}")
  set(custody_excludes ${expected_excludes})
  string(JSON exclude_count ERROR_VARIABLE exclude_error
    LENGTH "${manifest_json}" excludes)
  if(NOT exclude_error STREQUAL "NOTFOUND" OR NOT exclude_count EQUAL 2)
    message(FATAL_ERROR
      "${label} inventory manifest must contain the exact two custody exclusions")
  endif()
  math(EXPR exclude_last "${exclude_count} - 1")
  foreach(index RANGE ${exclude_last})
    _facman_json_get(excluded_path "${manifest_json}"
      "${label} inventory exclusion" STRING excludes ${index})
    list(FIND expected_excludes "${excluded_path}" excluded_index)
    if(excluded_index EQUAL -1)
      message(FATAL_ERROR
        "${label} inventory manifest has unknown or duplicate exclusion '${excluded_path}'")
    endif()
    list(REMOVE_AT expected_excludes ${excluded_index})
  endforeach()
  if(expected_excludes)
    message(FATAL_ERROR "${label} inventory manifest omits a custody exclusion")
  endif()

  string(JSON file_count ERROR_VARIABLE files_error
    LENGTH "${manifest_json}" files)
  if(NOT files_error STREQUAL "NOTFOUND"
      OR NOT file_count EQUAL inventory_count
      OR file_count LESS 1)
    message(FATAL_ERROR
      "${label} inventory file count does not match its identity")
  endif()
  set(manifest_paths)
  set(previous_path "")
  math(EXPR file_last "${file_count} - 1")
  foreach(index RANGE ${file_last})
    _facman_json_get(entry_path "${manifest_json}"
      "${label} inventory file path" STRING files ${index} path)
    _facman_json_get(entry_bytes "${manifest_json}"
      "${label} inventory file bytes" NUMBER files ${index} bytes)
    _facman_json_get(entry_sha "${manifest_json}"
      "${label} inventory file sha256" STRING files ${index} sha256)
    _facman_require_sha("${entry_sha}" 64
      "${label} inventory file sha256")
    if(previous_path AND NOT "${previous_path}" STRLESS "${entry_path}")
      message(FATAL_ERROR
        "${label} inventory file records are not strictly sorted and unique")
    endif()
    set(previous_path "${entry_path}")
    list(FIND custody_excludes "${entry_path}" excluded_file_index)
    if(NOT excluded_file_index EQUAL -1)
      message(FATAL_ERROR
        "${label} inventory lists an excluded custody file")
    endif()
    _facman_resolve_relative_file(entry_file "${sdk_root}" "${entry_path}"
      "${label} inventory file")
    if(IS_SYMLINK "${entry_file}")
      file(READ_SYMLINK "${entry_file}" link_target)
      string(LENGTH "${link_target}" live_bytes)
      string(SHA256 live_sha "${link_target}")
    else()
      file(SIZE "${entry_file}" live_bytes)
      file(SHA256 "${entry_file}" live_sha)
    endif()
    if(NOT entry_bytes EQUAL live_bytes
        OR NOT "${entry_sha}" STREQUAL "${live_sha}")
      message(FATAL_ERROR
        "${label} inventory file content disagrees with '${entry_path}'")
    endif()
    list(APPEND manifest_paths "${entry_path}")
  endforeach()

  file(GLOB_RECURSE all_sdk_paths LIST_DIRECTORIES TRUE
    RELATIVE "${sdk_root}" "${sdk_root}/*")
  set(live_inventory_paths)
  foreach(relative_path IN LISTS all_sdk_paths)
    file(TO_CMAKE_PATH "${relative_path}" relative_path)
    set(absolute_path "${sdk_root}/${relative_path}")
    if(IS_SYMLINK "${absolute_path}" OR NOT IS_DIRECTORY "${absolute_path}")
      list(APPEND live_inventory_paths "${relative_path}")
    endif()
  endforeach()
  list(REMOVE_ITEM live_inventory_paths "${identity_relative}" "${manifest_relative}")
  list(SORT live_inventory_paths)
  if(NOT "${live_inventory_paths}" STREQUAL "${manifest_paths}")
    message(FATAL_ERROR
      "${label} installed SDK contains missing or unrecorded inventory files")
  endif()

  set(${out_manifest} "${manifest_file}" PARENT_SCOPE)
  set(${out_metadata} "${metadata_file}" PARENT_SCOPE)
endfunction()

function(_facman_normalize_architecture out_var value)
  string(TOLOWER "${value}" normalized)
  if(normalized MATCHES "^(amd64|x64|x86_64)$")
    set(normalized x86_64)
  elseif(normalized MATCHES "^(arm64|aarch64)$")
    set(normalized arm64)
  elseif(normalized MATCHES "^(win32|x86|i[3-6]86)$")
    set(normalized x86)
  endif()
  set(${out_var} "${normalized}" PARENT_SCOPE)
endfunction()

function(_facman_validate_toolchain_identity identity_json label)
  string(JSON toolchain_count ERROR_VARIABLE toolchain_error
    LENGTH "${identity_json}" toolchain)
  list(LENGTH _FACMAN_PROVIDER_TOOLCHAIN_KEYS expected_toolchain_count)
  if(NOT toolchain_error STREQUAL "NOTFOUND"
      OR NOT toolchain_count EQUAL expected_toolchain_count)
    message(FATAL_ERROR
      "${label} identity must contain the exact known toolchain field set")
  endif()
  math(EXPR toolchain_last "${toolchain_count} - 1")
  foreach(index RANGE ${toolchain_last})
    string(JSON toolchain_name MEMBER "${identity_json}" toolchain ${index})
    list(FIND _FACMAN_PROVIDER_TOOLCHAIN_KEYS "${toolchain_name}"
      toolchain_expected_index)
    if(toolchain_expected_index EQUAL -1)
      message(FATAL_ERROR
        "${label} identity contains unknown toolchain field '${toolchain_name}'")
    endif()
    string(REGEX MATCHALL
      "\"${toolchain_name}\"[ \\t\\r\\n]*:"
      toolchain_occurrences "${identity_json}")
    list(LENGTH toolchain_occurrences toolchain_occurrence_count)
    if(NOT toolchain_occurrence_count EQUAL 1)
      message(FATAL_ERROR
        "${label} identity contains a duplicate toolchain field '${toolchain_name}'")
    endif()
  endforeach()

  foreach(field IN ITEMS
      cmake generator generator_platform generator_toolset system processor
      configuration c_compiler_id c_compiler_version c_compiler_target
      cxx_compiler_id cxx_compiler_version cxx_compiler_target sysroot
      msvc_runtime_library)
    _facman_json_get(toolchain_${field} "${identity_json}"
      "${label} toolchain.${field}" STRING toolchain ${field})
    _facman_reject_leaking_value("${toolchain_${field}}"
      "${label} toolchain.${field}")
  endforeach()
  _facman_json_get(toolchain_pointer_bits "${identity_json}"
    "${label} toolchain.pointer_bits" NUMBER toolchain pointer_bits)

  set(expected_cmake "cmake version ${CMAKE_VERSION}")
  if(NOT "${toolchain_cmake}" STREQUAL "${expected_cmake}")
    message(FATAL_ERROR
      "${label} toolchain CMake identity '${toolchain_cmake}' does not match active '${expected_cmake}'")
  endif()
  if(NOT "${toolchain_generator}" STREQUAL "${CMAKE_GENERATOR}")
    message(FATAL_ERROR
      "${label} toolchain generator '${toolchain_generator}' does not match active '${CMAKE_GENERATOR}'")
  endif()
  foreach(field IN ITEMS
      generator_platform generator_toolset c_compiler_target
      cxx_compiler_target sysroot msvc_runtime_library)
    string(TOUPPER "${field}" active_field)
    set(active_value "${CMAKE_${active_field}}")
    if("${active_value}" STREQUAL "")
      set(active_value "none")
    endif()
    if(NOT "${toolchain_${field}}" STREQUAL "${active_value}")
      message(FATAL_ERROR
        "${label} toolchain ${field} '${toolchain_${field}}' does not match active '${active_value}'")
    endif()
  endforeach()
  if(NOT "${toolchain_system}" STREQUAL "${CMAKE_SYSTEM_NAME}")
    message(FATAL_ERROR
      "${label} toolchain system '${toolchain_system}' does not match active '${CMAKE_SYSTEM_NAME}'")
  endif()

  set(active_processor "${CMAKE_SYSTEM_PROCESSOR}")
  if(NOT active_processor)
    set(active_processor "${CMAKE_GENERATOR_PLATFORM}")
  endif()
  if(NOT active_processor)
    message(FATAL_ERROR
      "${label} toolchain processor cannot be validated on this generator")
  endif()
  _facman_normalize_architecture(identity_processor
    "${toolchain_processor}")
  _facman_normalize_architecture(configure_processor
    "${active_processor}")
  if(NOT "${identity_processor}" STREQUAL "${configure_processor}")
    message(FATAL_ERROR
      "${label} toolchain processor '${toolchain_processor}' does not match active '${active_processor}'")
  endif()
  if(NOT CMAKE_SIZEOF_VOID_P)
    message(FATAL_ERROR
      "${label} toolchain pointer width cannot be validated")
  endif()
  math(EXPR active_pointer_bits "${CMAKE_SIZEOF_VOID_P} * 8")
  if(NOT toolchain_pointer_bits EQUAL active_pointer_bits)
    message(FATAL_ERROR
      "${label} toolchain pointer width '${toolchain_pointer_bits}' does not match active '${active_pointer_bits}'")
  endif()

  foreach(language IN ITEMS C CXX)
    string(TOLOWER "${language}" language_lower)
    if(NOT "${toolchain_${language_lower}_compiler_id}" STREQUAL "${CMAKE_${language}_COMPILER_ID}"
        OR NOT "${toolchain_${language_lower}_compiler_version}" STREQUAL "${CMAKE_${language}_COMPILER_VERSION}")
      message(FATAL_ERROR
        "${label} ${language} compiler identity does not match the active configure toolchain")
    endif()
  endforeach()

  if(CMAKE_CONFIGURATION_TYPES)
    list(FIND CMAKE_CONFIGURATION_TYPES "${toolchain_configuration}"
      configuration_index)
    if(configuration_index EQUAL -1)
      message(FATAL_ERROR
        "${label} toolchain configuration '${toolchain_configuration}' is unavailable in this generator")
    endif()
    if(CMAKE_BUILD_TYPE
        AND NOT "${toolchain_configuration}" STREQUAL "${CMAKE_BUILD_TYPE}")
      message(FATAL_ERROR
        "${label} toolchain configuration contradicts the explicitly selected multi-config build type")
    endif()
  elseif(CMAKE_BUILD_TYPE)
    if(NOT "${toolchain_configuration}" STREQUAL "${CMAKE_BUILD_TYPE}")
      message(FATAL_ERROR
        "${label} toolchain configuration '${toolchain_configuration}' does not match active '${CMAKE_BUILD_TYPE}'")
    endif()
  else()
    message(FATAL_ERROR
      "${label} toolchain configuration cannot be validated because no active configuration is declared")
  endif()
endfunction()

function(_facman_validate_abi_version locked computed label)
  if(locked STREQUAL computed)
    return()
  endif()
  if(computed MATCHES "^([0-9]+)\\.0$" AND locked STREQUAL CMAKE_MATCH_1)
    return()
  endif()
  message(FATAL_ERROR "${label} ABI ${computed} does not match tracked ABI ${locked}")
endfunction()

function(_facman_validate_imported_path_value value sdk_root label)
  if(NOT value OR value MATCHES "-NOTFOUND$")
    return()
  endif()
  if(value MATCHES "^\\$<")
    message(FATAL_ERROR
      "${label} must not defer path custody through a generator expression")
  endif()
  if(NOT IS_ABSOLUTE "${value}")
    message(FATAL_ERROR
      "${label} must be an exact absolute path inside the selected SDK root")
  endif()
  _facman_require_within_root(resolved_imported_path "${value}" "${sdk_root}"
    "${label}")
endfunction()

function(_facman_validate_interface_option value kind label)
  if(value MATCHES "^\\$<" OR value MATCHES "[@\\\\]"
      OR value MATCHES "\\.\\.")
    message(FATAL_ERROR
      "${label} contains a deferred or path-bearing ${kind} option '${value}'")
  endif()
  if(kind STREQUAL "compile")
    if(value MATCHES "^-I" OR value MATCHES "^-isystem"
        OR value MATCHES "^-iquote" OR value MATCHES "^-include"
        OR value MATCHES "^--sysroot" OR value MATCHES "^/I"
        OR value MATCHES "^/FI" OR value MATCHES "^/external:I")
      message(FATAL_ERROR
        "${label} contains a path-introducing compile option '${value}'")
    endif()
    if(NOT value MATCHES
        "^(-pthread|-W[A-Za-z0-9_+.,=-]+|-O[0-3sg]|-g[0-9]?|-m(32|64)|-f(PIC|PIE|no-exceptions|no-rtti|visibility=(default|hidden|internal|protected))|/(W[0-4]|WX|O[12dxt]|EH(sc|s|a|c|r|-)|GR-?|MDd?|MTd?|permissive-))$")
      message(FATAL_ERROR
        "${label} compile option is outside the exact safe grammar: '${value}'")
    endif()
  elseif(kind STREQUAL "link")
    if(value MATCHES "^-L" OR value MATCHES "^-F"
        OR value MATCHES "^-Wl," OR value MATCHES "^/LIBPATH:"
        OR value MATCHES "^/DEF:" OR value MATCHES "^/WHOLEARCHIVE:")
      message(FATAL_ERROR
        "${label} contains a path-introducing link option '${value}'")
    endif()
    if(NOT value MATCHES
        "^(-pthread|-static|-shared|-s|-rdynamic|/INCREMENTAL(:NO)?|/DEBUG(:FULL|:FASTLINK)?|/OPT:(REF|NOREF|ICF|NOICF))$")
      message(FATAL_ERROR
        "${label} link option is outside the exact safe grammar: '${value}'")
    endif()
  else()
    message(FATAL_ERROR "Internal error: unknown interface option kind '${kind}'")
  endif()
endfunction()

function(_facman_classify_interface_link_item out_dependency value sdk_root label)
  set(item "${value}")
  if(item MATCHES "^\\$<LINK_ONLY:([^$<>]+)>$")
    set(item "${CMAKE_MATCH_1}")
  elseif(item MATCHES "^\\$<")
    message(FATAL_ERROR
      "${label} contains an unsupported deferred link item '${value}'")
  endif()
  if(TARGET "${item}")
    set(${out_dependency} "${item}" PARENT_SCOPE)
    return()
  endif()
  if(item MATCHES "^[A-Za-z0-9_.+-]+::[A-Za-z0-9_.+-]+$")
    message(FATAL_ERROR "${label} names missing imported dependency '${item}'")
  endif()
  if(IS_ABSOLUTE "${item}")
    _facman_validate_imported_path_value("${item}" "${sdk_root}" "${label}")
  elseif(NOT item MATCHES "^(-l)?[A-Za-z0-9_+.-]+$")
    message(FATAL_ERROR
      "${label} link item is outside the exact safe grammar: '${item}'")
  endif()
  set(${out_dependency} "" PARENT_SCOPE)
endfunction()

function(_facman_validate_imported_target target sdk_root label)
  set(target_queue "${target}")
  set(validated_targets)
  while(target_queue)
    list(POP_FRONT target_queue current_target)
    list(FIND validated_targets "${current_target}" validated_index)
    if(NOT validated_index EQUAL -1)
      continue()
    endif()
    if(NOT TARGET "${current_target}")
      message(FATAL_ERROR
        "${label} SDK package is partial: missing ${current_target}")
    endif()
    get_target_property(is_imported "${current_target}" IMPORTED)
    if(NOT is_imported)
      message(FATAL_ERROR
        "${label} dependency closure contains non-imported target ${current_target}")
    endif()
    list(APPEND validated_targets "${current_target}")

    foreach(property IN ITEMS
        INTERFACE_INCLUDE_DIRECTORIES INTERFACE_SYSTEM_INCLUDE_DIRECTORIES
        INTERFACE_LINK_DIRECTORIES INTERFACE_SOURCES INTERFACE_LINK_DEPENDS)
      get_target_property(property_values "${current_target}" ${property})
      if(property_values AND NOT property_values MATCHES "-NOTFOUND$")
        foreach(property_value IN LISTS property_values)
          _facman_validate_imported_path_value("${property_value}" "${sdk_root}"
            "${label} ${current_target} ${property}")
        endforeach()
      endif()
    endforeach()

    set(option_properties INTERFACE_COMPILE_OPTIONS INTERFACE_LINK_OPTIONS)
    set(option_kinds compile link)
    foreach(property kind IN ZIP_LISTS option_properties option_kinds)
      get_target_property(property_values "${current_target}" ${property})
      if(property_values AND NOT property_values MATCHES "-NOTFOUND$")
        foreach(property_value IN LISTS property_values)
          _facman_validate_interface_option("${property_value}" "${kind}"
            "${label} ${current_target} ${property}")
        endforeach()
      endif()
    endforeach()

    get_target_property(definitions "${current_target}"
      INTERFACE_COMPILE_DEFINITIONS)
    if(definitions AND NOT definitions MATCHES "-NOTFOUND$")
      foreach(definition IN LISTS definitions)
        if(NOT definition MATCHES
            "^[A-Za-z_][A-Za-z0-9_]*(=[A-Za-z0-9_+.,-]+)?$")
          message(FATAL_ERROR
            "${label} ${current_target} has unsafe interface definition '${definition}'")
        endif()
      endforeach()
    endif()
    get_target_property(features "${current_target}" INTERFACE_COMPILE_FEATURES)
    if(features AND NOT features MATCHES "-NOTFOUND$")
      foreach(feature IN LISTS features)
        if(NOT feature MATCHES "^(c|cxx)_[A-Za-z0-9_]+$")
          message(FATAL_ERROR
            "${label} ${current_target} has unsafe interface feature '${feature}'")
        endif()
      endforeach()
    endif()

    get_target_property(link_items "${current_target}" INTERFACE_LINK_LIBRARIES)
    if(link_items AND NOT link_items MATCHES "-NOTFOUND$")
      foreach(link_item IN LISTS link_items)
        _facman_classify_interface_link_item(dependency "${link_item}"
          "${sdk_root}"
          "${label} ${current_target} INTERFACE_LINK_LIBRARIES")
        if(dependency)
          list(APPEND target_queue "${dependency}")
        endif()
      endforeach()
    endif()

    set(location_properties IMPORTED_LOCATION IMPORTED_IMPLIB IMPORTED_OBJECTS)
    get_target_property(imported_configurations "${current_target}"
      IMPORTED_CONFIGURATIONS)
    if(imported_configurations
        AND NOT imported_configurations MATCHES "-NOTFOUND$")
      foreach(configuration IN LISTS imported_configurations)
        string(TOUPPER "${configuration}" configuration_upper)
        list(APPEND location_properties
          "IMPORTED_LOCATION_${configuration_upper}"
          "IMPORTED_IMPLIB_${configuration_upper}"
          "IMPORTED_OBJECTS_${configuration_upper}")
      endforeach()
    endif()
    list(REMOVE_DUPLICATES location_properties)
    foreach(property IN LISTS location_properties)
      get_target_property(property_values "${current_target}" ${property})
      if(property_values AND NOT property_values MATCHES "-NOTFOUND$")
        foreach(property_value IN LISTS property_values)
          _facman_validate_imported_path_value("${property_value}" "${sdk_root}"
            "${label} ${current_target} ${property}")
        endforeach()
      endif()
    endforeach()
  endwhile()
  if(NOT validated_targets)
    message(FATAL_ERROR "${label} imported dependency closure is empty")
  endif()
endfunction()

function(_facman_validate_installed_provider out_prefix)
  set(options PRELOAD)
  set(one_value
    LABEL PROVIDER_ID PACKAGE_NAME PACKAGE_VERSION IDENTITY_FILE SDK_ROOT
    LOCK_PIN LOCK_TREE LOCK_REMOTE LOCK_REF REPOSITORY RELEASE_SOURCE
    RELEASE_PACKAGE_VERSION RELEASE_PACKAGE_IDENTITY_KIND
    RELEASE_CONSUMPTION_MODE ABI_VERSION ABI_SCHEMA
    CONTRACT_SET_ID CONTRACT_DIGEST)
  set(multi_value REQUIRED_CONTRACTS REQUIRED_TARGETS)
  cmake_parse_arguments(ARG "${options}" "${one_value}" "${multi_value}" ${ARGN})

  _facman_real_existing_path(sdk_root "${ARG_SDK_ROOT}" DIRECTORY "${ARG_LABEL} SDK root")
  _facman_require_within_root(identity_file "${ARG_IDENTITY_FILE}" "${sdk_root}"
    "${ARG_LABEL} identity sidecar")
  file(READ "${identity_file}" identity_json)

  _facman_json_get(schema "${identity_json}" "${ARG_LABEL} identity schema" STRING schema)
  if(NOT schema STREQUAL "facman.provider_sdk_identity.v1")
    message(FATAL_ERROR "${ARG_LABEL} identity has unsupported schema '${schema}'")
  endif()
  _facman_json_get(provider_id "${identity_json}" "${ARG_LABEL} provider_id" STRING provider_id)
  _facman_json_get(repository "${identity_json}" "${ARG_LABEL} repository" STRING repository)
  _facman_json_get(main_ref "${identity_json}" "${ARG_LABEL} canonical_main_ref" STRING canonical_main_ref)
  _facman_json_get(source_commit "${identity_json}" "${ARG_LABEL} source.commit" STRING source commit)
  _facman_json_get(source_tree "${identity_json}" "${ARG_LABEL} source.tree" STRING source tree)
  _facman_json_get(source_remote "${identity_json}" "${ARG_LABEL} source.remote" STRING source remote)
  _facman_json_get(identity_mode "${identity_json}" "${ARG_LABEL} consumption.mode" STRING consumption mode)
  _facman_json_get(identity_linkage "${identity_json}" "${ARG_LABEL} consumption.linkage" STRING consumption linkage)
  _facman_json_get(package_version "${identity_json}" "${ARG_LABEL} package.version" STRING package version)
  _facman_json_get(metadata_relative "${identity_json}" "${ARG_LABEL} package.metadata_relative_path" STRING package metadata_relative_path)
  _facman_json_get(metadata_sha "${identity_json}" "${ARG_LABEL} package.metadata_sha256" STRING package metadata_sha256)
  _facman_json_get(abi_version "${identity_json}" "${ARG_LABEL} abi.version" STRING abi version)
  _facman_json_get(abi_relative "${identity_json}" "${ARG_LABEL} abi.manifest_relative_path" STRING abi manifest_relative_path)
  _facman_json_get(abi_sha "${identity_json}" "${ARG_LABEL} abi.manifest_sha256" STRING abi manifest_sha256)
  _facman_json_get(contract_id "${identity_json}" "${ARG_LABEL} contracts.contract_set_id" STRING contracts contract_set_id)
  _facman_json_get(contract_sha "${identity_json}" "${ARG_LABEL} contracts.bundle_sha256" STRING contracts bundle_sha256)
  _facman_json_get(contract_count "${identity_json}" "${ARG_LABEL} contracts.file_count" NUMBER contracts file_count)
  _facman_json_get(install_root "${identity_json}" "${ARG_LABEL} install.root" STRING install root)
  _facman_json_get(inventory_sha "${identity_json}" "${ARG_LABEL} install.inventory_sha256" STRING install inventory_sha256)
  _facman_json_get(inventory_count "${identity_json}" "${ARG_LABEL} install.file_count" NUMBER install file_count)

  if(NOT "${provider_id}" STREQUAL "${ARG_PROVIDER_ID}"
      OR NOT "${repository}" STREQUAL "${ARG_REPOSITORY}")
    message(FATAL_ERROR "${ARG_LABEL} identity names the wrong provider or repository")
  endif()
  if(NOT "${main_ref}" STREQUAL "${ARG_LOCK_REF}"
      OR NOT "${main_ref}" STREQUAL "refs/heads/main")
    message(FATAL_ERROR "${ARG_LABEL} identity is not bound to canonical main")
  endif()
  _facman_require_sha("${source_commit}" 40 "${ARG_LABEL} source commit")
  _facman_require_sha("${source_tree}" 40 "${ARG_LABEL} source tree")
  if(NOT "${source_commit}" STREQUAL "${ARG_LOCK_PIN}"
      OR NOT "${source_remote}" STREQUAL "${ARG_LOCK_REMOTE}")
    message(FATAL_ERROR "${ARG_LABEL} identity does not match the selected source lock")
  endif()
  if(ARG_LOCK_TREE AND NOT "${source_tree}" STREQUAL "${ARG_LOCK_TREE}")
    message(FATAL_ERROR "${ARG_LABEL} identity tree does not match the selected source lock")
  endif()
  if(NOT "${ARG_RELEASE_PACKAGE_IDENTITY_KIND}" STREQUAL "source_composition_identity"
      OR NOT "${ARG_RELEASE_CONSUMPTION_MODE}" STREQUAL "source")
    message(FATAL_ERROR
      "${ARG_LABEL} active release-provider record is not a source-composition identity")
  endif()
  if(NOT "${source_commit}" STREQUAL "${ARG_RELEASE_SOURCE}")
    if(NOT FACMAN_PROVIDER_CONFORMANCE_ONLY
        OR NOT "${FACMAN_PROVIDER_LOCK_KIND}" STREQUAL "conformance")
      message(FATAL_ERROR
        "${ARG_LABEL} source identity disagrees with the active release-provider lock outside explicit conformance")
    endif()
  endif()
  if(NOT "${identity_mode}" STREQUAL "${FACMAN_PROVIDER_MODE}")
    message(FATAL_ERROR "${ARG_LABEL} identity was not issued for ${FACMAN_PROVIDER_MODE}")
  endif()
  if(FACMAN_PROVIDER_MODE STREQUAL "installed_static")
    set(expected_linkage static)
  else()
    set(expected_linkage shared)
  endif()
  if(NOT "${identity_linkage}" STREQUAL "${expected_linkage}")
    message(FATAL_ERROR "${ARG_LABEL} identity has wrong linkage '${identity_linkage}'")
  endif()
  if(NOT "${package_version}" STREQUAL "${ARG_PACKAGE_VERSION}")
    message(FATAL_ERROR "${ARG_LABEL} package version is not ${ARG_PACKAGE_VERSION}")
  endif()
  foreach(digest IN ITEMS metadata_sha abi_sha contract_sha inventory_sha)
    _facman_require_sha("${${digest}}" 64 "${ARG_LABEL} ${digest}")
  endforeach()
  if(NOT "${contract_id}" STREQUAL "${ARG_CONTRACT_SET_ID}"
      OR NOT "${contract_sha}" STREQUAL "${ARG_CONTRACT_DIGEST}")
    message(FATAL_ERROR "${ARG_LABEL} contract identity disagrees with the release-provider lock")
  endif()
  if(NOT "${install_root}" STREQUAL "."
      OR contract_count LESS 1 OR inventory_count LESS 1)
    message(FATAL_ERROR "${ARG_LABEL} identity has invalid relative install inventory metadata")
  endif()

  _facman_validate_toolchain_identity("${identity_json}" "${ARG_LABEL}")
  _facman_validate_authority_json("${identity_json}" "${ARG_LABEL}")

  string(JSON target_count ERROR_VARIABLE target_error LENGTH "${identity_json}" package exported_targets)
  if(NOT target_error STREQUAL "NOTFOUND")
    message(FATAL_ERROR "${ARG_LABEL} exported target inventory is malformed")
  endif()
  list(LENGTH ARG_REQUIRED_TARGETS expected_target_count)
  if(NOT target_count EQUAL expected_target_count)
    message(FATAL_ERROR "${ARG_LABEL} identity does not contain the exact supported target set")
  endif()
  set(unmatched_targets ${ARG_REQUIRED_TARGETS})
  if(target_count GREATER 0)
    math(EXPR target_last "${target_count} - 1")
    foreach(index RANGE ${target_last})
      _facman_json_get(exported_target "${identity_json}" "${ARG_LABEL} exported target" STRING package exported_targets ${index})
      list(FIND unmatched_targets "${exported_target}" target_index)
      if(target_index EQUAL -1)
        message(FATAL_ERROR "${ARG_LABEL} identity exports unsupported or duplicate target '${exported_target}'")
      endif()
      list(REMOVE_AT unmatched_targets ${target_index})
    endforeach()
  endif()
  if(unmatched_targets)
    message(FATAL_ERROR "${ARG_LABEL} identity omits supported targets: ${unmatched_targets}")
  endif()

  _facman_validate_sdk_inventory(prevalidated_manifest prevalidated_metadata
    "${sdk_root}" "${identity_file}" "${identity_json}" "${ARG_LABEL}"
    "${ARG_PROVIDER_ID}" "${identity_mode}" "${identity_linkage}"
    "${ARG_PACKAGE_NAME}")
  _facman_resolve_relative_file(prevalidated_abi "${sdk_root}"
    "${abi_relative}" "${ARG_LABEL} ABI manifest")
  if(IS_SYMLINK "${prevalidated_abi}")
    message(FATAL_ERROR "${ARG_LABEL} ABI manifest must not be a symlink")
  endif()
  file(SHA256 "${prevalidated_abi}" prevalidated_abi_sha)
  if(NOT "${prevalidated_abi_sha}" STREQUAL "${abi_sha}")
    message(FATAL_ERROR
      "${ARG_LABEL} ABI manifest digest does not match its identity")
  endif()

  if(ARG_PRELOAD)
    set(${out_prefix}_SOURCE_COMMIT "${source_commit}" PARENT_SCOPE)
    set(${out_prefix}_SOURCE_TREE "${source_tree}" PARENT_SCOPE)
    set(${out_prefix}_SDK_ROOT "${sdk_root}" PARENT_SCOPE)
    set(${out_prefix}_METADATA_FILE "${prevalidated_metadata}" PARENT_SCOPE)
    set(${out_prefix}_INVENTORY_MANIFEST "${prevalidated_manifest}" PARENT_SCOPE)
    return()
  endif()

  foreach(required_target IN LISTS ARG_REQUIRED_TARGETS)
    _facman_validate_imported_target("${required_target}" "${sdk_root}"
      "${ARG_LABEL}")
  endforeach()

  set(dir_var "${ARG_PACKAGE_NAME}_DIR")
  set(config_file "${${dir_var}}/${ARG_PACKAGE_NAME}Config.cmake")
  _facman_require_within_root(config_file "${config_file}" "${sdk_root}"
    "${ARG_LABEL} package metadata")
  file(REAL_PATH "${config_file}" selected_metadata_real)
  file(REAL_PATH "${prevalidated_metadata}" expected_metadata_real)
  if(NOT "${selected_metadata_real}" STREQUAL "${expected_metadata_real}")
    message(FATAL_ERROR
      "${ARG_LABEL} find_package selected metadata other than the prevalidated config")
  endif()
  file(SHA256 "${config_file}" live_metadata_sha)
  if(NOT "${live_metadata_sha}" STREQUAL "${metadata_sha}")
    message(FATAL_ERROR "${ARG_LABEL} package metadata digest does not match its identity")
  endif()

  set(contracts_var "${ARG_PACKAGE_NAME}_CONTRACTS_DIR")
  set(abi_var "${ARG_PACKAGE_NAME}_ABI_MANIFEST")
  _facman_require_within_root(contracts_dir "${${contracts_var}}" "${sdk_root}"
    "${ARG_LABEL} contracts directory")
  _facman_require_within_root(abi_manifest "${${abi_var}}" "${sdk_root}"
    "${ARG_LABEL} ABI manifest")
  file(RELATIVE_PATH live_abi_relative "${sdk_root}" "${abi_manifest}")
  file(TO_CMAKE_PATH "${live_abi_relative}" live_abi_relative)
  if(IS_ABSOLUTE "${abi_relative}" OR abi_relative MATCHES "^\\.\\.(/|$)"
      OR abi_relative MATCHES "\\\\"
      OR NOT "${abi_relative}" STREQUAL "${live_abi_relative}")
    message(FATAL_ERROR "${ARG_LABEL} ABI manifest path is not exact and relative")
  endif()
  file(SHA256 "${abi_manifest}" live_abi_sha)
  if(NOT "${live_abi_sha}" STREQUAL "${abi_sha}")
    message(FATAL_ERROR "${ARG_LABEL} ABI manifest digest does not match its identity")
  endif()
  file(STRINGS "${abi_manifest}" abi_lines)
  set(live_abi_schema "")
  set(live_abi_major "")
  set(live_abi_minor "")
  foreach(line IN LISTS abi_lines)
    if(line MATCHES "^schema = \"([^\"]+)\"$")
      set(live_abi_schema "${CMAKE_MATCH_1}")
    elseif(line MATCHES "^abi_major = ([0-9]+)$")
      set(live_abi_major "${CMAKE_MATCH_1}")
    elseif(line MATCHES "^abi_minor = ([0-9]+)$")
      set(live_abi_minor "${CMAKE_MATCH_1}")
    endif()
  endforeach()
  if(NOT "${live_abi_schema}" STREQUAL "${ARG_ABI_SCHEMA}"
      OR "${live_abi_major}" STREQUAL "" OR "${live_abi_minor}" STREQUAL "")
    message(FATAL_ERROR "${ARG_LABEL} ABI manifest has invalid schema or version fields")
  endif()
  set(live_abi_version "${live_abi_major}.${live_abi_minor}")
  if(NOT "${abi_version}" STREQUAL "${live_abi_version}")
    message(FATAL_ERROR "${ARG_LABEL} identity ABI version does not match its live manifest")
  endif()
  _facman_validate_abi_version("${ARG_ABI_VERSION}" "${live_abi_version}" "${ARG_LABEL}")

  foreach(required_contract IN LISTS ARG_REQUIRED_CONTRACTS)
    if(NOT EXISTS "${contracts_dir}/${required_contract}")
      message(FATAL_ERROR "${ARG_LABEL} SDK contract closure is incomplete: ${required_contract}")
    endif()
  endforeach()
  file(GLOB_RECURSE contract_files LIST_DIRECTORIES FALSE "${contracts_dir}/*.json")
  list(LENGTH contract_files live_contract_count)
  if(NOT live_contract_count EQUAL contract_count)
    message(FATAL_ERROR "${ARG_LABEL} contract file count does not match its identity")
  endif()

  set(headers_target "${ARG_PACKAGE_NAME}::Headers")
  get_target_property(include_dirs ${headers_target} INTERFACE_INCLUDE_DIRECTORIES)
  if(NOT include_dirs)
    message(FATAL_ERROR "${ARG_LABEL} Headers target has no include directory")
  endif()
  set(resolved_include_dirs)
  foreach(include_dir IN LISTS include_dirs)
    if(include_dir MATCHES "^\\$<")
      message(FATAL_ERROR "${ARG_LABEL} imported Headers target contains an unresolved generator expression")
    endif()
    _facman_require_within_root(resolved_include "${include_dir}" "${sdk_root}"
      "${ARG_LABEL} public include directory")
    list(APPEND resolved_include_dirs "${resolved_include}")
  endforeach()
  list(REMOVE_DUPLICATES resolved_include_dirs)
  list(LENGTH resolved_include_dirs include_count)
  if(NOT include_count EQUAL 1)
    message(FATAL_ERROR "${ARG_LABEL} public include root is ambiguous")
  endif()
  list(GET resolved_include_dirs 0 include_dir)

  set(${out_prefix}_SOURCE_COMMIT "${source_commit}" PARENT_SCOPE)
  set(${out_prefix}_SOURCE_TREE "${source_tree}" PARENT_SCOPE)
  set(${out_prefix}_SDK_ROOT "${sdk_root}" PARENT_SCOPE)
  set(${out_prefix}_INCLUDE_DIR "${include_dir}" PARENT_SCOPE)
  set(${out_prefix}_CONTRACTS_DIR "${contracts_dir}" PARENT_SCOPE)
  set(${out_prefix}_ABI_MANIFEST "${abi_manifest}" PARENT_SCOPE)
endfunction()

function(_facman_define_provider_wrapper target_name alias_name provider_target)
  add_library(${target_name} INTERFACE)
  target_link_libraries(${target_name} INTERFACE ${provider_target})
  add_library(${alias_name} ALIAS ${target_name})
endfunction()

macro(facman_configure_providers)
  _facman_validate_provider_lock(FACMAN_PROVIDER_LOCK_KIND FACMAN_PROVIDER_LOCK_RESOLVED)
  _facman_classify_provider_consumption(
    FACMAN_PROVIDER_CONSUMPTION_CLASSIFICATION)
  _facman_load_lock_component(FACMAN_ULK_LOCK "${FACMAN_PROVIDER_LOCK_RESOLVED}" universal_launcher)
  _facman_load_lock_component(FACMAN_USK_LOCK "${FACMAN_PROVIDER_LOCK_RESOLVED}" universal_setup)
  if(NOT "${FACMAN_ULK_LOCK_SOURCE}" STREQUAL "universal-launcher"
      OR NOT "${FACMAN_USK_LOCK_SOURCE}" STREQUAL "universal-setup")
    message(FATAL_ERROR
      "Provider lock component source identities are not the exact supported repositories")
  endif()
  if(NOT "${FACMAN_ULK_LOCK_REQUIRED_REF}" STREQUAL "refs/heads/main"
      OR NOT "${FACMAN_USK_LOCK_REQUIRED_REF}" STREQUAL "refs/heads/main")
    message(FATAL_ERROR
      "Provider lock components must bind refs/heads/main")
  endif()
  if(FACMAN_PROVIDER_CONFORMANCE_ONLY
      AND (NOT FACMAN_ULK_LOCK_TREE OR NOT FACMAN_USK_LOCK_TREE))
    message(FATAL_ERROR
      "Conformance candidate lock components must contain exact source trees")
  endif()
  _facman_load_release_provider(FACMAN_ULK_RELEASE universal_launcher)
  _facman_load_release_provider(FACMAN_USK_RELEASE universal_setup)
  _facman_classify_release_source_match(FACMAN_ULK_RELEASE_IDENTITY_COHERENT
    "Universal Launcher"
    "${FACMAN_ULK_LOCK_PIN}" "${FACMAN_ULK_RELEASE_SOURCE_REVISION}")
  _facman_classify_release_source_match(FACMAN_USK_RELEASE_IDENTITY_COHERENT
    "Universal Setup"
    "${FACMAN_USK_LOCK_PIN}" "${FACMAN_USK_RELEASE_SOURCE_REVISION}")
  if(FACMAN_ULK_RELEASE_IDENTITY_COHERENT
      AND FACMAN_USK_RELEASE_IDENTITY_COHERENT)
    set(FACMAN_PROVIDER_RELEASE_IDENTITY_COHERENT TRUE)
  else()
    set(FACMAN_PROVIDER_RELEASE_IDENTITY_COHERENT FALSE)
  endif()

  if(FACMAN_PROVIDER_MODE STREQUAL "source")
    set(FLAUNCH_UNIVERSAL_LAUNCHER_ROOT "" CACHE PATH
      "Explicit Universal Launcher source root")
    set(FLAUNCH_UNIVERSAL_SETUP_ROOT "" CACHE PATH
      "Explicit Universal Setup source root")
    _facman_explicit_source_root(FLAUNCH_UNIVERSAL_LAUNCHER_ROOT
      FLAUNCH_UNIVERSAL_LAUNCHER_ROOT "Universal Launcher")
    _facman_explicit_source_root(FLAUNCH_UNIVERSAL_SETUP_ROOT
      FLAUNCH_UNIVERSAL_SETUP_ROOT "Universal Setup")
    # FACMAN_WITH_SETUP gates product operations, not the two-provider custody
    # set. Both exact provider sources remain mandatory and validated.
    _facman_git_identity(FACMAN_UNIVERSAL_LAUNCHER_REVISION FACMAN_UNIVERSAL_LAUNCHER_TREE
      "${FLAUNCH_UNIVERSAL_LAUNCHER_ROOT}" "Universal Launcher"
      "${FACMAN_ULK_LOCK_PIN}" "${FACMAN_ULK_LOCK_TREE}"
      "${FACMAN_ULK_LOCK_REMOTE}" "${FACMAN_ULK_LOCK_REQUIRED_REF}")
    _facman_git_identity(FACMAN_UNIVERSAL_SETUP_REVISION FACMAN_UNIVERSAL_SETUP_TREE
      "${FLAUNCH_UNIVERSAL_SETUP_ROOT}" "Universal Setup"
      "${FACMAN_USK_LOCK_PIN}" "${FACMAN_USK_LOCK_TREE}"
      "${FACMAN_USK_LOCK_REMOTE}" "${FACMAN_USK_LOCK_REQUIRED_REF}")

    set(ULK_BUILD_APPS OFF CACHE BOOL "" FORCE)
    set(ULK_BUILD_TESTS OFF CACHE BOOL "" FORCE)
    set(ULK_BUILD_STATIC ON CACHE BOOL "" FORCE)
    set(ULK_BUILD_SHARED ON CACHE BOOL "" FORCE)
    add_subdirectory("${FLAUNCH_UNIVERSAL_LAUNCHER_ROOT}"
      "${CMAKE_CURRENT_BINARY_DIR}/universal-launcher" EXCLUDE_FROM_ALL)
    if(FACMAN_WITH_SETUP)
      set(USK_BUILD_APPS OFF CACHE BOOL "" FORCE)
      set(USK_BUILD_TESTS OFF CACHE BOOL "" FORCE)
      set(USK_BUILD_FUZZERS OFF CACHE BOOL "" FORCE)
      set(USK_BUILD_STATIC ON CACHE BOOL "" FORCE)
      set(USK_BUILD_SHARED ON CACHE BOOL "" FORCE)
      add_subdirectory("${FLAUNCH_UNIVERSAL_SETUP_ROOT}"
        "${CMAKE_CURRENT_BINARY_DIR}/universal-setup" EXCLUDE_FROM_ALL)
    endif()
    set(FACMAN_UNIVERSAL_LAUNCHER_INCLUDE_DIR
      "${FLAUNCH_UNIVERSAL_LAUNCHER_ROOT}/include")
    # The tracked source pins predate the installed SDK aliases. Keep their
    # private target names contained here and expose only FacMan wrappers.
    set(FACMAN_UNIVERSAL_LAUNCHER_HEADERS_TARGET ulk_headers)
    set(FACMAN_UNIVERSAL_LAUNCHER_CORE_TARGET ulk_static)
    set(FACMAN_UNIVERSAL_LAUNCHER_SHARED_CLOSURE_TARGET ulk_shared)
    set(FACMAN_UNIVERSAL_LAUNCHER_RUNTIME_TARGET ulk_shared)
    if(FACMAN_WITH_SETUP)
      set(FACMAN_UNIVERSAL_SETUP_HEADERS_TARGET usk_headers)
      set(FACMAN_UNIVERSAL_SETUP_CORE_TARGET usk_static)
      set(FACMAN_UNIVERSAL_SETUP_RUNTIME_TARGET usk_shared)
    endif()
    set(FACMAN_PROVIDER_PRIVATE_SOURCE_TARGETS_AVAILABLE TRUE)
    message(STATUS "FacMan providers: explicit source mode (private provider tests available)")
  else()
    set(FACMAN_UNIVERSAL_LAUNCHER_SDK_ROOT "" CACHE PATH
      "Exact installed Universal Launcher SDK prefix")
    set(FACMAN_UNIVERSAL_SETUP_SDK_ROOT "" CACHE PATH
      "Exact installed Universal Setup SDK prefix")
    set(FACMAN_UNIVERSAL_LAUNCHER_IDENTITY_FILE "" CACHE FILEPATH
      "Universal Launcher facman.provider_sdk_identity.v1 sidecar")
    set(FACMAN_UNIVERSAL_SETUP_IDENTITY_FILE "" CACHE FILEPATH
      "Universal Setup facman.provider_sdk_identity.v1 sidecar")
    foreach(required_value IN ITEMS
        FACMAN_UNIVERSAL_LAUNCHER_SDK_ROOT FACMAN_UNIVERSAL_SETUP_SDK_ROOT
        FACMAN_UNIVERSAL_LAUNCHER_IDENTITY_FILE FACMAN_UNIVERSAL_SETUP_IDENTITY_FILE)
      if(NOT ${required_value})
        message(FATAL_ERROR "${required_value} is mandatory in installed provider modes")
      endif()
    endforeach()
    _facman_real_existing_path(FACMAN_UNIVERSAL_LAUNCHER_SDK_ROOT
      "${FACMAN_UNIVERSAL_LAUNCHER_SDK_ROOT}" DIRECTORY "Universal Launcher SDK root")
    _facman_real_existing_path(FACMAN_UNIVERSAL_SETUP_SDK_ROOT
      "${FACMAN_UNIVERSAL_SETUP_SDK_ROOT}" DIRECTORY "Universal Setup SDK root")
    # Installed-mode custody likewise remains a two-provider invariant when
    # Setup-backed product operations are disabled.
    _facman_validate_installed_provider(FACMAN_ULK_PRE
      PRELOAD
      LABEL "Universal Launcher"
      PROVIDER_ID universal_launcher
      PACKAGE_NAME UniversalLauncher
      PACKAGE_VERSION 1.8.0
      IDENTITY_FILE "${FACMAN_UNIVERSAL_LAUNCHER_IDENTITY_FILE}"
      SDK_ROOT "${FACMAN_UNIVERSAL_LAUNCHER_SDK_ROOT}"
      LOCK_PIN "${FACMAN_ULK_LOCK_PIN}"
      LOCK_TREE "${FACMAN_ULK_LOCK_TREE}"
      LOCK_REMOTE "${FACMAN_ULK_LOCK_REMOTE}"
      LOCK_REF "${FACMAN_ULK_LOCK_REQUIRED_REF}"
      REPOSITORY "${FACMAN_ULK_RELEASE_REPOSITORY}"
      RELEASE_SOURCE "${FACMAN_ULK_RELEASE_SOURCE_REVISION}"
      RELEASE_PACKAGE_VERSION "${FACMAN_ULK_RELEASE_PACKAGE_VERSION}"
      RELEASE_PACKAGE_IDENTITY_KIND "${FACMAN_ULK_RELEASE_PACKAGE_IDENTITY_KIND}"
      RELEASE_CONSUMPTION_MODE "${FACMAN_ULK_RELEASE_CONSUMPTION_MODE}"
      ABI_VERSION "${FACMAN_ULK_RELEASE_ABI_VERSION}"
      ABI_SCHEMA ulk.c_abi_snapshot.v1
      CONTRACT_SET_ID "${FACMAN_ULK_RELEASE_CONTRACT_SET_ID}"
      CONTRACT_DIGEST "${FACMAN_ULK_RELEASE_CONTRACT_DIGEST}"
      REQUIRED_TARGETS UniversalLauncher::Headers UniversalLauncher::CoreStatic UniversalLauncher::CoreShared
      REQUIRED_CONTRACTS
        composition/product_descriptor.v2.schema.json
        composition/entrypoint_descriptor.v1.schema.json
        composition/launch_capability.v1.schema.json
        composition/product_composition.v1.schema.json
        composition/contract_set_identity.v1.schema.json)
    _facman_validate_installed_provider(FACMAN_USK_PRE
      PRELOAD
      LABEL "Universal Setup"
      PROVIDER_ID universal_setup
      PACKAGE_NAME UniversalSetup
      PACKAGE_VERSION 1.0.0
      IDENTITY_FILE "${FACMAN_UNIVERSAL_SETUP_IDENTITY_FILE}"
      SDK_ROOT "${FACMAN_UNIVERSAL_SETUP_SDK_ROOT}"
      LOCK_PIN "${FACMAN_USK_LOCK_PIN}"
      LOCK_TREE "${FACMAN_USK_LOCK_TREE}"
      LOCK_REMOTE "${FACMAN_USK_LOCK_REMOTE}"
      LOCK_REF "${FACMAN_USK_LOCK_REQUIRED_REF}"
      REPOSITORY "${FACMAN_USK_RELEASE_REPOSITORY}"
      RELEASE_SOURCE "${FACMAN_USK_RELEASE_SOURCE_REVISION}"
      RELEASE_PACKAGE_VERSION "${FACMAN_USK_RELEASE_PACKAGE_VERSION}"
      RELEASE_PACKAGE_IDENTITY_KIND "${FACMAN_USK_RELEASE_PACKAGE_IDENTITY_KIND}"
      RELEASE_CONSUMPTION_MODE "${FACMAN_USK_RELEASE_CONSUMPTION_MODE}"
      ABI_VERSION "${FACMAN_USK_RELEASE_ABI_VERSION}"
      ABI_SCHEMA universal_setup.c_abi.v1
      CONTRACT_SET_ID "${FACMAN_USK_RELEASE_CONTRACT_SET_ID}"
      CONTRACT_DIGEST "${FACMAN_USK_RELEASE_CONTRACT_DIGEST}"
      REQUIRED_TARGETS UniversalSetup::Headers UniversalSetup::CoreStatic UniversalSetup::CoreShared
      REQUIRED_CONTRACTS
        package/component_manifest.v1.schema.json
        package/product_package.v1.schema.json
        package/source_manifest.v1.schema.json
        setup/product_setup_recipe.v1.schema.json
        state/installed_state_compatibility.v1.schema.json)
    unset(UniversalLauncher_DIR CACHE)
    unset(UniversalSetup_DIR CACHE)
    find_package(UniversalLauncher 1.8.0 EXACT CONFIG REQUIRED
      PATHS "${FACMAN_UNIVERSAL_LAUNCHER_SDK_ROOT}" NO_DEFAULT_PATH)
    find_package(UniversalSetup 1.0.0 EXACT CONFIG REQUIRED
      PATHS "${FACMAN_UNIVERSAL_SETUP_SDK_ROOT}" NO_DEFAULT_PATH)

    _facman_validate_installed_provider(FACMAN_ULK_SDK
      LABEL "Universal Launcher"
      PROVIDER_ID universal_launcher
      PACKAGE_NAME UniversalLauncher
      PACKAGE_VERSION 1.8.0
      IDENTITY_FILE "${FACMAN_UNIVERSAL_LAUNCHER_IDENTITY_FILE}"
      SDK_ROOT "${FACMAN_UNIVERSAL_LAUNCHER_SDK_ROOT}"
      LOCK_PIN "${FACMAN_ULK_LOCK_PIN}"
      LOCK_TREE "${FACMAN_ULK_LOCK_TREE}"
      LOCK_REMOTE "${FACMAN_ULK_LOCK_REMOTE}"
      LOCK_REF "${FACMAN_ULK_LOCK_REQUIRED_REF}"
      REPOSITORY "${FACMAN_ULK_RELEASE_REPOSITORY}"
      RELEASE_SOURCE "${FACMAN_ULK_RELEASE_SOURCE_REVISION}"
      RELEASE_PACKAGE_VERSION "${FACMAN_ULK_RELEASE_PACKAGE_VERSION}"
      RELEASE_PACKAGE_IDENTITY_KIND "${FACMAN_ULK_RELEASE_PACKAGE_IDENTITY_KIND}"
      RELEASE_CONSUMPTION_MODE "${FACMAN_ULK_RELEASE_CONSUMPTION_MODE}"
      ABI_VERSION "${FACMAN_ULK_RELEASE_ABI_VERSION}"
      ABI_SCHEMA ulk.c_abi_snapshot.v1
      CONTRACT_SET_ID "${FACMAN_ULK_RELEASE_CONTRACT_SET_ID}"
      CONTRACT_DIGEST "${FACMAN_ULK_RELEASE_CONTRACT_DIGEST}"
      REQUIRED_TARGETS UniversalLauncher::Headers UniversalLauncher::CoreStatic UniversalLauncher::CoreShared
      REQUIRED_CONTRACTS
        composition/product_descriptor.v2.schema.json
        composition/entrypoint_descriptor.v1.schema.json
        composition/launch_capability.v1.schema.json
        composition/product_composition.v1.schema.json
        composition/contract_set_identity.v1.schema.json)
    _facman_validate_installed_provider(FACMAN_USK_SDK
      LABEL "Universal Setup"
      PROVIDER_ID universal_setup
      PACKAGE_NAME UniversalSetup
      PACKAGE_VERSION 1.0.0
      IDENTITY_FILE "${FACMAN_UNIVERSAL_SETUP_IDENTITY_FILE}"
      SDK_ROOT "${FACMAN_UNIVERSAL_SETUP_SDK_ROOT}"
      LOCK_PIN "${FACMAN_USK_LOCK_PIN}"
      LOCK_TREE "${FACMAN_USK_LOCK_TREE}"
      LOCK_REMOTE "${FACMAN_USK_LOCK_REMOTE}"
      LOCK_REF "${FACMAN_USK_LOCK_REQUIRED_REF}"
      REPOSITORY "${FACMAN_USK_RELEASE_REPOSITORY}"
      RELEASE_SOURCE "${FACMAN_USK_RELEASE_SOURCE_REVISION}"
      RELEASE_PACKAGE_VERSION "${FACMAN_USK_RELEASE_PACKAGE_VERSION}"
      RELEASE_PACKAGE_IDENTITY_KIND "${FACMAN_USK_RELEASE_PACKAGE_IDENTITY_KIND}"
      RELEASE_CONSUMPTION_MODE "${FACMAN_USK_RELEASE_CONSUMPTION_MODE}"
      ABI_VERSION "${FACMAN_USK_RELEASE_ABI_VERSION}"
      ABI_SCHEMA universal_setup.c_abi.v1
      CONTRACT_SET_ID "${FACMAN_USK_RELEASE_CONTRACT_SET_ID}"
      CONTRACT_DIGEST "${FACMAN_USK_RELEASE_CONTRACT_DIGEST}"
      REQUIRED_TARGETS UniversalSetup::Headers UniversalSetup::CoreStatic UniversalSetup::CoreShared
      REQUIRED_CONTRACTS
        package/component_manifest.v1.schema.json
        package/product_package.v1.schema.json
        package/source_manifest.v1.schema.json
        setup/product_setup_recipe.v1.schema.json
        state/installed_state_compatibility.v1.schema.json)

    set(FACMAN_UNIVERSAL_LAUNCHER_REVISION "${FACMAN_ULK_SDK_SOURCE_COMMIT}")
    set(FACMAN_UNIVERSAL_SETUP_REVISION "${FACMAN_USK_SDK_SOURCE_COMMIT}")
    set(FACMAN_UNIVERSAL_LAUNCHER_TREE "${FACMAN_ULK_SDK_SOURCE_TREE}")
    set(FACMAN_UNIVERSAL_SETUP_TREE "${FACMAN_USK_SDK_SOURCE_TREE}")
    set(FACMAN_UNIVERSAL_LAUNCHER_INCLUDE_DIR "${FACMAN_ULK_SDK_INCLUDE_DIR}")
    set(FACMAN_UNIVERSAL_LAUNCHER_HEADERS_TARGET UniversalLauncher::Headers)
    set(FACMAN_UNIVERSAL_SETUP_HEADERS_TARGET UniversalSetup::Headers)
    if(FACMAN_PROVIDER_MODE STREQUAL "installed_static")
      set(FACMAN_UNIVERSAL_LAUNCHER_CORE_TARGET UniversalLauncher::CoreStatic)
      set(FACMAN_UNIVERSAL_LAUNCHER_SHARED_CLOSURE_TARGET UniversalLauncher::CoreStatic)
      set(FACMAN_UNIVERSAL_SETUP_CORE_TARGET UniversalSetup::CoreStatic)
    else()
      if(CMAKE_VERSION VERSION_LESS 3.21)
        message(FATAL_ERROR "installed_shared requires CMake 3.21 for private runtime closure installation")
      endif()
      set(FACMAN_UNIVERSAL_LAUNCHER_CORE_TARGET UniversalLauncher::CoreShared)
      set(FACMAN_UNIVERSAL_LAUNCHER_SHARED_CLOSURE_TARGET UniversalLauncher::CoreShared)
      set(FACMAN_UNIVERSAL_SETUP_CORE_TARGET UniversalSetup::CoreShared)
      set(FACMAN_UNIVERSAL_LAUNCHER_RUNTIME_TARGET UniversalLauncher::CoreShared)
      set(FACMAN_UNIVERSAL_SETUP_RUNTIME_TARGET UniversalSetup::CoreShared)
    endif()
    set(FACMAN_PROVIDER_PRIVATE_SOURCE_TARGETS_AVAILABLE FALSE)
    message(STATUS
      "FacMan providers: ${FACMAN_PROVIDER_MODE}; classification=${FACMAN_PROVIDER_CONSUMPTION_CLASSIFICATION} (source-only private USK tests are excluded)")
  endif()

  _facman_validate_play_evidence_provider_availability(
    "${FACMAN_PROVIDER_PRIVATE_SOURCE_TARGETS_AVAILABLE}")

  _facman_define_provider_wrapper(facman_provider_launcher_headers
    FacManProvider::LauncherHeaders "${FACMAN_UNIVERSAL_LAUNCHER_HEADERS_TARGET}")
  _facman_define_provider_wrapper(facman_provider_launcher
    FacManProvider::Launcher "${FACMAN_UNIVERSAL_LAUNCHER_CORE_TARGET}")
  _facman_define_provider_wrapper(facman_provider_launcher_shared_closure
    FacManProvider::LauncherSharedClosure "${FACMAN_UNIVERSAL_LAUNCHER_SHARED_CLOSURE_TARGET}")
  if(FACMAN_WITH_SETUP)
    _facman_define_provider_wrapper(facman_provider_setup_headers
      FacManProvider::SetupHeaders "${FACMAN_UNIVERSAL_SETUP_HEADERS_TARGET}")
    _facman_define_provider_wrapper(facman_provider_setup
      FacManProvider::Setup "${FACMAN_UNIVERSAL_SETUP_CORE_TARGET}")
  endif()
  set(FACMAN_UNIVERSAL_LAUNCHER_TARGET FacManProvider::Launcher)
  set(FACMAN_UNIVERSAL_LAUNCHER_SHARED_TARGET FacManProvider::LauncherSharedClosure)
  set(FACMAN_UNIVERSAL_SETUP_TARGET FacManProvider::Setup)
endmacro()
