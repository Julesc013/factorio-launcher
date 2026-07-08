cmake_minimum_required(VERSION 3.16)
project(factorio_qt LANGUAGES CXX)

add_executable(factorio_qt
  ../../source/apps/qt/main.cpp
  ../../source/apps/qt/command_client.cpp
)
