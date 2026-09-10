// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "shell_view.h"
#include "generated_product_metadata.h"

static void dispatch_action(GtkWidget *widget, gpointer user_data)
{
    FacManGtkView *view = user_data;
    if (view->on_action != NULL)
        view->on_action(g_object_get_data(G_OBJECT(widget), "facman-action"), view->action_context);
}

static void connect_action(GtkWidget *widget, FacManGtkView *view, const gchar *action)
{
    g_object_set_data(G_OBJECT(widget), "facman-action", (gpointer)action);
    g_signal_connect(widget, "clicked", G_CALLBACK(dispatch_action), view);
}

static void add_page(FacManGtkView *view, GtkWidget *content, const gchar *name, const gchar *title)
{
    GtkWidget *scroll = gtk_scrolled_window_new(NULL, NULL);
    gtk_scrolled_window_set_policy(GTK_SCROLLED_WINDOW(scroll), GTK_POLICY_AUTOMATIC, GTK_POLICY_AUTOMATIC);
    gtk_container_add(GTK_CONTAINER(scroll), content);
    gtk_stack_add_titled(GTK_STACK(view->stack), scroll, name, title);
}

void facman_gtk_accessibility(GtkWidget *widget, const gchar *name, const gchar *description)
{
    AtkObject *accessible = gtk_widget_get_accessible(widget);
    atk_object_set_name(accessible, name);
    atk_object_set_description(accessible, description);
}

GtkWidget *facman_gtk_label(const gchar *text, gfloat xalign)
{
    GtkWidget *widget = gtk_label_new(text);
    gtk_label_set_xalign(GTK_LABEL(widget), xalign);
    gtk_label_set_line_wrap(GTK_LABEL(widget), TRUE);
    facman_gtk_accessibility(widget, text, text);
    return widget;
}

void facman_gtk_view_page(FacManGtkView *shell, const gchar *page)
{
    gtk_stack_set_visible_child_name(GTK_STACK(shell->stack), page);
}

static void menu_page(GtkMenuItem *item, gpointer user_data)
{
    FacManGtkView *shell = user_data;
    facman_gtk_view_page(shell, g_object_get_data(G_OBJECT(item), "facman-page"));
}

void facman_gtk_system_native(FacManGtkView *shell)
{
    GtkStyleContext *context = gtk_widget_get_style_context(shell->deck);
    gtk_style_context_remove_class(context, "facman-oem-launch-deck");
}

void facman_gtk_apply_system_native(GtkMenuItem *item, gpointer user_data)
{
    (void)item;
    facman_gtk_system_native(user_data);
}

void facman_gtk_apply_oem(GtkMenuItem *item, gpointer user_data)
{
    (void)item;
    FacManGtkView *shell = user_data;
    GtkCssProvider *provider = gtk_css_provider_new();
    gtk_css_provider_load_from_data(provider,
        ".facman-oem-launch-deck { background-color: #21334d; color: #ffffff; }", -1, NULL);
    GtkStyleContext *context = gtk_widget_get_style_context(shell->deck);
    gtk_style_context_add_provider(context, GTK_STYLE_PROVIDER(provider), GTK_STYLE_PROVIDER_PRIORITY_APPLICATION);
    gtk_style_context_add_class(context, "facman-oem-launch-deck");
    g_object_unref(provider);
}

static GtkWidget *page_box(const gchar *title, const gchar *summary)
{
    GtkWidget *box = gtk_box_new(GTK_ORIENTATION_VERTICAL, 12);
    gtk_container_set_border_width(GTK_CONTAINER(box), 18);
    GtkWidget *heading = facman_gtk_label(title, 0.0f);
    PangoAttrList *attributes = pango_attr_list_new();
    pango_attr_list_insert(attributes, pango_attr_weight_new(PANGO_WEIGHT_BOLD));
    pango_attr_list_insert(attributes, pango_attr_scale_new(1.35));
    gtk_label_set_attributes(GTK_LABEL(heading), attributes);
    pango_attr_list_unref(attributes);
    gtk_box_pack_start(GTK_BOX(box), heading, FALSE, FALSE, 0);
    gtk_box_pack_start(GTK_BOX(box), facman_gtk_label(summary, 0.0f), FALSE, FALSE, 0);
    return box;
}

