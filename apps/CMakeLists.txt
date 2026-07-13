# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

if(FACMAN_BUILD_GUI)
  message(FATAL_ERROR
    "FACMAN_BUILD_GUI does not build an in-tree GUI target. Native GUI shells use their documented external build lanes; select FACMAN_BUILD_CLI or FACMAN_BUILD_TUI here.")
endif()

if(FACMAN_BUILD_CLI)
  add_subdirectory(cli)
endif()
if(FACMAN_BUILD_TUI)
  add_subdirectory(tui)
endif()
if(FACMAN_BUILD_DAEMON)
  add_subdirectory(daemon)
endif()
