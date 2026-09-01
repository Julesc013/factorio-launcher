# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

find_package(Python3 REQUIRED COMPONENTS Interpreter)

file(GLOB_RECURSE FACMAN_RUNTIME_RESOURCE_INPUTS CONFIGURE_DEPENDS
  "${PROJECT_SOURCE_DIR}/contracts/schema/*"
  "${PROJECT_SOURCE_DIR}/contracts/command/*"
  "${PROJECT_SOURCE_DIR}/contracts/generated-index/*"
  "${PROJECT_SOURCE_DIR}/contracts/policy/*"
  "${PROJECT_SOURCE_DIR}/content/factorio/*")
list(APPEND FACMAN_RUNTIME_RESOURCE_INPUTS
  "${PROJECT_SOURCE_DIR}/release/index/version.v2.toml"
  "${PROJECT_SOURCE_DIR}/release/index/product.v2.toml"
  "${PROJECT_SOURCE_DIR}/release/index/providers.lock.v2.toml"
  "${PROJECT_SOURCE_DIR}/release/index/workspace_lock.v1.toml"
  "${PROJECT_SOURCE_DIR}/release/index/support.v2.toml"
  "${PROJECT_SOURCE_DIR}/release/index/technical_preview_scope.v1.toml")
list(APPEND FACMAN_RUNTIME_RESOURCE_INPUTS
  "${PROJECT_SOURCE_DIR}/release/index/foundation_public_beta_scope.v2.toml")

set(FACMAN_RUNTIME_RESOURCE_PACK
  "${CMAKE_CURRENT_BINARY_DIR}/generated/facman.resources")
add_custom_command(
  OUTPUT "${FACMAN_RUNTIME_RESOURCE_PACK}"
  COMMAND "${Python3_EXECUTABLE}" "${PROJECT_SOURCE_DIR}/tools/resource_pack.py"
    build --root "${PROJECT_SOURCE_DIR}" --out "${FACMAN_RUNTIME_RESOURCE_PACK}"
  DEPENDS "${PROJECT_SOURCE_DIR}/tools/resource_pack.py" ${FACMAN_RUNTIME_RESOURCE_INPUTS}
  COMMENT "Building deterministic FacMan runtime resource pack"
  VERBATIM)
add_custom_target(facman_runtime_resources ALL
  DEPENDS "${FACMAN_RUNTIME_RESOURCE_PACK}")
