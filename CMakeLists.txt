cmake_minimum_required(VERSION 3.16)
project(factorio_launcher LANGUAGES C CXX)

option(FLAUNCH_BUILD_NATIVE_CLI "Build the native CLI scaffold" ON)

add_library(universal_launcher_abi INTERFACE)
target_include_directories(universal_launcher_abi INTERFACE
  ${CMAKE_CURRENT_SOURCE_DIR}/universal/include
)

add_library(factorio_binding_abi INTERFACE)
target_include_directories(factorio_binding_abi INTERFACE
  ${CMAKE_CURRENT_SOURCE_DIR}/factorio/include
  ${CMAKE_CURRENT_SOURCE_DIR}/universal/include
)
target_link_libraries(factorio_binding_abi INTERFACE universal_launcher_abi)

if(FLAUNCH_BUILD_NATIVE_CLI)
  add_executable(factorio_launcher_cli
    cli/src/main.c
    cli/src/json_mode.c
    cli/src/command_dispatch.c
  )
  target_link_libraries(factorio_launcher_cli PRIVATE universal_launcher_abi factorio_binding_abi)
endif()

