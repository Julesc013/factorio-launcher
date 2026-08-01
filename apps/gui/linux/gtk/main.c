// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include <atk/atk.h>
#include <gtk/gtk.h>

#include "command_client.h"
#include "generated_live_presentation.h"
#include "preview_model.h"

#if GLIB_CHECK_VERSION(2, 74, 0)
#define FACMAN_APPLICATION_FLAGS G_APPLICATION_DEFAULT_FLAGS
#else
#define FACMAN_APPLICATION_FLAGS G_APPLICATION_FLAGS_NONE
#endif

typedef struct {
    GtkApplication *application;
    GtkWidget *window;
    GtkWidget *stack;
    GtkWidget *deck;
    GtkWidget *deck_status;
    GtkWidget *deck_readiness;
    GtkWidget *deck_last_run;
    GtkWidget *deck_operation;
    GtkWidget *deck_primary;
    GtkWidget *deck_secondary;
    GtkWidget *activity_summary;
    GtkWidget *instance_summary;
    GtkWidget *installation_summary;
    GtkWidget *evidence_actions;
    GtkWidget *cli_path;
    GtkWidget *workspace;
    GtkTextBuffer *rpc_result;
    GtkAccelGroup *accelerators;
    FacManPreviewState state;
    gboolean relaunched;
    gboolean self_test;
    gboolean expect_timeout;
    gchar *probe_report;
    gboolean evidence_mode;
    gboolean live_execution_available;
    gboolean live_recovery_required;
    gint live_refresh_step;
    gchar *retained_last_run;
    gchar *live_instance_id;
    gchar *live_install_id;
    gchar *live_readiness_digest;
    gchar *live_readiness;
    gchar *live_status;
    gchar *live_activity;
    gchar *live_operation_id;
    gchar *live_recovery_id;
    gchar *live_recovery_transaction_id;
    gchar *live_refusal_code;
    gchar *live_refusal_detail;
    gchar *pending_last_run;
    gchar *pending_last_run_session_id;
} FacManGtkShell;

static gboolean preview_self_test = FALSE;

static void refresh_live(FacManGtkShell *shell);
static void render_fixture(FacManGtkShell *shell);

static void replace_text(gchar **target, const gchar *value)
{
    g_free(*target);
    *target = g_strdup(value != NULL ? value : "");
}

static gchar *live_cache_path(void)
{
    return g_build_filename(g_get_user_data_dir(), "facman", "presentation-cache.v0.ini", NULL);
}

static void load_view_only_last_run(FacManGtkShell *shell)
{
    g_free(shell->retained_last_run);
    shell->retained_last_run = NULL;
    gchar *path = live_cache_path();
    GKeyFile *cache = g_key_file_new();
    if (g_key_file_load_from_file(cache, path, G_KEY_FILE_NONE, NULL)) {
        gchar *authority = g_key_file_get_string(cache, "last_run", "authority", NULL);
        gchar *workspace = g_key_file_get_string(cache, "last_run", "workspace", NULL);
        gchar *digest = g_key_file_get_string(cache, "last_run", "readiness_digest", NULL);
        if (g_strcmp0(authority, "non_authoritative_view_copy") == 0 &&
            g_strcmp0(workspace, gtk_entry_get_text(GTK_ENTRY(shell->workspace))) == 0 &&
            g_strcmp0(digest, shell->live_readiness_digest) == 0)
            shell->retained_last_run = g_key_file_get_string(cache, "last_run", "summary", NULL);
        g_free(digest); g_free(workspace); g_free(authority);
    }
    g_key_file_unref(cache);
    g_free(path);
}

static void save_view_only_last_run(FacManGtkShell *shell, const gchar *session_id)
{
    if (shell->retained_last_run == NULL) return;
    gchar *path = live_cache_path();
    gchar *directory = g_path_get_dirname(path);
    g_mkdir_with_parents(directory, 0700);
    GKeyFile *cache = g_key_file_new();
    g_key_file_set_string(cache, "last_run", "authority", "non_authoritative_view_copy");
    g_key_file_set_string(cache, "last_run", "source", "completed_factorio_launch_session_v1");
    g_key_file_set_string(cache, "last_run", "workspace", gtk_entry_get_text(GTK_ENTRY(shell->workspace)));
    g_key_file_set_string(cache, "last_run", "readiness_digest", shell->live_readiness_digest != NULL ? shell->live_readiness_digest : "");
    g_key_file_set_string(cache, "last_run", "session_id", session_id != NULL ? session_id : "");
    g_key_file_set_string(cache, "last_run", "summary", shell->retained_last_run);
    gsize length = 0;
    gchar *contents = g_key_file_to_data(cache, &length, NULL);
    g_file_set_contents(path, contents, (gssize)length, NULL);
    g_free(contents);
    g_key_file_unref(cache);
    g_free(directory);
    g_free(path);
}

static void set_accessibility(GtkWidget *widget, const gchar *name, const gchar *description)
{
    AtkObject *accessible = gtk_widget_get_accessible(widget);
    atk_object_set_name(accessible, name);
    atk_object_set_description(accessible, description);
}

static GtkWidget *label(const gchar *text, gfloat xalign)
{
    GtkWidget *widget = gtk_label_new(text);
    gtk_label_set_xalign(GTK_LABEL(widget), xalign);
    gtk_label_set_line_wrap(GTK_LABEL(widget), TRUE);
    set_accessibility(widget, text, text);
    return widget;
}

static void show_page(FacManGtkShell *shell, const gchar *page)
{
    gtk_stack_set_visible_child_name(GTK_STACK(shell->stack), page);
}

static void menu_page(GtkMenuItem *item, gpointer user_data)
{
    FacManGtkShell *shell = user_data;
    show_page(shell, g_object_get_data(G_OBJECT(item), "facman-page"));
}

