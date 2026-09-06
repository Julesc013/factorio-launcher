// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include <atk/atk.h>
#include <gtk/gtk.h>

#include "command_client.h"
#include "generated_live_presentation.h"
#include "generated_product_metadata.h"
#include "preview_model.h"
#include "shell_view.h"

#if GLIB_CHECK_VERSION(2, 74, 0)
#define FACMAN_APPLICATION_FLAGS G_APPLICATION_DEFAULT_FLAGS
#else
#define FACMAN_APPLICATION_FLAGS G_APPLICATION_FLAGS_NONE
#endif

typedef struct {
    FacManGtkView *view;
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
} FacManGtkShell;

static gboolean preview_self_test = FALSE;

static void refresh_live(FacManGtkShell *shell);
static void render_fixture(FacManGtkShell *shell);

static void replace_text(gchar **target, const gchar *value)
{
    g_free(*target);
    *target = g_strdup(value != NULL ? value : "");
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
    const gchar *last_run = shell->retained_last_run != NULL ? shell->retained_last_run :
        (shell->evidence_mode ? record->last_run : "Authoritative Last Run unavailable in this compatibility shell");
    if (shell->evidence_mode && shell->relaunched && shell->state == FACMAN_PREVIEW_RUNNING)
        operation_id = "operation.fixture-play-002";
    const gchar *secondary = shell->evidence_mode ? "Make readiness stale" : "Refresh backend state";
    if (shell->state == FACMAN_PREVIEW_STALE_READINESS) secondary = "Rescan readiness";
    if (shell->state == FACMAN_PREVIEW_INTERRUPTED) secondary = "Recover operation";
    FacManGtkPresentation presentation = {
        .instance_name = shell->evidence_mode ? "C1 Vanilla" : shell->live_instance_id,
        .status = status_text, .readiness = readiness_text, .activity = activity_text,
        .last_run = last_run, .operation_id = operation_id,
        .primary_label = primary_label,
        .primary_accessibility = shell->evidence_mode ? record->primary_accessibility_label : primary_label,
        .primary_available = shell->evidence_mode || shell->live_execution_available || shell->live_recovery_required,
        .primary_visible = TRUE, .secondary_label = secondary,
    };
    facman_gtk_view_render(shell->view, &presentation);
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
    const gchar *cli = gtk_entry_get_text(GTK_ENTRY(shell->view->cli_path));
    const gchar *workspace = gtk_entry_get_text(GTK_ENTRY(shell->view->workspace));
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
            gtk_label_set_text(GTK_LABEL(shell->view->installation_summary), summary);
            g_free(summary); g_free(version); g_free(install_id);
            facman_gtk_rpc_invoke(cli, workspace, "instance.list", live_refresh_completed, shell);
            return;
        }
        case 2: {
            gchar *instance_id = facman_payload_text(result, "instance_id");
            if (*instance_id == '\0') { g_free(instance_id); instance_id = facman_payload_text(result, "id"); }
            replace_text(&shell->live_instance_id, instance_id);
            if (*instance_id == '\0') {
                gtk_label_set_text(GTK_LABEL(shell->view->instance_summary), "No backend instance; create one to continue");
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
            gtk_label_set_text(GTK_LABEL(shell->view->instance_summary), summary);
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
            g_clear_pointer(&shell->retained_last_run, g_free);
            shell->live_execution_available = facman_payload_boolean(result, "execution_available");
            shell->state = shell->live_execution_available
                ? FACMAN_PREVIEW_READY
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
                replace_text(&shell->live_activity, "No active backend recovery operation.");
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
        gtk_entry_get_text(GTK_ENTRY(shell->view->cli_path)),
        gtk_entry_get_text(GTK_ENTRY(shell->view->workspace)),
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
            gtk_entry_get_text(GTK_ENTRY(shell->view->cli_path)),
            gtk_entry_get_text(GTK_ENTRY(shell->view->workspace)),
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
        if (shell->live_recovery_required) { facman_gtk_view_page(shell->view, "activity"); return; }
        if (!shell->live_execution_available) {
            GtkWidget *dialog = gtk_message_dialog_new(GTK_WINDOW(shell->view->window),
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
            gtk_entry_get_text(GTK_ENTRY(shell->view->cli_path)),
            gtk_entry_get_text(GTK_ENTRY(shell->view->workspace)),
            "instances.readiness", payload, TRUE, live_play_readiness_completed, shell);
        g_free(payload);
        return;
    }
    switch (shell->state) {
        case FACMAN_PREVIEW_STALE_READINESS: {
            GtkWidget *dialog = gtk_message_dialog_new(GTK_WINDOW(shell->view->window),
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
            facman_gtk_view_page(shell->view, "activity");
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
            GtkWidget *dialog = gtk_message_dialog_new(GTK_WINDOW(shell->view->window),
                GTK_DIALOG_MODAL | GTK_DIALOG_DESTROY_WITH_PARENT, GTK_MESSAGE_WARNING, GTK_BUTTONS_OK_CANCEL,
                "Recover backend transaction %s?", shell->live_recovery_transaction_id);
            gtk_message_dialog_format_secondary_text(GTK_MESSAGE_DIALOG(dialog),
                "Recovery is explicit and will not auto-launch Factorio.");
            gint answer = gtk_dialog_run(GTK_DIALOG(dialog));
            gtk_widget_destroy(dialog);
            if (answer != GTK_RESPONSE_OK) return;
            gchar *payload = facman_recovery_payload(shell->live_recovery_transaction_id);
            facman_gtk_rpc_invoke_payload(
                gtk_entry_get_text(GTK_ENTRY(shell->view->cli_path)),
                gtk_entry_get_text(GTK_ENTRY(shell->view->workspace)),
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
    GtkWidget *dialog = gtk_dialog_new_with_buttons("Create backend instance", GTK_WINDOW(shell->view->window),
        GTK_DIALOG_MODAL | GTK_DIALOG_DESTROY_WITH_PARENT,
        "_Cancel", GTK_RESPONSE_CANCEL, "_Create", GTK_RESPONSE_OK, NULL);
    GtkWidget *content = gtk_dialog_get_content_area(GTK_DIALOG(dialog));
    GtkWidget *id = gtk_entry_new();
    GtkWidget *name = gtk_entry_new();
    gtk_entry_set_text(GTK_ENTRY(id), "c1-vanilla");
    gtk_entry_set_text(GTK_ENTRY(name), "C1 Vanilla");
    gtk_entry_set_placeholder_text(GTK_ENTRY(id), "portable instance id");
    gtk_entry_set_placeholder_text(GTK_ENTRY(name), "display name");
    gtk_box_pack_start(GTK_BOX(content), facman_gtk_label("Instance ID", 0.0f), FALSE, FALSE, 2);
    gtk_box_pack_start(GTK_BOX(content), id, FALSE, FALSE, 2);
    gtk_box_pack_start(GTK_BOX(content), facman_gtk_label("Display name", 0.0f), FALSE, FALSE, 2);
    gtk_box_pack_start(GTK_BOX(content), name, FALSE, FALSE, 2);
    gtk_widget_show_all(content);
    if (gtk_dialog_run(GTK_DIALOG(dialog)) == GTK_RESPONSE_OK) {
        gchar *payload = facman_create_instance_payload(
            gtk_entry_get_text(GTK_ENTRY(id)),
            gtk_entry_get_text(GTK_ENTRY(name)),
            shell->live_install_id);
        facman_gtk_rpc_invoke_payload(
            gtk_entry_get_text(GTK_ENTRY(shell->view->cli_path)),
            gtk_entry_get_text(GTK_ENTRY(shell->view->workspace)),
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
    facman_gtk_view_page(shell->view, "activity");
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
    gtk_text_buffer_set_text(shell->view->rpc_result, "Running product.inspect through bounded process RPC…", -1);
    facman_gtk_rpc_invoke(
        gtk_entry_get_text(GTK_ENTRY(shell->view->cli_path)),
        gtk_entry_get_text(GTK_ENTRY(shell->view->workspace)),
        "product.inspect", rpc_completed, g_object_ref(shell->view->rpc_result));
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
    facman_gtk_view_free(shell->view);
    g_free(shell);
}

static gboolean has_accelerator(FacManGtkShell *shell, guint key)
{
    guint entry_count = 0;
    GtkAccelGroupEntry *entries = gtk_accel_group_query(
        shell->view->accelerators, key, GDK_CONTROL_MASK, &entry_count);
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
        : result != NULL && result[0] == '{';
    g_print("%s\n", shell->probe_report);
    g_print("bounded_rpc=%s\n", rpc_pass ? "pass" : "fail");
    g_print("rpc_timeout=%s\n", shell->expect_timeout ? (rpc_pass ? "pass" : "fail") : "not_requested");
    g_print("process_transport=rpc --stdio\n");
    fflush(stdout);
    g_application_quit(G_APPLICATION(shell->view->application));
}

static void run_runtime_probe(FacManGtkShell *shell)
{
    GString *facts = g_string_new(
        "schema=facman.classic_preview_runtime_probe.v1\n"
        "platform=gtk\n"
        "authority=fixture_only\n"
        "live_play=false\n");
    GList *pages = gtk_container_get_children(GTK_CONTAINER(shell->view->stack));
    g_string_append_printf(facts, "pages=%s\n", g_list_length(pages) == 5 ? "pass" : "fail");
    g_list_free(pages);
    gboolean menu_pass = has_accelerator(shell, GDK_KEY_0)
        && has_accelerator(shell, GDK_KEY_1)
        && has_accelerator(shell, GDK_KEY_2)
        && has_accelerator(shell, GDK_KEY_3)
        && has_accelerator(shell, GDK_KEY_4)
        && has_accelerator(shell, GDK_KEY_5);
    g_string_append_printf(facts, "menu_keyboard=%s\n", menu_pass ? "pass" : "fail");

    gtk_window_resize(GTK_WINDOW(shell->view->window), 920, 640);
    while (gtk_events_pending()) gtk_main_iteration();
    gint width = 0;
    gint height = 0;
    gtk_window_get_size(GTK_WINDOW(shell->view->window), &width, &height);
    g_string_append_printf(facts, "resize=%s\n", width >= 800 && height >= 500 ? "pass" : "fail");
    gtk_widget_grab_focus(shell->view->deck_primary);
    gboolean focus_pass = gtk_window_get_focus(GTK_WINDOW(shell->view->window)) == shell->view->deck_primary;
    facman_gtk_view_page(shell->view, "activity");
    facman_gtk_view_page(shell->view, "instances");
    gtk_widget_grab_focus(shell->view->deck_primary);
    focus_pass = focus_pass && gtk_window_get_focus(GTK_WINDOW(shell->view->window)) == shell->view->deck_primary;
    g_string_append_printf(facts, "focus_restoration=%s\n", focus_pass ? "pass" : "fail");

    facman_gtk_apply_oem(NULL, shell->view);
    gboolean appearance_pass = gtk_style_context_has_class(
        gtk_widget_get_style_context(shell->view->deck), "facman-oem-launch-deck");
    facman_gtk_apply_system_native(NULL, shell->view);
    appearance_pass = appearance_pass && !gtk_style_context_has_class(
        gtk_widget_get_style_context(shell->view->deck), "facman-oem-launch-deck");
    g_string_append_printf(facts, "appearance_recovery=%s\n", appearance_pass ? "pass" : "fail");

    AtkObject *deck_accessible = gtk_widget_get_accessible(shell->view->deck);
    AtkObject *play_accessible = gtk_widget_get_accessible(shell->view->deck_primary);
    gboolean accessibility_pass = atk_object_get_name(deck_accessible) != NULL
        && atk_object_get_name(play_accessible) != NULL
        && atk_object_get_role(play_accessible) != ATK_ROLE_INVALID;
    g_string_append_printf(facts, "accessibility=%s\n", accessibility_pass ? "pass" : "fail");
    gchar *theme_name = NULL;
    g_object_get(gtk_settings_get_default(), "gtk-theme-name", &theme_name, NULL);
    gchar *lower_theme = theme_name != NULL ? g_ascii_strdown(theme_name, -1) : NULL;
    const gchar *theme_override = g_getenv("GTK_THEME");
    gchar *lower_override = theme_override != NULL ? g_ascii_strdown(theme_override, -1) : NULL;
    gboolean high_contrast = (lower_theme != NULL && g_strrstr(lower_theme, "highcontrast") != NULL)
        || (lower_override != NULL && g_strrstr(lower_override, "highcontrast") != NULL);
    const gchar *gtk_modules = g_getenv("GTK_MODULES");
    gboolean at_spi_bridge = gtk_modules != NULL
        && g_strrstr(gtk_modules, "atk-bridge") != NULL
        && g_strcmp0(g_getenv("NO_AT_BRIDGE"), "1") != 0
        && at_spi_bus_available();
    g_string_append_printf(facts, "high_contrast=%s\n", high_contrast ? "pass" : "fail");
    g_string_append_printf(facts, "at_spi_bridge=%s\n", at_spi_bridge ? "pass" : "fail");
    g_free(lower_override);
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
        gtk_entry_get_text(GTK_ENTRY(shell->view->cli_path)),
        gtk_entry_get_text(GTK_ENTRY(shell->view->workspace)),
        "product.inspect", runtime_probe_completed, shell);
}

static void controller_action(const gchar *action, gpointer user_data)
{
    static const struct {
        const gchar *identifier;
        void (*handle)(GtkButton *, gpointer);
    } handlers[] = {
        {"instance.create", create_instance}, {"instance.select", select_instance},
        {"fixture.finish", finish_fixture}, {"fixture.interrupt", interrupt_fixture},
        {"recovery.apply", recover_fixture}, {"product.inspect", run_advanced_rpc},
        {"launch.primary", primary_action}, {"launch.secondary", secondary_action},
    };
    for (guint index = 0; index < G_N_ELEMENTS(handlers); ++index) {
        if (g_strcmp0(action, handlers[index].identifier) == 0) {
            handlers[index].handle(NULL, user_data);
            return;
        }
    }
}

static void activate(GtkApplication *application, gpointer user_data)
{
    (void)user_data;
    FacManGtkShell *shell = g_new0(FacManGtkShell, 1);
    shell->state = FACMAN_PREVIEW_READY;
    shell->self_test = preview_self_test;
    shell->evidence_mode = g_ascii_strcasecmp(g_getenv("FACMAN_PRESENTATION_MODE") != NULL
        ? g_getenv("FACMAN_PRESENTATION_MODE") : "", "evidence") == 0;
    replace_text(&shell->live_readiness, "Not inspected");
    replace_text(&shell->live_status, "Backend workspace has not been inspected");
    replace_text(&shell->live_activity, "No backend activity inspected");
    replace_text(&shell->live_operation_id, "");
    shell->view = facman_gtk_view_new(application, shell->evidence_mode, FALSE,
        controller_action, shell);
    render_fixture(shell);
    g_object_set_data_full(G_OBJECT(shell->view->window), "facman-shell", shell, destroy_shell);
    gtk_widget_show_all(shell->view->window);
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
        FACMAN_GUI_APPLICATION_ID, FACMAN_APPLICATION_FLAGS);
    g_signal_connect(application, "activate", G_CALLBACK(activate), NULL);
    int status = g_application_run(G_APPLICATION(application), argc, argv);
    g_object_unref(application);
    return status;
}
