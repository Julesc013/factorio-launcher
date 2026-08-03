// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "command_client.h"
#include "generated_rpc_request.h"

#include <errno.h>
#include <signal.h>
#include <stdlib.h>
#include <string.h>
#include <sys/types.h>
#include <unistd.h>

enum {
    FACMAN_RPC_TIMEOUT_SECONDS = 30,
    FACMAN_RPC_STDOUT_LIMIT = 16 * 1024 * 1024,
    FACMAN_RPC_STDERR_LIMIT = 64 * 1024
};

typedef struct {
    GSubprocess *process;
    GCancellable *cancellable;
    guint timeout_id;
    FacManGtkRpcCompletion completion;
    gpointer user_data;
} FacManGtkRpcCall;

static gboolean facman_gtk_rpc_timeout(gpointer user_data)
{
    FacManGtkRpcCall *call = user_data;
    call->timeout_id = 0;
    g_cancellable_cancel(call->cancellable);
    const gchar *identifier = g_subprocess_get_identifier(call->process);
    if (identifier != NULL) {
        gchar *end = NULL;
        errno = 0;
        long pid = strtol(identifier, &end, 10);
        if (errno == 0 && end != identifier && *end == '\0' && pid > 1)
            (void)kill((pid_t)-pid, SIGTERM);
    }
    g_subprocess_force_exit(call->process);
    return G_SOURCE_REMOVE;
}

static void facman_gtk_rpc_child_setup(gpointer user_data)
{
    (void)user_data;
    (void)setpgid(0, 0);
}

static guint facman_gtk_rpc_timeout_seconds(void)
{
    const gchar *configured = g_getenv("FACMAN_PREVIEW_RPC_TIMEOUT_SECONDS");
    if (configured == NULL || *configured == '\0') return FACMAN_RPC_TIMEOUT_SECONDS;
    gchar *end = NULL;
    unsigned long value = strtoul(configured, &end, 10);
    if (end == configured || *end != '\0' || value == 0 || value > FACMAN_RPC_TIMEOUT_SECONDS)
        return FACMAN_RPC_TIMEOUT_SECONDS;
    return (guint)value;
}

static void facman_gtk_rpc_complete(GObject *source, GAsyncResult *result, gpointer user_data)
{
    FacManGtkRpcCall *call = user_data;
    gchar *stdout_text = NULL;
    gchar *stderr_text = NULL;
    GError *error = NULL;
    gboolean ok = g_subprocess_communicate_utf8_finish(
        G_SUBPROCESS(source), result, &stdout_text, &stderr_text, &error);
    if (call->timeout_id != 0)
        g_source_remove(call->timeout_id);

    gchar *message = NULL;
    if (!ok && g_error_matches(error, G_IO_ERROR, G_IO_ERROR_CANCELLED)) {
        message = g_strdup(
            "outcome_unknown: bounded process RPC timed out after dispatch; inspect Activity/recovery before retrying");
    } else if (!ok) {
        message = g_strdup_printf("frontend_backend_error: %s", error != NULL ? error->message : "unknown error");
    } else if (strlen(stdout_text != NULL ? stdout_text : "") > FACMAN_RPC_STDOUT_LIMIT
               || strlen(stderr_text != NULL ? stderr_text : "") > FACMAN_RPC_STDERR_LIMIT) {
        message = g_strdup("frontend_backend_output_too_large: bounded output budget exceeded");
    } else if (!g_subprocess_get_successful(call->process)) {
        message = g_strdup_printf("structured refusal\n%s\n%s",
            stdout_text != NULL ? stdout_text : "", stderr_text != NULL ? stderr_text : "");
    } else {
        message = g_strdup(stdout_text != NULL && *stdout_text != '\0' ? stdout_text : "RPC completed with no output");
    }
    call->completion(message, call->user_data);
    g_free(message);
    g_free(stdout_text);
    g_free(stderr_text);
    g_clear_error(&error);
    g_object_unref(call->process);
    g_object_unref(call->cancellable);
    g_free(call);
}

void facman_gtk_rpc_invoke(
    const gchar *cli_path,
    const gchar *workspace,
    const gchar *command,
    FacManGtkRpcCompletion completion,
    gpointer user_data)
{
    facman_gtk_rpc_invoke_payload(
        cli_path, workspace, command, "{}", TRUE, completion, user_data);
}

void facman_gtk_rpc_invoke_payload(
    const gchar *cli_path,
    const gchar *workspace,
    const gchar *command,
    const gchar *payload_json,
    gboolean dry_run,
    FacManGtkRpcCompletion completion,
    gpointer user_data)
{
    const gchar *configured = cli_path != NULL ? cli_path : "";
    if (*configured == '\0') configured = g_getenv("FACMAN_CLI");
    if (configured == NULL || *configured == '\0') configured = "facman";
    const gchar *argv[] = { configured, "rpc", "--stdio", NULL };
    GError *error = NULL;
    GSubprocessLauncher *launcher = g_subprocess_launcher_new(
        G_SUBPROCESS_FLAGS_STDIN_PIPE | G_SUBPROCESS_FLAGS_STDOUT_PIPE | G_SUBPROCESS_FLAGS_STDERR_PIPE);
    g_subprocess_launcher_set_child_setup(launcher, facman_gtk_rpc_child_setup, NULL, NULL);
    GSubprocess *process = g_subprocess_launcher_spawnv(launcher, argv, &error);
    g_object_unref(launcher);
    if (process == NULL) {
        gchar *message = g_strdup_printf("frontend_backend_unavailable: %s",
            error != NULL ? error->message : "could not start facman");
        completion(message, user_data);
        g_free(message);
        g_clear_error(&error);
        return;
    }

    gchar *request = facman_preview_generated_rpc_request_with_payload(
        workspace, command, payload_json, dry_run);

    FacManGtkRpcCall *call = g_new0(FacManGtkRpcCall, 1);
    call->process = process;
    call->cancellable = g_cancellable_new();
    call->completion = completion;
    call->user_data = user_data;
    call->timeout_id = g_timeout_add_seconds(facman_gtk_rpc_timeout_seconds(), facman_gtk_rpc_timeout, call);
    g_subprocess_communicate_utf8_async(
        process, request, call->cancellable, facman_gtk_rpc_complete, call);
    g_free(request);
}