static void render_fixture(FacManGtkShell *shell)
{
    const FacManPreviewRecord *record = facman_preview_record(shell->state);
    const gchar *readiness_text = shell->evidence_mode ? record->readiness : shell->live_readiness;
    const gchar *status_text = shell->evidence_mode ? record->status_text : shell->live_status;
    const gchar *activity_text = shell->evidence_mode ? record->activity_summary : shell->live_activity;
    const gchar *primary_label = shell->evidence_mode ? record->primary_label :
        (shell->state == FACMAN_PREVIEW_EXITED ? "Relaunch" :
         shell->state == FACMAN_PREVIEW_INTERRUPTED ? "Inspect recovery" : "Play");
    const gchar *operation_id = shell->evidence_mode ? record->operation_id : shell->live_operation_id;
    gchar *readiness = g_strdup_printf("Readiness: %s", readiness_text != NULL ? readiness_text : "Unavailable");
    const gchar *last_run = shell->retained_last_run != NULL ? shell->retained_last_run :
        (shell->evidence_mode ? record->last_run : "No backend-completed run recorded");
    gchar *last = g_strdup_printf("Last Run: %s", last_run);
    if (operation_id == NULL) operation_id = "";
    if (shell->evidence_mode && shell->relaunched && shell->state == FACMAN_PREVIEW_RUNNING)
        operation_id = "operation.fixture-play-002";
    gchar *operation = g_strdup_printf("Operation: %s", *operation_id != '\0' ? operation_id : "none");
    gtk_label_set_text(GTK_LABEL(shell->deck_status), status_text != NULL ? status_text : "Backend state unavailable");
    gtk_label_set_text(GTK_LABEL(shell->deck_readiness), readiness);
    gtk_label_set_text(GTK_LABEL(shell->deck_last_run), last);
    gtk_label_set_text(GTK_LABEL(shell->deck_operation), operation);
    gtk_label_set_text(GTK_LABEL(shell->activity_summary), activity_text != NULL ? activity_text : "No active operation.");
    gtk_button_set_label(GTK_BUTTON(shell->deck_primary), primary_label);
    gtk_widget_set_sensitive(shell->deck_primary,
        shell->evidence_mode || shell->live_execution_available || shell->live_recovery_required);
    set_accessibility(shell->deck_primary,
        shell->evidence_mode ? record->primary_accessibility_label : primary_label,
        shell->evidence_mode ? "Explicit evidence/development fixture action; no live process is started."
                             : "Exact registered backend route; backend readiness and admission remain authoritative.");
    const gchar *secondary = shell->evidence_mode ? "Make readiness stale" : "Refresh backend state";
    if (shell->state == FACMAN_PREVIEW_STALE_READINESS) secondary = "Rescan readiness";
    if (shell->state == FACMAN_PREVIEW_INTERRUPTED) secondary = "Recover operation";
    gtk_button_set_label(GTK_BUTTON(shell->deck_secondary), secondary);
    set_accessibility(shell->deck_secondary, secondary,
        shell->evidence_mode ? "Safe fixture transition; no live process is started."
                             : "Refresh backend-derived presentation or explicitly recover; never auto-launch.");
    if (shell->evidence_actions != NULL)
        gtk_widget_set_visible(shell->evidence_actions, shell->evidence_mode);
    g_free(readiness);
    g_free(last);
    g_free(operation);
}

static void live_refuse(FacManGtkShell *shell, const gchar *code, const gchar *detail)
{
    shell->state = FACMAN_PREVIEW_STALE_READINESS;
    shell->live_execution_available = FALSE;
    replace_text(&shell->live_refusal_code, code != NULL && *code != '\0' ? code : "play_route_unavailable");
    replace_text(&shell->live_refusal_detail, detail != NULL && *detail != '\0'
        ? detail : "The backend did not enable the exact registered Play route.");
    gchar *status = g_strdup_printf("Play unavailable — %s",
        code != NULL && *code != '\0' ? code : "play_route_unavailable");
    replace_text(&shell->live_status, status);
    g_free(status);
    replace_text(&shell->live_activity, "No process was started by the frontend.");
}

static gboolean rpc_ok(const gchar *result)
{
    gchar *outcome = facman_record_text(result, "outcome");
    gboolean ok = g_strcmp0(outcome, "ok") == 0;
    g_free(outcome);
    return ok;
}

static void live_refresh_completed(const gchar *result, gpointer user_data)
{
    FacManGtkShell *shell = user_data;
    if (!rpc_ok(result)) {
        gchar *code = facman_error_text(result, "code");
        gchar *message = facman_error_text(result, "message");
        live_refuse(shell, code, message);
        g_free(code);
        g_free(message);
        render_fixture(shell);
        return;
    }
    const gchar *cli = gtk_entry_get_text(GTK_ENTRY(shell->cli_path));
    const gchar *workspace = gtk_entry_get_text(GTK_ENTRY(shell->workspace));
    switch (shell->live_refresh_step++) {
        case 0:
            facman_gtk_rpc_invoke(cli, workspace, "installs.scan", live_refresh_completed, shell);
            return;
        case 1: {
            gchar *install_id = facman_payload_text(result, "install_id");
            if (*install_id == '\0') { g_free(install_id); install_id = facman_payload_text(result, "id"); }
            gchar *version = facman_payload_text(result, "version");
            replace_text(&shell->live_install_id, install_id);
            gchar *summary = *install_id == '\0' ? g_strdup("No supported installation discovered") :
                g_strdup_printf("Selected backend installation %s · version %s", install_id, *version != '\0' ? version : "unknown");
            gtk_label_set_text(GTK_LABEL(shell->installation_summary), summary);
            g_free(summary); g_free(version); g_free(install_id);
            facman_gtk_rpc_invoke(cli, workspace, "instance.list", live_refresh_completed, shell);
            return;
        }
        case 2: {
            gchar *instance_id = facman_payload_text(result, "instance_id");
            if (*instance_id == '\0') { g_free(instance_id); instance_id = facman_payload_text(result, "id"); }
            replace_text(&shell->live_instance_id, instance_id);
            if (*instance_id == '\0') {
                gtk_label_set_text(GTK_LABEL(shell->instance_summary), "No backend instance; create one to continue");
                live_refuse(shell, "no_instance_selected", "Select or create an instance before Play.");
                g_free(instance_id);
                render_fixture(shell);
                return;
            }
            gchar *payload = facman_instance_payload(instance_id);
            g_free(instance_id);
            facman_gtk_rpc_invoke_payload(cli, workspace, "instances.inspect", payload, TRUE, live_refresh_completed, shell);
            g_free(payload);
            return;
        }
        case 3: {
            gchar *name = facman_payload_text(result, "display_name");
            gchar *summary = g_strdup_printf("%s — selected backend instance %s",
                *name != '\0' ? name : shell->live_instance_id, shell->live_instance_id);
            gtk_label_set_text(GTK_LABEL(shell->instance_summary), summary);
            g_free(summary); g_free(name);
            gchar *payload = facman_instance_payload(shell->live_instance_id);
            facman_gtk_rpc_invoke_payload(cli, workspace, "instances.readiness", payload, TRUE, live_refresh_completed, shell);
            g_free(payload);
            return;
        }
        case 4: {
            gchar *digest = facman_payload_text(result, "readiness_digest");
            gchar *overall = facman_payload_text(result, "overall_state");
            gchar *freshness = facman_payload_text(result, "freshness");
            gchar *authority = facman_payload_text(result, "play_authority_state");
            gchar *summary = g_strdup_printf("%s · freshness %s · Play authority %s",
                *overall != '\0' ? overall : "unavailable",
                *freshness != '\0' ? freshness : "unknown",
                *authority != '\0' ? authority : "unavailable");
            replace_text(&shell->live_readiness_digest, digest);
            replace_text(&shell->live_readiness, summary);
            load_view_only_last_run(shell);
            if (shell->pending_last_run != NULL) {
                shell->retained_last_run = g_strdup(shell->pending_last_run);
                save_view_only_last_run(shell, shell->pending_last_run_session_id);
                g_clear_pointer(&shell->pending_last_run, g_free);
                g_clear_pointer(&shell->pending_last_run_session_id, g_free);
            }
            shell->live_execution_available = facman_payload_boolean(result, "execution_available");
            shell->state = shell->live_execution_available
                ? (shell->retained_last_run != NULL ? FACMAN_PREVIEW_EXITED : FACMAN_PREVIEW_READY)
                : FACMAN_PREVIEW_STALE_READINESS;
            if (shell->live_execution_available) {
                replace_text(&shell->live_status, "Backend enabled exact registered Play route");
                replace_text(&shell->live_refusal_code, "");
                replace_text(&shell->live_refusal_detail, "");
            } else {
                gchar *code = facman_payload_text(result, "code");
                gchar *detail = facman_payload_text(result, "detail");
                live_refuse(shell, code, detail);
                g_free(code); g_free(detail);
            }
            g_free(summary); g_free(authority); g_free(freshness); g_free(overall); g_free(digest);
            facman_gtk_rpc_invoke(cli, workspace, "workspace.recovery.inspect", live_refresh_completed, shell);
            return;
        }
        case 5: {
            shell->live_recovery_required = facman_payload_recovery_required(result);
            if (shell->live_recovery_required) {
                gchar *transaction_id = facman_payload_recovery_text(result, "transaction_id");
                if (*transaction_id == '\0') { g_free(transaction_id); transaction_id = facman_payload_recovery_text(result, "id"); }
                gchar *operation_id = facman_payload_recovery_text(result, "command_id");
                g_clear_pointer(&shell->retained_last_run, g_free);
                replace_text(&shell->live_recovery_transaction_id, transaction_id);
                replace_text(&shell->live_recovery_id, transaction_id);
                replace_text(&shell->live_operation_id, operation_id);
                replace_text(&shell->live_status, "Backend recovery required after interruption");
                replace_text(&shell->live_activity, "A backend journal transaction requires explicit recovery.");
                shell->state = FACMAN_PREVIEW_INTERRUPTED;
                g_free(operation_id); g_free(transaction_id);
            } else {
                replace_text(&shell->live_recovery_transaction_id, "");
                replace_text(&shell->live_recovery_id, "");
                replace_text(&shell->live_operation_id, "");
                replace_text(&shell->live_activity, shell->retained_last_run != NULL
                    ? "Last backend-completed run retained as a non-authoritative view copy."
                    : "No active backend recovery operation.");
            }
            render_fixture(shell);
            return;
        }
        default:
            return;
    }
}

