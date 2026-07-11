# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

cmake_minimum_required(VERSION 3.16)
project(factorio_qt LANGUAGES CXX)

add_executable(factorio_qt
  main.cpp
  command_client.cpp
)
