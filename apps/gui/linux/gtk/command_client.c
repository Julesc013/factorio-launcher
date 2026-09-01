// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "command_client.h"
#include "generated_rpc_request.h"
#include "transport_validator.h"

#include <errno.h>
#include <signal.h>
#include <stdlib.h>
#include <string.h>
#include <sys/types.h>
#include <unistd.h>

enum {
    FACMAN_RPC_TIMEOUT_SECONDS = 30,
    FACMAN_RPC_REQUEST_LIMIT = 1024 * 1024,
    FACMAN_RPC_STDOUT_LIMIT = 16 * 1024 * 1024,
    FACMAN_RPC_STDERR_LIMIT = 64 * 1024,
    FACMAN_RPC_READ_CHUNK = 8192
};

typedef struct {
    GSubprocess *process;
    GCancellable *cancellable;
    GByteArray *stdout_data;
    GByteArray *stderr_data;
    guint timeout_id;
    guint pending;
    gboolean termination_requested;
    gchar *failure;
    gchar *request_id;
    gchar *operation_id;
    gchar *attempt_id;
    gchar *command;
    FacManGtkRpcCompletion completion;
    gpointer user_data;
} FacManGtkRpcCall;

typedef struct {
    FacManGtkRpcCall *call;
    GInputStream *stream;
    GByteArray *destination;
    gsize limit;
} FacManGtkRpcRead;

static void facman_gtk_rpc_maybe_complete(FacManGtkRpcCall *call);

static void facman_gtk_rpc_set_failure(FacManGtkRpcCall *call, const gchar *failure)
{
    if (call->failure == NULL) call->failure = g_strdup(failure);
}

static pid_t facman_gtk_rpc_process_group(GSubprocess *process)
{
    const gchar *identifier = g_subprocess_get_identifier(process);
    if (identifier == NULL) return (pid_t)0;
    gchar *end = NULL;
    errno = 0;
    long pid = strtol(identifier, &end, 10);
    return errno == 0 && end != identifier && *end == '\0' && pid > 1
        ? (pid_t)pid : (pid_t)0;
}

static void facman_gtk_rpc_terminate_tree(FacManGtkRpcCall *call)
{
    if (call->termination_requested) return;
    call->termination_requested = TRUE;
    g_cancellable_cancel(call->cancellable);
    pid_t process_group = facman_gtk_rpc_process_group(call->process);
    if (process_group > 1) (void)kill(-process_group, SIGTERM);
    g_subprocess_force_exit(call->process);
    if (process_group > 1) (void)kill(-process_group, SIGKILL);
}

