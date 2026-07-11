add_library(facman_workspace_static STATIC fl_workspace_store.cpp)
target_include_directories(facman_workspace_static PUBLIC
  ${CMAKE_CURRENT_SOURCE_DIR}
  ${PROJECT_SOURCE_DIR}/runtime/core
  ${PROJECT_SOURCE_DIR}/runtime/core/json
  ${PROJECT_SOURCE_DIR}/runtime/base
  ${PROJECT_SOURCE_DIR}/runtime/platform
)
target_compile_features(facman_workspace_static PUBLIC cxx_std_17)
target_link_libraries(facman_workspace_static PUBLIC facman_base_static facman_core_static facman_platform_static)
add_library(facman::workspace ALIAS facman_workspace_static)
facman_apply_policies(facman_workspace_static)