static void add_pages(FacManGtkView *shell)
{
    GtkWidget *instances = page_box("Instances", shell->gallery_mode ? "CONTROL GALLERY — actions are recorded only" : shell->evidence_mode
        ? "EXPLICIT EVIDENCE / DEVELOPMENT MODE — deterministic fixture"
        : "LIVE BACKEND MODE — registered instance records");
    shell->instance_summary = facman_gtk_label("Inspecting backend instances…", 0.0f);
    gtk_box_pack_start(GTK_BOX(instances), shell->instance_summary, FALSE, FALSE, 0);
    GtkWidget *instance_actions = gtk_button_box_new(GTK_ORIENTATION_HORIZONTAL);
    gtk_button_box_set_layout(GTK_BUTTON_BOX(instance_actions), GTK_BUTTONBOX_START);
    GtkWidget *create = gtk_button_new_with_mnemonic("_Create instance…");
    GtkWidget *select = gtk_button_new_with_mnemonic(shell->evidence_mode ? "_Select C1 Vanilla" : "_Select instance");
    facman_gtk_accessibility(create, "Create instance", "Create/select fixture instance preview");
    facman_gtk_accessibility(select, shell->evidence_mode ? "Select C1 Vanilla" : "Select instance", "Select the backend instance context");
    connect_action(create, shell, "instance.create");
    connect_action(select, shell, "instance.select");
    gtk_container_add(GTK_CONTAINER(instance_actions), create);
    gtk_container_add(GTK_CONTAINER(instance_actions), select);
    gtk_box_pack_start(GTK_BOX(instances), instance_actions, FALSE, FALSE, 0);
    add_page(shell, instances, "instances", "Instances");

    GtkWidget *installations = page_box("Installations",
        "Read-only backend discovery; this preview never repairs or updates an installation.");
    shell->installation_summary = facman_gtk_label("Inspecting backend installations…", 0.0f);
    gtk_box_pack_start(GTK_BOX(installations), shell->installation_summary, FALSE, FALSE, 0);
    GtkWidget *scan = gtk_button_new_with_mnemonic("_Scan for installations");
    facman_gtk_accessibility(scan, "Scan for installations", "Refresh deterministic installation/readiness fixture");
    connect_action(scan, shell, "instance.select");
    gtk_box_pack_start(GTK_BOX(installations), scan, FALSE, FALSE, 0);
    add_page(shell, installations, "installations", "Installations");

    GtkWidget *activity = page_box("Activity", "Backend-owned operation and recovery state");
    shell->activity_summary = facman_gtk_label("No active operations.", 0.0f);
    gtk_box_pack_start(GTK_BOX(activity), shell->activity_summary, FALSE, FALSE, 0);
    GtkWidget *activity_actions = gtk_button_box_new(GTK_ORIENTATION_HORIZONTAL);
    shell->evidence_actions = activity_actions;
    gtk_button_box_set_layout(GTK_BUTTON_BOX(activity_actions), GTK_BUTTONBOX_START);
    GtkWidget *finish = gtk_button_new_with_mnemonic("_Finish fixture run");
    GtkWidget *interrupt = gtk_button_new_with_mnemonic("Simulate _interruption");
    GtkWidget *recover = gtk_button_new_with_mnemonic("_Recover operation");
    facman_gtk_accessibility(finish, "Finish fixture run", "Publish deterministic exited and Last Run state");
    facman_gtk_accessibility(interrupt, "Simulate interruption", "Publish outcome unknown with exact recovery identity");
    facman_gtk_accessibility(recover, "Recover operation", "Clear exact interrupted fixture record without auto-launch");
    connect_action(finish, shell, "fixture.finish");
    connect_action(interrupt, shell, "fixture.interrupt");
    connect_action(recover, shell, "recovery.apply");
    gtk_container_add(GTK_CONTAINER(activity_actions), finish);
    gtk_container_add(GTK_CONTAINER(activity_actions), interrupt);
    gtk_container_add(GTK_CONTAINER(activity_actions), recover);
    gtk_box_pack_start(GTK_BOX(activity), activity_actions, FALSE, FALSE, 0);
    add_page(shell, activity, "activity", "Activity");

    GtkWidget *settings = page_box("Settings / About", shell->evidence_mode
        ? FACMAN_GUI_SETTINGS_EVIDENCE : FACMAN_GUI_SETTINGS_LIVE);
    gtk_box_pack_start(GTK_BOX(settings), facman_gtk_label(
        "Appearance: System Native by default; FacMan OEM+ affects only Launch Deck semantics. "
        "Use Appearance → System Native to recover immediately.", 0.0f), FALSE, FALSE, 0);
    add_page(shell, settings, "settings", "Settings / About");

    GtkWidget *advanced = page_box("Advanced", "Generated command access through bounded process RPC");
    shell->cli_path = gtk_entry_new();
    shell->workspace = gtk_entry_new();
    gtk_entry_set_placeholder_text(GTK_ENTRY(shell->cli_path), "facman CLI path (optional)");
    gtk_entry_set_placeholder_text(GTK_ENTRY(shell->workspace), "workspace path (optional)");
    facman_gtk_accessibility(shell->cli_path, "FacMan CLI path", "Executable used only as rpc --stdio");
    facman_gtk_accessibility(shell->workspace, "Workspace path", "Workspace sent in the bounded RPC request");
    gtk_box_pack_start(GTK_BOX(advanced), shell->cli_path, FALSE, FALSE, 0);
    gtk_box_pack_start(GTK_BOX(advanced), shell->workspace, FALSE, FALSE, 0);
    GtkWidget *run = gtk_button_new_with_mnemonic("_Inspect product through RPC");
    connect_action(run, shell, "product.inspect");
    gtk_box_pack_start(GTK_BOX(advanced), run, FALSE, FALSE, 0);
    GtkWidget *result = gtk_text_view_new();
    gtk_text_view_set_editable(GTK_TEXT_VIEW(result), FALSE);
    gtk_text_view_set_monospace(GTK_TEXT_VIEW(result), TRUE);
    facman_gtk_accessibility(result, "Advanced command result", "Structured result or exact refusal from bounded process RPC");
    shell->rpc_result = gtk_text_view_get_buffer(GTK_TEXT_VIEW(result));
    GtkWidget *scroll = gtk_scrolled_window_new(NULL, NULL);
    gtk_container_add(GTK_CONTAINER(scroll), result);
    gtk_box_pack_start(GTK_BOX(advanced), scroll, TRUE, TRUE, 0);
    add_page(shell, advanced, "advanced", "Advanced");
}

