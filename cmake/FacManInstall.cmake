# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

include(GNUInstallDirs)
include(CMakePackageConfigHelpers)

if(FACMAN_PROVIDER_CONFORMANCE_ONLY)
  message(STATUS
    "FacMan install/package rules are disabled for provider conformance-only configurations")
  return()
endif()

if(FACMAN_PROVIDER_SDK_CONSUMPTION_CANDIDATE)
  message(STATUS
    "FacMan install/package rules are enabled for a non-adopted, release-ineligible SDK candidate")
endif()

if(TARGET facman_cli)
  install(TARGETS facman_cli RUNTIME DESTINATION ${CMAKE_INSTALL_BINDIR} COMPONENT CLI)
endif()
if(TARGET facman_tui)
  install(TARGETS facman_tui RUNTIME DESTINATION ${CMAKE_INSTALL_BINDIR} COMPONENT TUI)
endif()
if(FACMAN_PROVIDER_MODE STREQUAL "source"
    AND FACMAN_PROVIDER_SOURCE_LINKAGE STREQUAL "shared")
  install(TARGETS flb_factorio_shared
    EXPORT FacManTargets
    RUNTIME DESTINATION ${CMAKE_INSTALL_BINDIR} COMPONENT Runtime
    LIBRARY DESTINATION ${CMAKE_INSTALL_LIBDIR} COMPONENT Runtime NAMELINK_COMPONENT Development
    ARCHIVE DESTINATION ${CMAKE_INSTALL_LIBDIR} COMPONENT Development
    INCLUDES DESTINATION ${CMAKE_INSTALL_INCLUDEDIR})
  set(facman_install_shared_export TRUE)
  set(facman_source_provider_runtime_targets
    ${FACMAN_UNIVERSAL_LAUNCHER_RUNTIME_TARGET})
  if(FACMAN_WITH_SETUP)
    list(APPEND facman_source_provider_runtime_targets
      ${FACMAN_UNIVERSAL_SETUP_RUNTIME_TARGET})
  endif()
  install(TARGETS ${facman_source_provider_runtime_targets}
    RUNTIME DESTINATION ${CMAKE_INSTALL_BINDIR} COMPONENT Runtime
    LIBRARY DESTINATION ${CMAKE_INSTALL_LIBDIR} COMPONENT Runtime NAMELINK_COMPONENT Development
    ARCHIVE DESTINATION ${CMAKE_INSTALL_LIBDIR} COMPONENT Development)
elseif(FACMAN_PROVIDER_MODE STREQUAL "installed_shared")
  install(TARGETS flb_factorio_shared
    EXPORT FacManTargets
    RUNTIME DESTINATION ${CMAKE_INSTALL_BINDIR} COMPONENT Runtime
    LIBRARY DESTINATION ${CMAKE_INSTALL_LIBDIR} COMPONENT Runtime NAMELINK_COMPONENT Development
    ARCHIVE DESTINATION ${CMAKE_INSTALL_LIBDIR} COMPONENT Development
    INCLUDES DESTINATION ${CMAKE_INSTALL_INCLUDEDIR})
  set(facman_install_shared_export TRUE)
  set(facman_provider_runtime_targets
    ${FACMAN_UNIVERSAL_LAUNCHER_RUNTIME_TARGET})
  if(FACMAN_WITH_SETUP)
    list(APPEND facman_provider_runtime_targets
      ${FACMAN_UNIVERSAL_SETUP_RUNTIME_TARGET})
  endif()
  install(IMPORTED_RUNTIME_ARTIFACTS ${facman_provider_runtime_targets}
    RUNTIME DESTINATION ${CMAKE_INSTALL_BINDIR} COMPONENT Runtime
    LIBRARY DESTINATION ${CMAKE_INSTALL_LIBDIR} COMPONENT Runtime
    FRAMEWORK DESTINATION ${CMAKE_INSTALL_LIBDIR} COMPONENT Runtime)
else()
  # Static product packages select runtime components explicitly and therefore
  # exclude this development-only compatibility SDK runtime. A complete SDK
  # install still receives the relocatable FacMan::flb export and its DLL.
  install(TARGETS flb_factorio_shared
    EXPORT FacManTargets
    RUNTIME DESTINATION ${CMAKE_INSTALL_BINDIR} COMPONENT Development
    LIBRARY DESTINATION ${CMAKE_INSTALL_LIBDIR} COMPONENT Development
    ARCHIVE DESTINATION ${CMAKE_INSTALL_LIBDIR} COMPONENT Development
    INCLUDES DESTINATION ${CMAKE_INSTALL_INCLUDEDIR})
  set(facman_install_shared_export TRUE)