static void refresh_live(FacManGtkShell *shell)
{
    shell->live_refresh_step = 0;
    replace_text(&shell->live_status, "Inspecting workspace, installations, instances, readiness, Activity, Last Run, and recovery…");
    render_fixture(shell);
    facman_gtk_rpc_invoke(
        gtk_entry_get_text(GTK_ENTRY(shell->cli_path)),
        gtk_entry_get_text(GTK_ENTRY(shell->workspace)),
        "workspace.status", live_refresh_completed, shell);
}

static void live_play_completed(const gchar *result, gpointer user_data)
{
    FacManGtkShell *shell = user_data;
    if (!rpc_ok(result)) {
        gchar *code = facman_error_text(result, "code");
        gchar *message = facman_error_text(result, "message");
        live_refuse(shell, code, message);
        g_free(message); g_free(code);
    } else {
        gchar *schema = facman_payload_text(result, "schema");
        gboolean completed_session = g_strcmp0(schema, "factorio.launch_session.v1") == 0 &&
            facman_payload_boolean(result, "complete");
        g_free(schema);
        if (completed_session) {
            gchar *session_id = facman_payload_text(result, "session_id");
            replace_text(&shell->pending_last_run_session_id, session_id);
            g_free(shell->pending_last_run);
            shell->pending_last_run = g_strdup_printf(
                "Exited · backend-completed session %s · non-authoritative view copy",
                *session_id != '\0' ? session_id : "unknown");
            g_free(session_id);
        }
    }
    refresh_live(shell);
}

static void live_play_readiness_completed(const gchar *result, gpointer user_data)
{
    FacManGtkShell *shell = user_data;
    gchar *current = facman_payload_text(result, "readiness_digest");
    gboolean enabled = rpc_ok(result) && facman_payload_boolean(result, "execution_available");
    if (g_strcmp0(current, shell->live_readiness_digest) != 0) {
        replace_text(&shell->live_readiness_digest, current);
        live_refuse(shell, "stale_readiness", "Workspace evidence changed; readiness was refreshed and no process started.");
        render_fixture(shell);
    } else if (!enabled) {
        gchar *code = facman_payload_text(result, "code");
        gchar *detail = facman_payload_text(result, "detail");
        live_refuse(shell, code, detail);
        render_fixture(shell);
        g_free(detail); g_free(code);
    } else {
        gchar *payload = facman_instance_payload(shell->live_instance_id);
        facman_gtk_rpc_invoke_payload(
            gtk_entry_get_text(GTK_ENTRY(shell->cli_path)),
            gtk_entry_get_text(GTK_ENTRY(shell->workspace)),
            "run.execute", payload, FALSE, live_play_completed, shell);
        g_free(payload);
    }
    g_free(current);
}

static void live_recovery_completed(const gchar *result, gpointer user_data)
{
    FacManGtkShell *shell = user_data;
    if (!rpc_ok(result)) {
        gchar *code = facman_error_text(result, "code");
        gchar *message = facman_error_text(result, "message");
        live_refuse(shell, code, message);
        g_free(message); g_free(code);
        render_fixture(shell);
        return;
    }
    refresh_live(shell);
}

