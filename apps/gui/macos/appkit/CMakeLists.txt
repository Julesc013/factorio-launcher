# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

cmake_minimum_required(VERSION 3.20)
project(FacManAppKit LANGUAGES C CXX OBJC OBJCXX)

if(NOT APPLE)
  message(FATAL_ERROR "The AppKit preview bundle must be built on macOS")
endif()

set(CMAKE_OSX_ARCHITECTURES "x86_64" CACHE STRING "C1 preview architecture" FORCE)
set(CMAKE_OSX_DEPLOYMENT_TARGET "10.13" CACHE STRING "C1 preview deployment floor" FORCE)

add_executable(FacMan MACOSX_BUNDLE
  main.m
  AppDelegate.m
  MainWindowController.m
  FacManPreviewFixture.m
  CommandClient.mm
  CliProcessClient.mm
  FacManGeneratedCommandCatalog.m)
target_compile_features(FacMan PRIVATE cxx_std_17)
target_compile_options(FacMan PRIVATE -fobjc-arc -fblocks -fmodules)
target_link_libraries(FacMan PRIVATE "-framework Cocoa")
set_target_properties(FacMan PROPERTIES
  MACOSX_BUNDLE_INFO_PLIST "${CMAKE_CURRENT_SOURCE_DIR}/Info.plist"
  XCODE_ATTRIBUTE_ARCHS "x86_64"
  XCODE_ATTRIBUTE_MACOSX_DEPLOYMENT_TARGET "10.13")

install(TARGETS FacMan BUNDLE DESTINATION . COMPONENT appkit_preview)
