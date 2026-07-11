# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

add_executable(facman_tui tui_main.c tui_command_client.c tui_views.c)
target_link_libraries(facman_tui PRIVATE flaunch_client_static flaunch_runtime_static ulk_static)
set_target_properties(facman_tui PROPERTIES OUTPUT_NAME facman-tui)
facman_apply_policies(facman_tui)
