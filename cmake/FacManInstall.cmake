include(GNUInstallDirs)

if(TARGET facman_cli)
  install(TARGETS facman_cli RUNTIME DESTINATION ${CMAKE_INSTALL_BINDIR} COMPONENT CLI)
endif()
install(TARGETS flb_factorio_shared LIBRARY DESTINATION ${CMAKE_INSTALL_LIBDIR} RUNTIME DESTINATION ${CMAKE_INSTALL_BINDIR} COMPONENT Runtime)
install(DIRECTORY ${PROJECT_SOURCE_DIR}/contracts/schema/ DESTINATION ${CMAKE_INSTALL_DATADIR}/facman/contracts/schema COMPONENT Contracts)
install(DIRECTORY ${PROJECT_SOURCE_DIR}/content/factorio/ DESTINATION ${CMAKE_INSTALL_DATADIR}/facman/content/factorio COMPONENT Content)
install(DIRECTORY ${PROJECT_SOURCE_DIR}/docs/ DESTINATION ${CMAKE_INSTALL_DOCDIR} COMPONENT Documentation)
install(FILES ${PROJECT_SOURCE_DIR}/LICENSE ${PROJECT_SOURCE_DIR}/THIRD_PARTY_NOTICES.md DESTINATION ${CMAKE_INSTALL_DOCDIR}/licenses COMPONENT Licenses)
install(DIRECTORY ${PROJECT_SOURCE_DIR}/include/ DESTINATION ${CMAKE_INSTALL_INCLUDEDIR} COMPONENT Development)

set(FACMAN_INSTALL_MANIFEST ${CMAKE_CURRENT_BINARY_DIR}/facman-install-artifact-manifest.v1.json)
file(WRITE ${FACMAN_INSTALL_MANIFEST}
  "{\n  \"schema\": \"facman.install_artifact_manifest.v1\",\n  \"components\": [\"Runtime\", \"CLI\", \"Contracts\", \"Content\", \"Documentation\", \"Licenses\", \"Development\"]\n}\n")
install(FILES ${FACMAN_INSTALL_MANIFEST} DESTINATION ${CMAKE_INSTALL_DATADIR}/facman/manifest COMPONENT Runtime)