static void primary_action(GtkButton *button, gpointer user_data)
{
    (void)button;
    FacManGtkShell *shell = user_data;
    if (!shell->evidence_mode) {
        if (shell->live_recovery_required) { show_page(shell, "activity"); return; }
        if (!shell->live_execution_available) {
            GtkWidget *dialog = gtk_message_dialog_new(GTK_WINDOW(shell->window),
                GTK_DIALOG_MODAL | GTK_DIALOG_DESTROY_WITH_PARENT, GTK_MESSAGE_WARNING, GTK_BUTTONS_OK,
                "%s", shell->live_refusal_code != NULL ? shell->live_refusal_code : "Play unavailable");
            gtk_message_dialog_format_secondary_text(GTK_MESSAGE_DIALOG(dialog), "%s",
                shell->live_refusal_detail != NULL ? shell->live_refusal_detail : "Backend did not enable Play.");
            gtk_dialog_run(GTK_DIALOG(dialog));
            gtk_widget_destroy(dialog);
            return;
        }
        gchar *payload = facman_instance_payload(shell->live_instance_id);
        facman_gtk_rpc_invoke_payload(
            gtk_entry_get_text(GTK_ENTRY(shell->cli_path)),
            gtk_entry_get_text(GTK_ENTRY(shell->workspace)),
            "instances.readiness", payload, TRUE, live_play_readiness_completed, shell);
        g_free(payload);
        return;
    }
    switch (shell->state) {
        case FACMAN_PREVIEW_STALE_READINESS: {
            GtkWidget *dialog = gtk_message_dialog_new(GTK_WINDOW(shell->window),
                GTK_DIALOG_MODAL | GTK_DIALOG_DESTROY_WITH_PARENT, GTK_MESSAGE_WARNING, GTK_BUTTONS_OK,
                "Readiness changed");
            gtk_message_dialog_format_secondary_text(GTK_MESSAGE_DIALOG(dialog),
                "stale_readiness — Play was refused before effects because observed revision 7 is stale; "
                "current revision is 8. Rescan readiness before retrying.");
            gtk_dialog_run(GTK_DIALOG(dialog));
            gtk_widget_destroy(dialog);
            return;
        }
        case FACMAN_PREVIEW_RUNNING:
        case FACMAN_PREVIEW_INTERRUPTED:
            show_page(shell, "activity");
            return;
        case FACMAN_PREVIEW_EXITED:
            shell->relaunched = TRUE;
            shell->state = FACMAN_PREVIEW_RUNNING;
            break;
        case FACMAN_PREVIEW_READY:
        default:
            shell->relaunched = FALSE;
            shell->state = FACMAN_PREVIEW_RUNNING;
            break;
    }
    render_fixture(shell);
}

static void secondary_action(GtkButton *button, gpointer user_data)
{
    (void)button;
    FacManGtkShell *shell = user_data;
    if (!shell->evidence_mode) {
        if (shell->live_recovery_required && shell->live_recovery_transaction_id != NULL &&
            *shell->live_recovery_transaction_id != '\0') {
            GtkWidget *dialog = gtk_message_dialog_new(GTK_WINDOW(shell->window),
                GTK_DIALOG_MODAL | GTK_DIALOG_DESTROY_WITH_PARENT, GTK_MESSAGE_WARNING, GTK_BUTTONS_OK_CANCEL,
                "Recover backend transaction %s?", shell->live_recovery_transaction_id);
            gtk_message_dialog_format_secondary_text(GTK_MESSAGE_DIALOG(dialog),
                "Recovery is explicit and will not auto-launch Factorio.");
            gint answer = gtk_dialog_run(GTK_DIALOG(dialog));
            gtk_widget_destroy(dialog);
            if (answer != GTK_RESPONSE_OK) return;
            gchar *payload = facman_recovery_payload(shell->live_recovery_transaction_id);
            facman_gtk_rpc_invoke_payload(
                gtk_entry_get_text(GTK_ENTRY(shell->cli_path)),
                gtk_entry_get_text(GTK_ENTRY(shell->workspace)),
                "workspace.recovery.apply", payload, FALSE, live_recovery_completed, shell);
            g_free(payload);
        } else {
            refresh_live(shell);
        }
        return;
    }
    if (shell->state == FACMAN_PREVIEW_INTERRUPTED || shell->state == FACMAN_PREVIEW_STALE_READINESS)
        shell->state = FACMAN_PREVIEW_READY;
    else
        shell->state = FACMAN_PREVIEW_STALE_READINESS;
    render_fixture(shell);
}

static void select_instance(GtkButton *button, gpointer user_data)
{
    (void)button;
    FacManGtkShell *shell = user_data;
    if (!shell->evidence_mode) { refresh_live(shell); return; }
    shell->state = FACMAN_PREVIEW_READY;
    render_fixture(shell);
}

static void create_instance(GtkButton *button, gpointer user_data)
{
    (void)button;
    FacManGtkShell *shell = user_data;
    if (shell->evidence_mode) { select_instance(NULL, shell); return; }
    if (shell->live_install_id == NULL || *shell->live_install_id == '\0') {
        live_refuse(shell, "no_installation_selected", "Scan and register a supported installation before creating an instance.");
        render_fixture(shell);
        return;
    }
    GtkWidget *dialog = gtk_dialog_new_with_buttons("Create backend instance", GTK_WINDOW(shell->window),
        GTK_DIALOG_MODAL | GTK_DIALOG_DESTROY_WITH_PARENT,
        "_Cancel", GTK_RESPONSE_CANCEL, "_Create", GTK_RESPONSE_OK, NULL);
    GtkWidget *content = gtk_dialog_get_content_area(GTK_DIALOG(dialog));
    GtkWidget *id = gtk_entry_new();
    GtkWidget *name = gtk_entry_new();
    gtk_entry_set_text(GTK_ENTRY(id), "c1-vanilla");
    gtk_entry_set_text(GTK_ENTRY(name), "C1 Vanilla");
    gtk_entry_set_placeholder_text(GTK_ENTRY(id), "portable instance id");
    gtk_entry_set_placeholder_text(GTK_ENTRY(name), "display name");
    gtk_box_pack_start(GTK_BOX(content), label("Instance ID", 0.0f), FALSE, FALSE, 2);
    gtk_box_pack_start(GTK_BOX(content), id, FALSE, FALSE, 2);
    gtk_box_pack_start(GTK_BOX(content), label("Display name", 0.0f), FALSE, FALSE, 2);
    gtk_box_pack_start(GTK_BOX(content), name, FALSE, FALSE, 2);
    gtk_widget_show_all(content);
    if (gtk_dialog_run(GTK_DIALOG(dialog)) == GTK_RESPONSE_OK) {
        gchar *payload = facman_create_instance_payload(
            gtk_entry_get_text(GTK_ENTRY(id)),
            gtk_entry_get_text(GTK_ENTRY(name)),
            shell->live_install_id);
        facman_gtk_rpc_invoke_payload(
            gtk_entry_get_text(GTK_ENTRY(shell->cli_path)),
            gtk_entry_get_text(GTK_ENTRY(shell->workspace)),
            "instance.create", payload, FALSE, live_recovery_completed, shell);
        g_free(payload);
    }
    gtk_widget_destroy(dialog);
}

static void finish_fixture(GtkButton *button, gpointer user_data)
{
    (void)button;
    FacManGtkShell *shell = user_data;
    if (!shell->evidence_mode) return;
    if (shell->state != FACMAN_PREVIEW_RUNNING) return;
    g_free(shell->retained_last_run);
    shell->retained_last_run = g_strdup(shell->relaunched
        ? "Exited normally · code 0 · operation.fixture-play-002"
        : "Exited normally · code 0 · operation.fixture-play-001");
    shell->state = FACMAN_PREVIEW_EXITED;
    render_fixture(shell);
}

