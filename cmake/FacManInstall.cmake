# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

include(GNUInstallDirs)
include(CMakePackageConfigHelpers)

if(TARGET facman_cli)
  install(TARGETS facman_cli RUNTIME DESTINATION ${CMAKE_INSTALL_BINDIR} COMPONENT CLI)
endif()
if(TARGET facman_tui)
  install(TARGETS facman_tui RUNTIME DESTINATION ${CMAKE_INSTALL_BINDIR} COMPONENT TUI)
endif()
install(TARGETS flb_factorio_shared
  EXPORT FacManTargets
  RUNTIME DESTINATION ${CMAKE_INSTALL_BINDIR} COMPONENT Runtime
  LIBRARY DESTINATION ${CMAKE_INSTALL_LIBDIR} COMPONENT Runtime NAMELINK_COMPONENT Development
  ARCHIVE DESTINATION ${CMAKE_INSTALL_LIBDIR} COMPONENT Development
  INCLUDES DESTINATION ${CMAKE_INSTALL_INCLUDEDIR})
if(TARGET ulk_shared)
  set_target_properties(ulk_shared PROPERTIES EXPORT_NAME ulk)
  set_property(TARGET ulk_shared PROPERTY INTERFACE_INCLUDE_DIRECTORIES
    "$<BUILD_INTERFACE:${FLAUNCH_UNIVERSAL_LAUNCHER_ROOT}/include>;$<INSTALL_INTERFACE:include>")
  install(TARGETS ulk_shared
    EXPORT FacManTargets
    RUNTIME DESTINATION ${CMAKE_INSTALL_BINDIR} COMPONENT Runtime
    LIBRARY DESTINATION ${CMAKE_INSTALL_LIBDIR} COMPONENT Runtime NAMELINK_COMPONENT Development
    ARCHIVE DESTINATION ${CMAKE_INSTALL_LIBDIR} COMPONENT Development
    INCLUDES DESTINATION ${CMAKE_INSTALL_INCLUDEDIR})
endif()
if(TARGET usk_shared)
  install(TARGETS usk_shared LIBRARY DESTINATION ${CMAKE_INSTALL_LIBDIR} RUNTIME DESTINATION ${CMAKE_INSTALL_BINDIR} COMPONENT Runtime)
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
install(DIRECTORY ${FLAUNCH_UNIVERSAL_LAUNCHER_ROOT}/include/ulk
  DESTINATION ${CMAKE_INSTALL_INCLUDEDIR} COMPONENT Development)
install(FILES ${FLAUNCH_UNIVERSAL_LAUNCHER_ROOT}/README.md
  DESTINATION ${CMAKE_INSTALL_DOCDIR}/providers
  RENAME Universal-Launcher-README.md
  COMPONENT Documentation)

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
install(FILES ${CMAKE_CURRENT_BINARY_DIR}/facman-flb.pc
  DESTINATION ${CMAKE_INSTALL_LIBDIR}/pkgconfig
  COMPONENT Development)
install(FILES ${PROJECT_SOURCE_DIR}/contracts/abi/flb/compatibility.v1.json
  DESTINATION ${CMAKE_INSTALL_DATADIR}/facman/abi
  COMPONENT Development)

set(FACMAN_INSTALL_MANIFEST ${CMAKE_CURRENT_BINARY_DIR}/facman-install-artifact-manifest.v1.json)
file(WRITE ${FACMAN_INSTALL_MANIFEST}
  "{\n  \"schema\": \"facman.install_artifact_manifest.v1\",\n  \"components\": [\"Runtime\", \"CLI\", \"TUI\", \"Contracts\", \"Content\", \"Documentation\", \"Licenses\", \"Development\"],\n  \"sdk\": {\"cmake_package\": \"FacMan\", \"pkg_config\": \"facman-flb\", \"flb_abi\": \"1.2\", \"required_ulk_abi\": \"1.2\"}\n}\n")
install(FILES ${FACMAN_INSTALL_MANIFEST} DESTINATION ${CMAKE_INSTALL_DATADIR}/facman/manifest COMPONENT Runtime)