static GtkWidget *menu_item(FacManGtkView *shell, GtkWidget *menu, const gchar *label_text,
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

static GtkWidget *build_menu(FacManGtkView *shell)
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
    g_signal_connect(system_native, "activate", G_CALLBACK(facman_gtk_apply_system_native), shell);
    g_signal_connect(oem, "activate", G_CALLBACK(facman_gtk_apply_oem), shell);
    gtk_widget_add_accelerator(system_native, "activate", shell->accelerators, GDK_KEY_0,
        GDK_CONTROL_MASK, GTK_ACCEL_VISIBLE);
    gtk_menu_shell_append(GTK_MENU_SHELL(appearance_menu), system_native);
    gtk_menu_shell_append(GTK_MENU_SHELL(appearance_menu), oem);
    gtk_menu_item_set_submenu(GTK_MENU_ITEM(appearance_root), appearance_menu);
    gtk_menu_shell_append(GTK_MENU_SHELL(bar), appearance_root);
    return bar;
}

static GtkWidget *build_launch_deck(FacManGtkView *shell)
{
    shell->deck = gtk_frame_new(shell->gallery_mode ? "Launch Deck — CONTROL GALLERY" : shell->evidence_mode
        ? "Launch Deck — EXPLICIT EVIDENCE / DEVELOPMENT MODE"
        : "Launch Deck — LIVE BACKEND MODE");
    facman_gtk_accessibility(shell->deck, "Persistent Launch Deck for selected instance No instance selected",
        "Selected instance readiness, primary action, operation, Last Run, and recovery state");
    GtkWidget *grid = gtk_grid_new();
    gtk_grid_set_row_spacing(GTK_GRID(grid), 6);
    gtk_grid_set_column_spacing(GTK_GRID(grid), 12);
    gtk_container_set_border_width(GTK_CONTAINER(grid), 12);
    shell->deck_status = facman_gtk_label("Unavailable", 0.0f);
    shell->deck_instance = facman_gtk_label("No instance selected", 0.0f);
    shell->deck_readiness = facman_gtk_label("Readiness", 0.0f);
    shell->deck_last_run = facman_gtk_label("Last Run", 0.0f);
    shell->deck_operation = facman_gtk_label("Operation", 0.0f);
    shell->deck_primary = gtk_button_new_with_label("Play");
    shell->deck_secondary = gtk_button_new_with_label("Make readiness stale");
    connect_action(shell->deck_primary, shell, "launch.primary");
    connect_action(shell->deck_secondary, shell, "launch.secondary");
    GtkWidget *labels[] = {shell->deck_instance, shell->deck_status, shell->deck_readiness,
        shell->deck_last_run, shell->deck_operation};
    for (guint index = 0; index < G_N_ELEMENTS(labels); ++index) {
        gtk_label_set_line_wrap(GTK_LABEL(labels[index]), FALSE);
        gtk_label_set_ellipsize(GTK_LABEL(labels[index]), PANGO_ELLIPSIZE_END);
        gtk_widget_set_hexpand(labels[index], TRUE);
        gtk_widget_set_size_request(labels[index], 0, -1);
        gtk_grid_attach(GTK_GRID(grid), labels[index], 0, index, 1, 1);
    }
    gtk_grid_attach(GTK_GRID(grid), shell->deck_primary, 1, 0, 1, 2);
    gtk_grid_attach(GTK_GRID(grid), shell->deck_secondary, 1, 2, 1, 2);
    gtk_container_add(GTK_CONTAINER(shell->deck), grid);
    return shell->deck;
}