static void interrupt_fixture(GtkButton *button, gpointer user_data)
{
    (void)button;
    FacManGtkShell *shell = user_data;
    if (!shell->evidence_mode) return;
    g_free(shell->retained_last_run);
    shell->retained_last_run = g_strdup("Interrupted · outcome unknown · operation.fixture-play-001");
    shell->state = FACMAN_PREVIEW_INTERRUPTED;
    render_fixture(shell);
    show_page(shell, "activity");
}

static void recover_fixture(GtkButton *button, gpointer user_data)
{
    (void)button;
    FacManGtkShell *shell = user_data;
    if (!shell->evidence_mode) { secondary_action(NULL, shell); return; }
    if (shell->state != FACMAN_PREVIEW_INTERRUPTED) return;
    shell->state = FACMAN_PREVIEW_READY;
    render_fixture(shell);
}

static void apply_system_native(FacManGtkShell *shell)
{
    GtkStyleContext *context = gtk_widget_get_style_context(shell->deck);
    gtk_style_context_remove_class(context, "facman-oem-launch-deck");
}

static void appearance_system_native(GtkMenuItem *item, gpointer user_data)
{
    (void)item;
    apply_system_native(user_data);
}

static void appearance_oem(GtkMenuItem *item, gpointer user_data)
{
    (void)item;
    FacManGtkShell *shell = user_data;
    GtkCssProvider *provider = gtk_css_provider_new();
    gtk_css_provider_load_from_data(provider,
        ".facman-oem-launch-deck { background-color: #21334d; color: #ffffff; }", -1, NULL);
    GtkStyleContext *context = gtk_widget_get_style_context(shell->deck);
    gtk_style_context_add_provider(context, GTK_STYLE_PROVIDER(provider), GTK_STYLE_PROVIDER_PRIORITY_APPLICATION);
    gtk_style_context_add_class(context, "facman-oem-launch-deck");
    g_object_unref(provider);
}

static void rpc_completed(const gchar *result, gpointer user_data)
{
    GtkTextBuffer *buffer = GTK_TEXT_BUFFER(user_data);
    gtk_text_buffer_set_text(buffer, result, -1);
    g_object_unref(buffer);
}

static void run_advanced_rpc(GtkButton *button, gpointer user_data)
{
    (void)button;
    FacManGtkShell *shell = user_data;
    gtk_text_buffer_set_text(shell->rpc_result, "Running product.inspect through bounded process RPC…", -1);
    facman_gtk_rpc_invoke(
        gtk_entry_get_text(GTK_ENTRY(shell->cli_path)),
        gtk_entry_get_text(GTK_ENTRY(shell->workspace)),
        "product.inspect", rpc_completed, g_object_ref(shell->rpc_result));
}

static GtkWidget *page_box(const gchar *title, const gchar *summary)
{
    GtkWidget *box = gtk_box_new(GTK_ORIENTATION_VERTICAL, 12);
    gtk_container_set_border_width(GTK_CONTAINER(box), 18);
    GtkWidget *heading = label(title, 0.0f);
    PangoAttrList *attributes = pango_attr_list_new();
    pango_attr_list_insert(attributes, pango_attr_weight_new(PANGO_WEIGHT_BOLD));
    pango_attr_list_insert(attributes, pango_attr_scale_new(1.35));
    gtk_label_set_attributes(GTK_LABEL(heading), attributes);
    pango_attr_list_unref(attributes);
    gtk_box_pack_start(GTK_BOX(box), heading, FALSE, FALSE, 0);
    gtk_box_pack_start(GTK_BOX(box), label(summary, 0.0f), FALSE, FALSE, 0);
    return box;
}

static void add_pages(FacManGtkShell *shell)
{
    GtkWidget *instances = page_box("Instances", shell->evidence_mode
        ? "EXPLICIT EVIDENCE / DEVELOPMENT MODE — deterministic fixture"
        : "LIVE BACKEND MODE — registered instance records");
    shell->instance_summary = label("Inspecting backend instances…", 0.0f);
    gtk_box_pack_start(GTK_BOX(instances), shell->instance_summary, FALSE, FALSE, 0);
    GtkWidget *instance_actions = gtk_button_box_new(GTK_ORIENTATION_HORIZONTAL);
    gtk_button_box_set_layout(GTK_BUTTON_BOX(instance_actions), GTK_BUTTONBOX_START);
    GtkWidget *create = gtk_button_new_with_mnemonic("_Create instance…");
    GtkWidget *select = gtk_button_new_with_mnemonic("_Select C1 Vanilla");
    set_accessibility(create, "Create instance", "Create/select fixture instance preview");
    set_accessibility(select, "Select C1 Vanilla", "Select fixture instance C1 Vanilla");
    g_signal_connect(create, "clicked", G_CALLBACK(create_instance), shell);
    g_signal_connect(select, "clicked", G_CALLBACK(select_instance), shell);
    gtk_container_add(GTK_CONTAINER(instance_actions), create);
    gtk_container_add(GTK_CONTAINER(instance_actions), select);
    gtk_box_pack_start(GTK_BOX(instances), instance_actions, FALSE, FALSE, 0);
    gtk_stack_add_titled(GTK_STACK(shell->stack), instances, "instances", "Instances");

    GtkWidget *installations = page_box("Installations",
        "Read-only backend discovery; this preview never repairs or updates an installation.");
    shell->installation_summary = label("Inspecting backend installations…", 0.0f);
    gtk_box_pack_start(GTK_BOX(installations), shell->installation_summary, FALSE, FALSE, 0);
    GtkWidget *scan = gtk_button_new_with_mnemonic("_Scan for installations");
    set_accessibility(scan, "Scan for installations", "Refresh deterministic installation/readiness fixture");
    g_signal_connect(scan, "clicked", G_CALLBACK(select_instance), shell);
    gtk_box_pack_start(GTK_BOX(installations), scan, FALSE, FALSE, 0);
    gtk_stack_add_titled(GTK_STACK(shell->stack), installations, "installations", "Installations");

    GtkWidget *activity = page_box("Activity", "Backend-owned operation and recovery state");
    shell->activity_summary = label("No active operations.", 0.0f);
    gtk_box_pack_start(GTK_BOX(activity), shell->activity_summary, FALSE, FALSE, 0);
    GtkWidget *activity_actions = gtk_button_box_new(GTK_ORIENTATION_HORIZONTAL);
    shell->evidence_actions = activity_actions;
    gtk_button_box_set_layout(GTK_BUTTON_BOX(activity_actions), GTK_BUTTONBOX_START);
    GtkWidget *finish = gtk_button_new_with_mnemonic("_Finish fixture run");
    GtkWidget *interrupt = gtk_button_new_with_mnemonic("Simulate _interruption");
    GtkWidget *recover = gtk_button_new_with_mnemonic("_Recover operation");
    set_accessibility(finish, "Finish fixture run", "Publish deterministic exited and Last Run state");
    set_accessibility(interrupt, "Simulate interruption", "Publish outcome unknown with exact recovery identity");
    set_accessibility(recover, "Recover operation", "Clear exact interrupted fixture record without auto-launch");
    g_signal_connect(finish, "clicked", G_CALLBACK(finish_fixture), shell);
    g_signal_connect(interrupt, "clicked", G_CALLBACK(interrupt_fixture), shell);
    g_signal_connect(recover, "clicked", G_CALLBACK(recover_fixture), shell);
    gtk_container_add(GTK_CONTAINER(activity_actions), finish);
    gtk_container_add(GTK_CONTAINER(activity_actions), interrupt);
    gtk_container_add(GTK_CONTAINER(activity_actions), recover);
    gtk_box_pack_start(GTK_BOX(activity), activity_actions, FALSE, FALSE, 0);
    gtk_stack_add_titled(GTK_STACK(shell->stack), activity, "activity", "Activity");

    GtkWidget *settings = page_box("Settings / About", shell->evidence_mode
        ? "EXPLICIT EVIDENCE / DEVELOPMENT MODE · unchanged fixtures · no live Play authority"
        : "LIVE BACKEND MODE · bounded process RPC · backend-gated Play · GTK preview support lane");
    gtk_box_pack_start(GTK_BOX(settings), label(
        "Appearance: System Native by default; FacMan OEM+ affects only Launch Deck semantics. "
        "Use Appearance → System Native to recover immediately.", 0.0f), FALSE, FALSE, 0);
    gtk_stack_add_titled(GTK_STACK(shell->stack), settings, "settings", "Settings / About");

    GtkWidget *advanced = page_box("Advanced", "Generated command access through bounded process RPC");
    shell->cli_path = gtk_entry_new();
    shell->workspace = gtk_entry_new();
    gtk_entry_set_placeholder_text(GTK_ENTRY(shell->cli_path), "facman CLI path (optional)");
    gtk_entry_set_placeholder_text(GTK_ENTRY(shell->workspace), "workspace path (optional)");
    set_accessibility(shell->cli_path, "FacMan CLI path", "Executable used only as rpc --stdio");
    set_accessibility(shell->workspace, "Workspace path", "Workspace sent in the bounded RPC request");
    gtk_box_pack_start(GTK_BOX(advanced), shell->cli_path, FALSE, FALSE, 0);
    gtk_box_pack_start(GTK_BOX(advanced), shell->workspace, FALSE, FALSE, 0);
    GtkWidget *run = gtk_button_new_with_mnemonic("_Inspect product through RPC");
    g_signal_connect(run, "clicked", G_CALLBACK(run_advanced_rpc), shell);
    gtk_box_pack_start(GTK_BOX(advanced), run, FALSE, FALSE, 0);
    GtkWidget *result = gtk_text_view_new();
    gtk_text_view_set_editable(GTK_TEXT_VIEW(result), FALSE);
    gtk_text_view_set_monospace(GTK_TEXT_VIEW(result), TRUE);
    set_accessibility(result, "Advanced command result", "Structured result or exact refusal from bounded process RPC");
    shell->rpc_result = gtk_text_view_get_buffer(GTK_TEXT_VIEW(result));
    GtkWidget *scroll = gtk_scrolled_window_new(NULL, NULL);
    gtk_container_add(GTK_CONTAINER(scroll), result);
    gtk_box_pack_start(GTK_BOX(advanced), scroll, TRUE, TRUE, 0);
    gtk_stack_add_titled(GTK_STACK(shell->stack), advanced, "advanced", "Advanced");
}

