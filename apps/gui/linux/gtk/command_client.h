// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#pragma once

#include <gio/gio.h>

typedef void (*FacManGtkRpcCompletion)(const gchar *result, gpointer user_data);

void facman_gtk_rpc_invoke(
    const gchar *cli_path,
    const gchar *workspace,
    const gchar *command,
    FacManGtkRpcCompletion completion,
    gpointer user_data);