FacManGtkView *facman_gtk_view_new(GtkApplication *application, gboolean evidence_mode,
    gboolean gallery_mode, FacManGtkActionHandler on_action, gpointer action_context)
{
    FacManGtkView *shell = g_new0(FacManGtkView, 1);
    shell->application = application;
    shell->evidence_mode = evidence_mode;
    shell->gallery_mode = gallery_mode;
    shell->on_action = on_action;
    shell->action_context = action_context;
    shell->window = gtk_application_window_new(application);
    gtk_window_set_title(GTK_WINDOW(shell->window), gallery_mode ? "FacMan GTK control gallery" : FACMAN_GUI_WINDOW_TITLE);
    gtk_window_set_icon_name(GTK_WINDOW(shell->window), FACMAN_GUI_APPLICATION_ID);
    gtk_window_set_default_size(GTK_WINDOW(shell->window), 1040, 720);
    GtkWidget *root = gtk_box_new(GTK_ORIENTATION_VERTICAL, 8);
    gtk_container_add(GTK_CONTAINER(shell->window), root);
    gtk_box_pack_start(GTK_BOX(root), build_menu(shell), FALSE, FALSE, 0);
    shell->stack = gtk_stack_new();
    gtk_stack_set_transition_type(GTK_STACK(shell->stack), GTK_STACK_TRANSITION_TYPE_NONE);
    GtkWidget *switcher = gtk_stack_switcher_new();
    gtk_stack_switcher_set_stack(GTK_STACK_SWITCHER(switcher), GTK_STACK(shell->stack));
    facman_gtk_accessibility(switcher, "Primary navigation", "Instances, Installations, Activity, Settings/About, and Advanced");
    gtk_box_pack_start(GTK_BOX(root), switcher, FALSE, FALSE, 0);
    add_pages(shell);
    gtk_box_pack_start(GTK_BOX(root), shell->stack, TRUE, TRUE, 0);
    gtk_box_pack_start(GTK_BOX(root), build_launch_deck(shell), FALSE, FALSE, 8);
    facman_gtk_view_page(shell, "instances");
    FacManGtkPresentation empty = {0};
    facman_gtk_view_render(shell, &empty);
    return shell;
}