static GtkWidget *menu_item(FacManGtkShell *shell, GtkWidget *menu, const gchar *label_text,
    const gchar *page, guint key)
{
    GtkWidget *item = gtk_menu_item_new_with_mnemonic(label_text);
    gtk_menu_shell_append(GTK_MENU_SHELL(menu), item);
    g_object_set_data(G_OBJECT(item), "facman-page", (gpointer)page);
    g_signal_connect(item, "activate", G_CALLBACK(menu_page), shell);
    gtk_widget_add_accelerator(item, "activate",
        shell->accelerators, key, GDK_CONTROL_MASK, GTK_ACCEL_VISIBLE);
    return item;
}

static GtkWidget *build_menu(FacManGtkShell *shell)
{
    shell->accelerators = gtk_accel_group_new();
    gtk_window_add_accel_group(GTK_WINDOW(shell->window), shell->accelerators);
    GtkWidget *bar = gtk_menu_bar_new();
    GtkWidget *file_root = gtk_menu_item_new_with_mnemonic("_File");
    GtkWidget *file_menu = gtk_menu_new();
    GtkWidget *quit = gtk_menu_item_new_with_mnemonic("_Quit");
    gtk_widget_add_accelerator(quit, "activate", shell->accelerators, GDK_KEY_q, GDK_CONTROL_MASK, GTK_ACCEL_VISIBLE);
    g_signal_connect_swapped(quit, "activate", G_CALLBACK(g_application_quit), shell->application);
    gtk_menu_shell_append(GTK_MENU_SHELL(file_menu), quit);
    gtk_menu_item_set_submenu(GTK_MENU_ITEM(file_root), file_menu);
    gtk_menu_shell_append(GTK_MENU_SHELL(bar), file_root);

    GtkWidget *view_root = gtk_menu_item_new_with_mnemonic("_View");
    GtkWidget *view_menu = gtk_menu_new();
    menu_item(shell, view_menu, "_Instances", "instances", GDK_KEY_1);
    menu_item(shell, view_menu, "_Installations", "installations", GDK_KEY_2);
    menu_item(shell, view_menu, "_Activity", "activity", GDK_KEY_3);
    menu_item(shell, view_menu, "_Settings / About", "settings", GDK_KEY_4);
    menu_item(shell, view_menu, "Ad_vanced", "advanced", GDK_KEY_5);
    gtk_menu_item_set_submenu(GTK_MENU_ITEM(view_root), view_menu);
    gtk_menu_shell_append(GTK_MENU_SHELL(bar), view_root);

    GtkWidget *appearance_root = gtk_menu_item_new_with_mnemonic("_Appearance");
    GtkWidget *appearance_menu = gtk_menu_new();
    GtkWidget *system_native = gtk_menu_item_new_with_mnemonic("_System Native");
    GtkWidget *oem = gtk_menu_item_new_with_mnemonic("FacMan _OEM+ Launch Deck");
    g_signal_connect(system_native, "activate", G_CALLBACK(appearance_system_native), shell);
    g_signal_connect(oem, "activate", G_CALLBACK(appearance_oem), shell);
    gtk_widget_add_accelerator(system_native, "activate", shell->accelerators, GDK_KEY_0,
        GDK_CONTROL_MASK, GTK_ACCEL_VISIBLE);
    gtk_menu_shell_append(GTK_MENU_SHELL(appearance_menu), system_native);
    gtk_menu_shell_append(GTK_MENU_SHELL(appearance_menu), oem);
    gtk_menu_item_set_submenu(GTK_MENU_ITEM(appearance_root), appearance_menu);
    gtk_menu_shell_append(GTK_MENU_SHELL(bar), appearance_root);
    return bar;
}

