cmake_minimum_required(VERSION 3.16)
project(factorio_launcher LANGUAGES C CXX)

option(FLAUNCH_BUILD_NATIVE_CLI "Build the native CLI scaffold" ON)

add_library(ulk INTERFACE)
target_include_directories(ulk INTERFACE
  ${CMAKE_CURRENT_SOURCE_DIR}/include
)

add_library(usk INTERFACE)
target_include_directories(usk INTERFACE
  ${CMAKE_CURRENT_SOURCE_DIR}/include
)

add_library(flb_factorio INTERFACE)
target_include_directories(flb_factorio INTERFACE
  ${CMAKE_CURRENT_SOURCE_DIR}/include
)
target_link_libraries(flb_factorio INTERFACE ulk)

if(FLAUNCH_BUILD_NATIVE_CLI)
  add_executable(factorio_cli
    apps/factorio_cli/src/main.c
    apps/factorio_cli/src/json_mode.c
    apps/factorio_cli/src/command_dispatch.c
  )
  target_link_libraries(factorio_cli PRIVATE ulk flb_factorio)
endif()