void facman_gtk_view_free(FacManGtkView *view)
{
    g_clear_object(&view->accelerators);
    g_free(view);
}

static void render_text(GtkWidget *widget, const gchar *prefix, const gchar *value, const gchar *fallback)
{
    gchar *text = g_strconcat(prefix, value != NULL && *value != '\0' ? value : fallback, NULL);
    gtk_label_set_text(GTK_LABEL(widget), text);
    facman_gtk_accessibility(widget, text, text);
    g_free(text);
}

void facman_gtk_view_render(FacManGtkView *view, const FacManGtkPresentation *presentation)
{
    const gchar *instance = presentation->instance_name != NULL && *presentation->instance_name != '\0'
        ? presentation->instance_name : "No instance selected";
    gchar *name = g_strconcat("Persistent Launch Deck for selected instance ", instance, NULL);
    facman_gtk_accessibility(view->deck, name, name);
    g_free(name);
    render_text(view->deck_status, "", presentation->status, "Backend state unavailable");
    render_text(view->deck_instance, "", instance, "No instance selected");
    if (presentation->instance_summary != NULL)
        render_text(view->instance_summary, "", presentation->instance_summary, "No backend instances.");
    if (presentation->installation_summary != NULL)
        render_text(view->installation_summary, "", presentation->installation_summary, "No backend installations.");
    render_text(view->deck_readiness, "Readiness: ", presentation->readiness, "Unavailable");
    render_text(view->deck_last_run, "Last Run: ", presentation->last_run, "Authoritative Last Run unavailable");
    render_text(view->deck_operation, "Operation: ", presentation->operation_id, "none");
    render_text(view->activity_summary, "", presentation->activity, "No active operation.");
    gtk_button_set_label(GTK_BUTTON(view->deck_primary), presentation->primary_label != NULL ? presentation->primary_label : "Play");
    gtk_widget_set_sensitive(view->deck_primary, presentation->primary_available);
    gtk_widget_set_no_show_all(view->deck_primary, !presentation->primary_visible);
    gtk_widget_set_visible(view->deck_primary, presentation->primary_visible);
    facman_gtk_accessibility(view->deck_primary,
        presentation->primary_accessibility != NULL ? presentation->primary_accessibility : "Play unavailable",
        view->gallery_mode ? "Recording only; no backend dispatch" : view->evidence_mode
            ? "Explicit evidence/development fixture action; no live process is started."
            : "Exact registered backend route; backend readiness and admission remain authoritative.");
    gtk_button_set_label(GTK_BUTTON(view->deck_secondary), presentation->secondary_label != NULL ? presentation->secondary_label : "Refresh backend state");
    facman_gtk_accessibility(view->deck_secondary,
        presentation->secondary_label != NULL ? presentation->secondary_label : "Refresh backend state",
        view->gallery_mode ? "Recording only; no backend dispatch" : "Refresh backend-derived presentation or explicitly recover; never auto-launch.");
    gtk_widget_set_no_show_all(view->evidence_actions, !view->evidence_mode);
    gtk_widget_set_visible(view->evidence_actions, view->evidence_mode);
}