static void destroy_shell(gpointer data)
{
    FacManGtkShell *shell = data;
    g_free(shell->retained_last_run);
    g_free(shell->probe_report);
    g_free(shell->live_instance_id);
    g_free(shell->live_install_id);
    g_free(shell->live_readiness_digest);
    g_free(shell->live_readiness);
    g_free(shell->live_status);
    g_free(shell->live_activity);
    g_free(shell->live_operation_id);
    g_free(shell->live_recovery_id);
    g_free(shell->live_recovery_transaction_id);
    g_free(shell->live_refusal_code);
    g_free(shell->live_refusal_detail);
    g_free(shell->pending_last_run);
    g_free(shell->pending_last_run_session_id);
    g_clear_object(&shell->accelerators);
    g_free(shell);
}

static gboolean has_accelerator(FacManGtkShell *shell, guint key)
{
    guint entry_count = 0;
    GtkAccelGroupEntry *entries = gtk_accel_group_query(
        shell->accelerators, key, GDK_CONTROL_MASK, &entry_count);
    return entries != NULL && entry_count > 0;
}

static gboolean at_spi_bus_available(void)
{
    GError *error = NULL;
    GDBusProxy *proxy = g_dbus_proxy_new_for_bus_sync(
        G_BUS_TYPE_SESSION,
        G_DBUS_PROXY_FLAGS_DO_NOT_LOAD_PROPERTIES,
        NULL,
        "org.a11y.Bus",
        "/org/a11y/bus",
        "org.a11y.Bus",
        NULL,
        &error);
    if (proxy == NULL) {
        g_clear_error(&error);
        return FALSE;
    }
    GVariant *address = g_dbus_proxy_call_sync(
        proxy, "GetAddress", NULL, G_DBUS_CALL_FLAGS_NONE, 5000, NULL, &error);
    gboolean available = address != NULL;
    if (address != NULL) g_variant_unref(address);
    g_clear_error(&error);
    g_object_unref(proxy);
    return available;
}

static void runtime_probe_completed(const gchar *result, gpointer user_data)
{
    FacManGtkShell *shell = user_data;
    gboolean rpc_pass = shell->expect_timeout
        ? g_strstr_len(result, -1, "outcome_unknown") != NULL
        : g_strstr_len(result, -1, "operation.preview-rpc-001") != NULL;
    g_print("%s\n", shell->probe_report);
    g_print("bounded_rpc=%s\n", rpc_pass ? "pass" : "fail");
    g_print("rpc_timeout=%s\n", shell->expect_timeout ? (rpc_pass ? "pass" : "fail") : "not_requested");
    g_print("process_transport=rpc --stdio\n");
    fflush(stdout);
    g_application_quit(G_APPLICATION(shell->application));
}

static void run_runtime_probe(FacManGtkShell *shell)
{
    GString *facts = g_string_new(
        "schema=facman.classic_preview_runtime_probe.v1\n"
        "platform=gtk\n"
        "authority=fixture_only\n"
        "live_play=false\n");
    GList *pages = gtk_container_get_children(GTK_CONTAINER(shell->stack));
    g_string_append_printf(facts, "pages=%s\n", g_list_length(pages) == 5 ? "pass" : "fail");
    g_list_free(pages);
    gboolean menu_pass = has_accelerator(shell, GDK_KEY_0)
        && has_accelerator(shell, GDK_KEY_1)
        && has_accelerator(shell, GDK_KEY_2)
        && has_accelerator(shell, GDK_KEY_3)
        && has_accelerator(shell, GDK_KEY_4)
        && has_accelerator(shell, GDK_KEY_5);
    g_string_append_printf(facts, "menu_keyboard=%s\n", menu_pass ? "pass" : "fail");

    gtk_window_resize(GTK_WINDOW(shell->window), 920, 640);
    while (gtk_events_pending()) gtk_main_iteration();
    gint width = 0;
    gint height = 0;
    gtk_window_get_size(GTK_WINDOW(shell->window), &width, &height);
    g_string_append_printf(facts, "resize=%s\n", width >= 800 && height >= 500 ? "pass" : "fail");
    gtk_widget_grab_focus(shell->deck_primary);
    gboolean focus_pass = gtk_window_get_focus(GTK_WINDOW(shell->window)) == shell->deck_primary;
    show_page(shell, "activity");
    show_page(shell, "instances");
    gtk_widget_grab_focus(shell->deck_primary);
    focus_pass = focus_pass && gtk_window_get_focus(GTK_WINDOW(shell->window)) == shell->deck_primary;
    g_string_append_printf(facts, "focus_restoration=%s\n", focus_pass ? "pass" : "fail");

    appearance_oem(NULL, shell);
    gboolean appearance_pass = gtk_style_context_has_class(
        gtk_widget_get_style_context(shell->deck), "facman-oem-launch-deck");
    appearance_system_native(NULL, shell);
    appearance_pass = appearance_pass && !gtk_style_context_has_class(
        gtk_widget_get_style_context(shell->deck), "facman-oem-launch-deck");
    g_string_append_printf(facts, "appearance_recovery=%s\n", appearance_pass ? "pass" : "fail");

    AtkObject *deck_accessible = gtk_widget_get_accessible(shell->deck);
    AtkObject *play_accessible = gtk_widget_get_accessible(shell->deck_primary);
    gboolean accessibility_pass = atk_object_get_name(deck_accessible) != NULL
        && atk_object_get_name(play_accessible) != NULL
        && atk_object_get_role(play_accessible) != ATK_ROLE_INVALID;
    g_string_append_printf(facts, "accessibility=%s\n", accessibility_pass ? "pass" : "fail");
    gchar *theme_name = NULL;
    g_object_get(gtk_settings_get_default(), "gtk-theme-name", &theme_name, NULL);
    gchar *lower_theme = theme_name != NULL ? g_ascii_strdown(theme_name, -1) : NULL;
    gboolean high_contrast = lower_theme != NULL && g_strrstr(lower_theme, "highcontrast") != NULL;
    const gchar *gtk_modules = g_getenv("GTK_MODULES");
    gboolean at_spi_bridge = gtk_modules != NULL
        && g_strrstr(gtk_modules, "atk-bridge") != NULL
        && g_strcmp0(g_getenv("NO_AT_BRIDGE"), "1") != 0
        && at_spi_bus_available();
    g_string_append_printf(facts, "high_contrast=%s\n", high_contrast ? "pass" : "fail");
    g_string_append_printf(facts, "at_spi_bridge=%s\n", at_spi_bridge ? "pass" : "fail");
    g_free(lower_theme);
    g_free(theme_name);

    shell->state = FACMAN_PREVIEW_READY;
    render_fixture(shell);
    primary_action(NULL, shell);
    gboolean fixture_pass = shell->state == FACMAN_PREVIEW_RUNNING;
    finish_fixture(NULL, shell);
    fixture_pass = fixture_pass && shell->state == FACMAN_PREVIEW_EXITED;
    primary_action(NULL, shell);
    fixture_pass = fixture_pass && shell->state == FACMAN_PREVIEW_RUNNING && shell->relaunched;
    interrupt_fixture(NULL, shell);
    fixture_pass = fixture_pass && shell->state == FACMAN_PREVIEW_INTERRUPTED;
    recover_fixture(NULL, shell);
    fixture_pass = fixture_pass && shell->state == FACMAN_PREVIEW_READY;
    shell->state = FACMAN_PREVIEW_STALE_READINESS;
    render_fixture(shell);
    const FacManPreviewRecord *stale = facman_preview_record(shell->state);
    fixture_pass = fixture_pass && g_strcmp0(stale->refusal_code, "stale_readiness") == 0;
    g_string_append_printf(facts, "fixture_journey=%s\n", fixture_pass ? "pass" : "fail");
    g_string_append(facts, "stale_refusal=stale_readiness");

    shell->probe_report = g_string_free(facts, FALSE);
    shell->expect_timeout = g_getenv("FACMAN_PREVIEW_EXPECT_TIMEOUT") != NULL;
    facman_gtk_rpc_invoke(
        gtk_entry_get_text(GTK_ENTRY(shell->cli_path)),
        gtk_entry_get_text(GTK_ENTRY(shell->workspace)),
        "product.inspect", runtime_probe_completed, shell);
}