endif()
install(DIRECTORY ${PROJECT_SOURCE_DIR}/contracts/schema/ DESTINATION ${CMAKE_INSTALL_DATADIR}/facman/contracts/schema COMPONENT Contracts)
install(DIRECTORY ${PROJECT_SOURCE_DIR}/content/factorio/ DESTINATION ${CMAKE_INSTALL_DATADIR}/facman/content/factorio COMPONENT Content)
install(DIRECTORY ${PROJECT_SOURCE_DIR}/docs/ DESTINATION ${CMAKE_INSTALL_DOCDIR} COMPONENT Documentation)
install(DIRECTORY ${PROJECT_SOURCE_DIR}/release/ DESTINATION ${CMAKE_INSTALL_DATADIR}/facman/release COMPONENT Runtime)
install(FILES ${PROJECT_SOURCE_DIR}/README.md DESTINATION ${CMAKE_INSTALL_DOCDIR} COMPONENT Documentation)
install(FILES
  ${PROJECT_SOURCE_DIR}/LICENSE
  ${PROJECT_SOURCE_DIR}/THIRD_PARTY_NOTICES.md
  ${PROJECT_SOURCE_DIR}/LICENSES/UniversalLauncher.txt
  ${PROJECT_SOURCE_DIR}/LICENSES/UniversalSetup.txt
  ${PROJECT_SOURCE_DIR}/LICENSES/Miniz.txt
  ${PROJECT_SOURCE_DIR}/LICENSES/PicoJSON.txt
  DESTINATION ${CMAKE_INSTALL_DOCDIR}/licenses
  COMPONENT Licenses)
install(DIRECTORY ${PROJECT_SOURCE_DIR}/include/ DESTINATION ${CMAKE_INSTALL_INCLUDEDIR} COMPONENT Development)
install(DIRECTORY ${FACMAN_UNIVERSAL_LAUNCHER_INCLUDE_DIR}/ulk
  DESTINATION ${CMAKE_INSTALL_INCLUDEDIR} COMPONENT Development)
if(FACMAN_PROVIDER_MODE STREQUAL "source")
  install(FILES ${FLAUNCH_UNIVERSAL_LAUNCHER_ROOT}/README.md
    DESTINATION ${CMAKE_INSTALL_DOCDIR}/providers
    RENAME Universal-Launcher-README.md
    COMPONENT Documentation)
endif()

set(FACMAN_CMAKE_INSTALL_DIR ${CMAKE_INSTALL_LIBDIR}/cmake/FacMan)
configure_package_config_file(
  ${PROJECT_SOURCE_DIR}/cmake/FacManConfig.cmake.in
  ${CMAKE_CURRENT_BINARY_DIR}/FacManConfig.cmake
  INSTALL_DESTINATION ${FACMAN_CMAKE_INSTALL_DIR})
write_basic_package_version_file(
  ${CMAKE_CURRENT_BINARY_DIR}/FacManConfigVersion.cmake
  VERSION ${PROJECT_VERSION}
  COMPATIBILITY SameMajorVersion)
configure_file(
  ${PROJECT_SOURCE_DIR}/cmake/facman-flb.pc.in
  ${CMAKE_CURRENT_BINARY_DIR}/facman-flb.pc
  @ONLY)
if(facman_install_shared_export)
  install(EXPORT FacManTargets
    FILE FacManTargets.cmake
    NAMESPACE FacMan::
    DESTINATION ${FACMAN_CMAKE_INSTALL_DIR}
    COMPONENT Development)
  install(FILES
    ${CMAKE_CURRENT_BINARY_DIR}/FacManConfig.cmake
    ${CMAKE_CURRENT_BINARY_DIR}/FacManConfigVersion.cmake
    DESTINATION ${FACMAN_CMAKE_INSTALL_DIR}
    COMPONENT Development)
endif()
install(FILES ${CMAKE_CURRENT_BINARY_DIR}/facman-flb.pc
  DESTINATION ${CMAKE_INSTALL_LIBDIR}/pkgconfig
  COMPONENT Development)
install(FILES ${PROJECT_SOURCE_DIR}/contracts/abi/flb/compatibility.v1.json
  DESTINATION ${CMAKE_INSTALL_DATADIR}/facman/abi
  COMPONENT Development)

set(FACMAN_INSTALL_MANIFEST ${CMAKE_CURRENT_BINARY_DIR}/facman-install-artifact-manifest.v1.json)
file(WRITE ${FACMAN_INSTALL_MANIFEST}
  "{\n  \"schema\": \"facman.install_artifact_manifest.v1\",\n  \"components\": [\"Runtime\", \"CLI\", \"TUI\", \"Contracts\", \"Content\", \"Documentation\", \"Licenses\", \"Development\"],\n  \"sdk\": {\"cmake_package\": \"FacMan\", \"pkg_config\": \"facman-flb\", \"flb_abi\": \"1.3\", \"required_ulk_abi\": \"1.8\"}\n}\n")
install(FILES ${FACMAN_INSTALL_MANIFEST} DESTINATION ${CMAKE_INSTALL_DATADIR}/facman/manifest COMPONENT Runtime)