static gboolean facman_gtk_rpc_timeout(gpointer user_data)
{
    FacManGtkRpcCall *call = user_data;
    call->timeout_id = 0;
    facman_gtk_rpc_set_failure(call,
        "outcome_unknown: bounded process RPC timed out after dispatch; "
        "inspect Activity/recovery before retrying");
    facman_gtk_rpc_terminate_tree(call);
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

static void facman_gtk_rpc_part_done(FacManGtkRpcCall *call)
{
    g_assert(call->pending > 0);
    call->pending--;
    facman_gtk_rpc_maybe_complete(call);
}

static void facman_gtk_rpc_read_next(FacManGtkRpcRead *read);

static void facman_gtk_rpc_read_complete(
    GObject *source,
    GAsyncResult *result,
    gpointer user_data)
{
    FacManGtkRpcRead *read = user_data;
    GError *error = NULL;
    GBytes *chunk = g_input_stream_read_bytes_finish(G_INPUT_STREAM(source), result, &error);
    if (chunk == NULL) {
        if (!g_error_matches(error, G_IO_ERROR, G_IO_ERROR_CANCELLED)) {
            facman_gtk_rpc_set_failure(
                read->call, "outcome_unknown: frontend_backend_stream_error while draining "
                "the dispatched operation; inspect Activity/recovery before retrying");
            facman_gtk_rpc_terminate_tree(read->call);
        }
        g_clear_error(&error);
        FacManGtkRpcCall *call = read->call;
        g_free(read);
        facman_gtk_rpc_part_done(call);
        return;
    }

    gsize size = 0;
    const guint8 *data = g_bytes_get_data(chunk, &size);
    if (size == 0) {
        g_bytes_unref(chunk);
        FacManGtkRpcCall *call = read->call;
        g_free(read);
        facman_gtk_rpc_part_done(call);
        return;
    }
    if (read->destination->len > read->limit || size > read->limit - read->destination->len) {
        facman_gtk_rpc_set_failure(
            read->call, "outcome_unknown: frontend_backend_output_too_large after dispatch; "
            "inspect Activity/recovery before retrying");
        facman_gtk_rpc_terminate_tree(read->call);
        g_bytes_unref(chunk);
        FacManGtkRpcCall *call = read->call;
        g_free(read);
        facman_gtk_rpc_part_done(call);
        return;
    }
    g_byte_array_append(read->destination, data, size);
    g_bytes_unref(chunk);
    facman_gtk_rpc_read_next(read);
}

static void facman_gtk_rpc_read_next(FacManGtkRpcRead *read)
{
    g_input_stream_read_bytes_async(
        read->stream,
        FACMAN_RPC_READ_CHUNK,
        G_PRIORITY_DEFAULT,
        read->call->cancellable,
        facman_gtk_rpc_read_complete,
        read);
}

static void facman_gtk_rpc_wait_complete(
    GObject *source,
    GAsyncResult *result,
    gpointer user_data)
{
    FacManGtkRpcCall *call = user_data;
    GError *error = NULL;
    if (!g_subprocess_wait_finish(G_SUBPROCESS(source), result, &error)) {
        facman_gtk_rpc_set_failure(
            call, "outcome_unknown: frontend_backend_process_error while waiting for the "
            "dispatched operation; inspect Activity/recovery before retrying");
        facman_gtk_rpc_terminate_tree(call);
    }
    g_clear_error(&error);
    facman_gtk_rpc_part_done(call);
}

static void facman_gtk_rpc_maybe_complete(FacManGtkRpcCall *call)
{
    if (call->pending != 0) return;
    if (call->timeout_id != 0) {
        g_source_remove(call->timeout_id);
        call->timeout_id = 0;
    }

    gchar *message = call->failure != NULL ? g_strdup(call->failure) : NULL;
    if (message == NULL) {
        FacManGtkTransportExpectation expectation = {
            call->request_id,
            call->operation_id,
            call->attempt_id,
            call->command,
        };
        message = facman_gtk_transport_validate(
            call->stdout_data->data,
            call->stdout_data->len,
            call->stderr_data->data,
            call->stderr_data->len,
            &expectation);
    }
    if (message == NULL)
        message = g_strndup((const gchar *)call->stdout_data->data, call->stdout_data->len);
    call->completion(message, call->user_data);
    g_free(message);
    g_free(call->failure);
    g_free(call->request_id);
    g_free(call->operation_id);
    g_free(call->attempt_id);
    g_free(call->command);
    g_byte_array_unref(call->stdout_data);
    g_byte_array_unref(call->stderr_data);
    g_object_unref(call->process);
    g_object_unref(call->cancellable);
    g_free(call);
}

static void facman_gtk_rpc_start_read(
    FacManGtkRpcCall *call,
    GInputStream *stream,
    GByteArray *destination,
    gsize limit)
{
    FacManGtkRpcRead *read = g_new0(FacManGtkRpcRead, 1);
    read->call = call;
    read->stream = stream;
    read->destination = destination;
    read->limit = limit;
    facman_gtk_rpc_read_next(read);
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
    gchar *bundled = NULL;
    if (configured == NULL || *configured == '\0') {
        gchar *running = g_file_read_link("/proc/self/exe", NULL);
        if (running != NULL) {
            gchar *directory = g_path_get_dirname(running);
            bundled = g_build_filename(directory, "facman", NULL);
            g_free(directory);
            g_free(running);
            if (!g_file_test(bundled, G_FILE_TEST_IS_EXECUTABLE)) {
                g_free(bundled);
                bundled = NULL;
            }
        }
        configured = bundled != NULL ? bundled : "facman";
    }
    const gchar *argv[] = { configured, "rpc", "--stdio", NULL };
    GError *error = NULL;
    GSubprocessLauncher *launcher = g_subprocess_launcher_new(
        G_SUBPROCESS_FLAGS_STDIN_PIPE | G_SUBPROCESS_FLAGS_STDOUT_PIPE |
        G_SUBPROCESS_FLAGS_STDERR_PIPE);
    g_subprocess_launcher_set_child_setup(launcher, facman_gtk_rpc_child_setup, NULL, NULL);
    GSubprocess *process = g_subprocess_launcher_spawnv(launcher, argv, &error);
    g_object_unref(launcher);
    g_free(bundled);
    if (process == NULL) {
        gchar *message = g_strdup_printf(
            "frontend_backend_unavailable: %s",
            error != NULL ? error->message : "could not start facman");
        completion(message, user_data);
        g_free(message);
        g_clear_error(&error);
        return;
    }

    FacManGtkRpcCall *call = g_new0(FacManGtkRpcCall, 1);
    call->process = process;
    call->cancellable = g_cancellable_new();
    call->stdout_data = g_byte_array_sized_new(FACMAN_RPC_READ_CHUNK);
    call->stderr_data = g_byte_array_sized_new(FACMAN_RPC_READ_CHUNK);
    call->command = g_strdup(command != NULL ? command : "product.inspect");
    call->completion = completion;
    call->user_data = user_data;
    gchar *request = facman_preview_generated_rpc_request_with_identity(
        workspace,
        call->command,
        payload_json,
        dry_run,
        &call->request_id,
        &call->operation_id,
        &call->attempt_id);

    call->pending = 3;
    call->timeout_id = g_timeout_add_seconds(
        facman_gtk_rpc_timeout_seconds(), facman_gtk_rpc_timeout, call);
    facman_gtk_rpc_start_read(
        call, g_subprocess_get_stdout_pipe(process), call->stdout_data, FACMAN_RPC_STDOUT_LIMIT);
    facman_gtk_rpc_start_read(
        call, g_subprocess_get_stderr_pipe(process), call->stderr_data, FACMAN_RPC_STDERR_LIMIT);
    g_subprocess_wait_async(process, NULL, facman_gtk_rpc_wait_complete, call);

    GOutputStream *input = g_subprocess_get_stdin_pipe(process);
    gsize request_size = strlen(request);
    gsize written = 0;
    gboolean request_ok = request_size <= FACMAN_RPC_REQUEST_LIMIT &&
        g_output_stream_write_all(input, request, request_size, &written, NULL, &error) &&
        written == request_size && g_output_stream_close(input, NULL, &error);
    g_free(request);
    if (!request_ok) {
        facman_gtk_rpc_set_failure(
            call, "outcome_unknown: frontend_backend_request_error after process start; "
            "inspect Activity/recovery before retrying");
        facman_gtk_rpc_terminate_tree(call);
        g_clear_error(&error);
    }
}