static GtkWidget *build_launch_deck(FacManGtkShell *shell)
{
    shell->deck = gtk_frame_new(shell->evidence_mode
        ? "Launch Deck — EXPLICIT EVIDENCE / DEVELOPMENT MODE"
        : "Launch Deck — LIVE BACKEND MODE");
    set_accessibility(shell->deck, "Persistent Launch Deck for selected instance C1 Vanilla",
        "Selected instance readiness, primary action, operation, Last Run, and recovery state");
    GtkWidget *grid = gtk_grid_new();
    gtk_grid_set_row_spacing(GTK_GRID(grid), 6);
    gtk_grid_set_column_spacing(GTK_GRID(grid), 12);
    gtk_container_set_border_width(GTK_CONTAINER(grid), 12);
    shell->deck_status = label("Ready", 0.0f);
    shell->deck_readiness = label("Readiness", 0.0f);
    shell->deck_last_run = label("Last Run", 0.0f);
    shell->deck_operation = label("Operation", 0.0f);
    shell->deck_primary = gtk_button_new_with_label("Play");
    shell->deck_secondary = gtk_button_new_with_label("Make readiness stale");
    g_signal_connect(shell->deck_primary, "clicked", G_CALLBACK(primary_action), shell);
    g_signal_connect(shell->deck_secondary, "clicked", G_CALLBACK(secondary_action), shell);
    gtk_grid_attach(GTK_GRID(grid), shell->deck_status, 0, 0, 1, 1);
    gtk_grid_attach(GTK_GRID(grid), shell->deck_readiness, 0, 1, 1, 1);
    gtk_grid_attach(GTK_GRID(grid), shell->deck_last_run, 0, 2, 1, 1);
    gtk_grid_attach(GTK_GRID(grid), shell->deck_operation, 0, 3, 1, 1);
    gtk_grid_attach(GTK_GRID(grid), shell->deck_primary, 1, 0, 1, 2);
    gtk_grid_attach(GTK_GRID(grid), shell->deck_secondary, 1, 2, 1, 2);
    gtk_container_add(GTK_CONTAINER(shell->deck), grid);
    return shell->deck;
}

static void activate(GtkApplication *application, gpointer user_data)
{
    (void)user_data;
    FacManGtkShell *shell = g_new0(FacManGtkShell, 1);
    shell->application = application;
    shell->state = FACMAN_PREVIEW_READY;
    shell->self_test = preview_self_test;
    shell->evidence_mode = g_ascii_strcasecmp(g_getenv("FACMAN_PRESENTATION_MODE") != NULL
        ? g_getenv("FACMAN_PRESENTATION_MODE") : "", "evidence") == 0;
    replace_text(&shell->live_readiness, "Not inspected");
    replace_text(&shell->live_status, "Backend workspace has not been inspected");
    replace_text(&shell->live_activity, "No backend activity inspected");
    replace_text(&shell->live_operation_id, "");
    shell->window = gtk_application_window_new(application);
    gtk_window_set_title(GTK_WINDOW(shell->window), "FacMan GTK 3 C1 Preview");
    gtk_window_set_default_size(GTK_WINDOW(shell->window), 1040, 720);
    GtkWidget *root = gtk_box_new(GTK_ORIENTATION_VERTICAL, 8);
    gtk_container_add(GTK_CONTAINER(shell->window), root);
    gtk_box_pack_start(GTK_BOX(root), build_menu(shell), FALSE, FALSE, 0);
    shell->stack = gtk_stack_new();
    gtk_stack_set_transition_type(GTK_STACK(shell->stack), GTK_STACK_TRANSITION_TYPE_NONE);
    GtkWidget *switcher = gtk_stack_switcher_new();
    gtk_stack_switcher_set_stack(GTK_STACK_SWITCHER(switcher), GTK_STACK(shell->stack));
    set_accessibility(switcher, "Primary navigation", "Instances, Installations, Activity, Settings/About, and Advanced");
    gtk_box_pack_start(GTK_BOX(root), switcher, FALSE, FALSE, 0);
    add_pages(shell);
    gtk_box_pack_start(GTK_BOX(root), shell->stack, TRUE, TRUE, 0);
    gtk_box_pack_start(GTK_BOX(root), build_launch_deck(shell), FALSE, FALSE, 8);
    gtk_stack_set_visible_child_name(GTK_STACK(shell->stack), "instances");
    render_fixture(shell);
    g_object_set_data_full(G_OBJECT(shell->window), "facman-shell", shell, destroy_shell);
    gtk_widget_show_all(shell->window);
    if (!shell->evidence_mode) refresh_live(shell);
    if (shell->self_test) run_runtime_probe(shell);
}

int main(int argc, char **argv)
{
    for (int index = 1; index < argc; ++index) {
        if (g_strcmp0(argv[index], "--facman-preview-self-test") == 0) {
            preview_self_test = TRUE;
            for (int shift = index; shift + 1 < argc; ++shift) argv[shift] = argv[shift + 1];
            --argc;
            --index;
        }
    }
    GtkApplication *application = gtk_application_new(
        "io.github.julesc013.facman.preview", FACMAN_APPLICATION_FLAGS);
    g_signal_connect(application, "activate", G_CALLBACK(activate), NULL);
    int status = g_application_run(G_APPLICATION(application), argc, argv);
    g_object_unref(application);
    return status;
}
