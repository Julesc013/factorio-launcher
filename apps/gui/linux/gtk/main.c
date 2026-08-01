// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include <atk/atk.h>
#include <gtk/gtk.h>

#include "command_client.h"
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
    GtkWidget *cli_path;
    GtkWidget *workspace;
    GtkTextBuffer *rpc_result;
    GtkAccelGroup *accelerators;
    FacManPreviewState state;
    gboolean relaunched;
    gboolean self_test;
    gboolean expect_timeout;
    gchar *retained_last_run;
    gchar *probe_report;
} FacManGtkShell;

static gboolean preview_self_test = FALSE;

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
    gchar *readiness = g_strdup_printf("Readiness: %s", record->readiness);
    const gchar *last_run = shell->retained_last_run != NULL ? shell->retained_last_run : record->last_run;
    gchar *last = g_strdup_printf("Last Run: %s", last_run);
    const gchar *operation_id = record->operation_id;
    if (shell->relaunched && shell->state == FACMAN_PREVIEW_RUNNING)
        operation_id = "operation.fixture-play-002";
    gchar *operation = g_strdup_printf("Operation: %s", *operation_id != '\0' ? operation_id : "none");
    gtk_label_set_text(GTK_LABEL(shell->deck_status), record->status_text);
    gtk_label_set_text(GTK_LABEL(shell->deck_readiness), readiness);
    gtk_label_set_text(GTK_LABEL(shell->deck_last_run), last);
    gtk_label_set_text(GTK_LABEL(shell->deck_operation), operation);
    gtk_label_set_text(GTK_LABEL(shell->activity_summary), record->activity_summary);
    gtk_button_set_label(GTK_BUTTON(shell->deck_primary), record->primary_label);
    set_accessibility(shell->deck_primary, record->primary_accessibility_label,
        "Fixture-only preview action; no live Factorio process is started.");
    const gchar *secondary = "Make readiness stale";
    if (shell->state == FACMAN_PREVIEW_STALE_READINESS) secondary = "Rescan readiness";
    if (shell->state == FACMAN_PREVIEW_INTERRUPTED) secondary = "Recover operation";
    gtk_button_set_label(GTK_BUTTON(shell->deck_secondary), secondary);
    set_accessibility(shell->deck_secondary, secondary,
        "Safe fixture transition; no live Factorio process is started.");
    g_free(readiness);
    g_free(last);
    g_free(operation);
}

static void primary_action(GtkButton *button, gpointer user_data)
{
    (void)button;
    FacManGtkShell *shell = user_data;
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
    shell->state = FACMAN_PREVIEW_READY;
    render_fixture(shell);
}

static void finish_fixture(GtkButton *button, gpointer user_data)
{
    (void)button;
    FacManGtkShell *shell = user_data;
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
    GtkWidget *instances = page_box("Instances", "C1 Vanilla — selected · 1 isolated vanilla instance");
    GtkWidget *instance_actions = gtk_button_box_new(GTK_ORIENTATION_HORIZONTAL);
    gtk_button_box_set_layout(GTK_BUTTON_BOX(instance_actions), GTK_BUTTONBOX_START);
    GtkWidget *create = gtk_button_new_with_mnemonic("_Create instance…");
    GtkWidget *select = gtk_button_new_with_mnemonic("_Select C1 Vanilla");
    set_accessibility(create, "Create instance", "Create/select fixture instance preview");
    set_accessibility(select, "Select C1 Vanilla", "Select fixture instance C1 Vanilla");
    g_signal_connect(create, "clicked", G_CALLBACK(select_instance), shell);
    g_signal_connect(select, "clicked", G_CALLBACK(select_instance), shell);
    gtk_container_add(GTK_CONTAINER(instance_actions), create);
    gtk_container_add(GTK_CONTAINER(instance_actions), select);
    gtk_box_pack_start(GTK_BOX(instances), instance_actions, FALSE, FALSE, 0);
    gtk_stack_add_titled(GTK_STACK(shell->stack), instances, "instances", "Instances");

    GtkWidget *installations = page_box("Installations",
        "Factorio 2.0.77 standalone — existing; this preview never repairs or updates it.");
    GtkWidget *scan = gtk_button_new_with_mnemonic("_Scan for installations");
    set_accessibility(scan, "Scan for installations", "Refresh deterministic installation/readiness fixture");
    g_signal_connect(scan, "clicked", G_CALLBACK(select_instance), shell);
    gtk_box_pack_start(GTK_BOX(installations), scan, FALSE, FALSE, 0);
    gtk_stack_add_titled(GTK_STACK(shell->stack), installations, "installations", "Installations");

    GtkWidget *activity = page_box("Activity", "Backend-owned operation and recovery state");
    shell->activity_summary = label("No active operations.", 0.0f);
    gtk_box_pack_start(GTK_BOX(activity), shell->activity_summary, FALSE, FALSE, 0);
    GtkWidget *activity_actions = gtk_button_box_new(GTK_ORIENTATION_HORIZONTAL);
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

    GtkWidget *settings = page_box("Settings / About",
        "FacMan 0.1 C1 · GTK 3/X11 x64 preview · no live Play or stable support claim");
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
    g_clear_object(&shell->accelerators);
    g_free(shell);
}

static gboolean has_accelerator(FacManGtkShell *shell, guint key)
{
    GtkAccelKey *entries = NULL;
    return gtk_accel_group_query(shell->accelerators, key, GDK_CONTROL_MASK, &entries) > 0;
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
    shell->deck = gtk_frame_new("Launch Deck — C1 Vanilla · fixture only");
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
