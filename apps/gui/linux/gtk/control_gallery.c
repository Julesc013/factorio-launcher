// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "shell_view.h"
#include <glib/gstdio.h>
#include <math.h>
#include <pango/pangocairo.h>
#include <unistd.h>

static guint assertions;
static GPtrArray *actions;
static gchar *output_root;
static gboolean timed_out;
static guint font_label_observations;
static guint font_unknown_glyphs;

static void require(gboolean condition, const gchar *message)
{
    ++assertions;
    if (!condition) g_error("gallery assertion: %s", message);
}

static void record_action(const gchar *action, gpointer context)
{
    (void)context;
    g_ptr_array_add(actions, g_strdup(action));
}

static void drain(void)
{
    /* Layout and frame-clock work can become ready after the current event batch. */
    gint64 until = g_get_monotonic_time() + 50000;
    do {
        while (gtk_events_pending()) gtk_main_iteration();
        g_usleep(1000);
    } while (g_get_monotonic_time() < until);
}

static void check_controls(GtkWidget *widget, FacManGtkView *view)
{
    if (!gtk_widget_get_mapped(widget)) return;
    const gchar *action = g_object_get_data(G_OBJECT(widget), "facman-action");
    if (action != NULL && gtk_widget_is_sensitive(widget)) {
        AtkObject *accessible = gtk_widget_get_accessible(widget);
        require(atk_object_get_name(accessible) != NULL, "action has a native accessible name");
        gtk_widget_grab_focus(widget);
        drain();
        require(gtk_window_get_focus(GTK_WINDOW(view->window)) == widget, "native action focus");
        GtkAllocation bounds;
        gtk_widget_get_allocation(widget, &bounds);
        if (bounds.width < 16 || bounds.height < 16)
            g_printerr("Unusable action allocation: %s (%d x %d)\n", action, bounds.width, bounds.height);
        require(bounds.width >= 16 && bounds.height >= 16, "action has usable allocation");
        gint x, y;
        require(gtk_widget_translate_coordinates(widget, view->window, 0, 0, &x, &y), "action belongs to this window");
        require(x >= 0 && y >= 0 && x + bounds.width <= gtk_widget_get_allocated_width(view->window) &&
            y + bounds.height <= gtk_widget_get_allocated_height(view->window), "action fits the native window");
        for (GtkWidget *parent = gtk_widget_get_parent(widget); parent != NULL; parent = gtk_widget_get_parent(parent)) {
            require(gtk_widget_translate_coordinates(widget, parent, 0, 0, &x, &y), "action has ancestor coordinates");
            require(x >= 0 && y >= 0 && x + bounds.width <= gtk_widget_get_allocated_width(parent) &&
                y + bounds.height <= gtk_widget_get_allocated_height(parent), "action fits each ancestor viewport");
        }
        guint before = actions->len;
        gtk_button_clicked(GTK_BUTTON(widget));
        drain();
        require(actions->len == before + 1, "each action records once");
        require(g_strcmp0(g_ptr_array_index(actions, before), action) == 0, "exact action recorded");
        GList *windows = gtk_window_list_toplevels();
        guint visible = 0;
        for (GList *item = windows; item != NULL; item = item->next)
            if (gtk_widget_get_visible(item->data)) ++visible;
        g_list_free(windows);
        require(visible == 1, "actions cannot open a live dialog or child window");
    }
    if (GTK_IS_CONTAINER(widget)) {
        GList *children = gtk_container_get_children(GTK_CONTAINER(widget));
        for (GList *item = children; item != NULL; item = item->next)
            check_controls(item->data, view);
        g_list_free(children);
    }
}

static gboolean contains_action(const gchar *action)
{
    for (guint index = 0; index < actions->len; ++index)
        if (g_strcmp0(g_ptr_array_index(actions, index), action) == 0) return TRUE;
    return FALSE;
}

static void observe_fonts(GtkWidget *widget)
{
    if (!gtk_widget_get_mapped(widget)) return;
    if (GTK_IS_LABEL(widget) && *gtk_label_get_text(GTK_LABEL(widget)) != '\0') {
        require(++font_label_observations <= 10000, "bounded mapped label observations");
        font_unknown_glyphs += pango_layout_get_unknown_glyphs_count(gtk_label_get_layout(GTK_LABEL(widget)));
    }
    if (GTK_IS_CONTAINER(widget)) {
        GList *children = gtk_container_get_children(GTK_CONTAINER(widget));
        for (GList *item = children; item != NULL; item = item->next)
            observe_fonts(item->data);
        g_list_free(children);
    }
}

static double linear(double value)
{
    return value <= .04045 ? value / 12.92 : pow((value + .055) / 1.055, 2.4);
}

static double observed_contrast(FacManGtkView *view)
{
    GdkRGBA foreground;
    gtk_style_context_get_color(gtk_widget_get_style_context(view->deck_status), GTK_STATE_FLAG_NORMAL, &foreground);
    require(foreground.alpha == 1, "observed foreground is opaque");
    cairo_surface_t *surface = cairo_image_surface_create(CAIRO_FORMAT_ARGB32, 1, 1);
    cairo_t *canvas = cairo_create(surface);
    gtk_render_background(gtk_widget_get_style_context(view->window), canvas, 0, 0, 1, 1);
    cairo_surface_flush(surface);
    guint32 pixel = *(guint32 *)cairo_image_surface_get_data(surface);
    require((pixel >> 24) == 255, "native window background is opaque for contrast observation");
    double background = .2126 * linear(((pixel >> 16) & 255) / 255.0) +
        .7152 * linear(((pixel >> 8) & 255) / 255.0) + .0722 * linear((pixel & 255) / 255.0);
    double text = .2126 * linear(foreground.red) + .7152 * linear(foreground.green) + .0722 * linear(foreground.blue);
    cairo_destroy(canvas);
    cairo_surface_destroy(surface);
    return (MAX(text, background) + .05) / (MIN(text, background) + .05);
}

static gboolean wait_for_external_probe(gpointer context)
{
    static guint ticks;
    gchar *release = g_build_filename(output_root, "external.release", NULL);
    gboolean done = g_file_test(release, G_FILE_TEST_IS_REGULAR);
    g_free(release);
    if (done || ++ticks >= 300) {
        timed_out = !done;
        g_application_quit(G_APPLICATION(context));
        return G_SOURCE_REMOVE;
    }
    return G_SOURCE_CONTINUE;
}

static gchar *field(GKeyFile *input, const gchar *name, GPtrArray *strings)
{
    GError *error = NULL;
    gchar *value = g_key_file_get_string(input, "case", name, &error);
    require(error == NULL && value != NULL && strlen(value) <= 16384, "bounded required case field");
    g_ptr_array_add(strings, value);
    return value;
}

int main(int argc, char **argv)
{
    if (argc != 3) return 2;
    GStatBuf metadata;
    require(g_stat(argv[1], &metadata) == 0 && metadata.st_size <= 1024 * 1024, "bounded fixture file");
    GKeyFile *input = g_key_file_new();
    GError *error = NULL;
    require(g_key_file_load_from_file(input, argv[1], G_KEY_FILE_NONE, &error), "fixture key file parses");
    GPtrArray *strings = g_ptr_array_new_with_free_func(g_free);
    require(g_strcmp0(field(input, "schema", strings), "facman.gtk_gallery_case.v1") == 0, "known fixture schema");
    const gchar *state = field(input, "state", strings);
    const gchar *variant = field(input, "variant", strings);
    const gchar *states[] = {"ready", "blocked", "busy", "recovery", "empty", "error"};
    gboolean known = FALSE;
    for (guint index = 0; index < G_N_ELEMENTS(states); ++index) known |= g_strcmp0(state, states[index]) == 0;
    require(known, "known semantic state");
    FacManGtkPresentation presentation = {
        .instance_name = field(input, "instance_name", strings),
        .instance_summary = field(input, "instance_summary", strings),
        .installation_summary = field(input, "installation_summary", strings),
        .status = field(input, "status", strings), .readiness = field(input, "readiness", strings),
        .activity = field(input, "activity", strings), .last_run = field(input, "last_run", strings),
        .operation_id = field(input, "operation_id", strings),
        .primary_label = field(input, "primary_label", strings),
        .primary_accessibility = field(input, "primary_accessibility", strings),
        .secondary_label = field(input, "secondary_label", strings),
    };
    presentation.primary_available = g_key_file_get_boolean(input, "case", "primary_available", &error);
    require(error == NULL, "primary availability is explicit");
    presentation.primary_visible = g_key_file_get_boolean(input, "case", "primary_visible", &error);
    require(error == NULL, "primary visibility is explicit");
    gtk_init(&argc, &argv);
    GtkApplication *application = gtk_application_new("io.github.julesc013.facman.gallery", G_APPLICATION_NON_UNIQUE);
    require(g_application_register(G_APPLICATION(application), NULL, &error), "register gallery application");
    actions = g_ptr_array_new_with_free_func(g_free);
    FacManGtkView *view = facman_gtk_view_new(application, FALSE, TRUE, record_action, NULL);
    g_signal_connect_swapped(application, "activate", G_CALLBACK(gtk_window_present), view->window);
    gchar *title = g_strdup_printf("FacMan GTK control gallery — %s/%s", state, variant);
    gtk_window_set_title(GTK_WINDOW(view->window), title);
    facman_gtk_view_render(view, &presentation);
    gtk_widget_show_all(view->window);
    drain();
    const gchar *pages[] = {"instances", "installations", "activity", "settings", "advanced"};
    for (guint index = 0; index < G_N_ELEMENTS(pages); ++index) {
        require(gtk_accel_groups_activate(G_OBJECT(view->window), GDK_KEY_1 + index, GDK_CONTROL_MASK), "production menu accelerator");
        drain();
        require(g_strcmp0(gtk_stack_get_visible_child_name(GTK_STACK(view->stack)), pages[index]) == 0, "accelerator selects exact page");
        gtk_window_set_focus(GTK_WINDOW(view->window), NULL);
        require(gtk_widget_child_focus(view->window, GTK_DIR_TAB_FORWARD), "native forward Tab focus entry");
        require(gtk_window_get_focus(GTK_WINDOW(view->window)) != NULL, "Tab establishes native focus");
        check_controls(view->window, view);
        observe_fonts(view->window);
        require(g_strcmp0(gtk_label_get_text(GTK_LABEL(view->deck_instance)), presentation.instance_name) == 0, "actions preserve fixed projection");
    }
    require(contains_action("product.inspect"), "Advanced routes through recorder");
    require(contains_action("launch.secondary"), "refresh or recovery routes through recorder");
    if (g_strcmp0(state, "empty") == 0 || g_strcmp0(state, "error") == 0) {
        require(!gtk_widget_get_visible(view->deck_primary), "no fabricated primary action");
        require(g_strcmp0(gtk_label_get_text(GTK_LABEL(view->deck_instance)), "No instance selected") == 0, "no sample instance");
    }
    if (g_strcmp0(state, "ready") == 0) require(gtk_widget_is_sensitive(view->deck_primary), "ready action available");
    if (g_strcmp0(state, "blocked") == 0) require(strstr(gtk_label_get_text(GTK_LABEL(view->deck_status)), "stale_readiness") != NULL, "exact blocked reason");
    if (g_strcmp0(state, "busy") == 0) require(strstr(gtk_label_get_text(GTK_LABEL(view->deck_operation)), "gallery-operation") != NULL, "exact busy identity");
    if (g_strcmp0(state, "recovery") == 0) require(strstr(gtk_label_get_text(GTK_LABEL(view->deck_status)), "gallery-transaction") != NULL, "exact recovery identity");
    if (g_strcmp0(variant, "overflow") == 0)
        require(g_strcmp0(atk_object_get_description(gtk_widget_get_accessible(view->deck_instance)), presentation.instance_name) == 0, "long identity retained for accessibility");
    facman_gtk_apply_oem(NULL, view);
    require(gtk_accel_groups_activate(G_OBJECT(view->window), GDK_KEY_0, GDK_CONTROL_MASK), "system appearance accelerator");
    require(!gtk_style_context_has_class(gtk_widget_get_style_context(view->deck), "facman-oem-launch-deck"), "system appearance recovery");
    facman_gtk_view_page(view, "instances");
    drain();
    double contrast = observed_contrast(view);
    require(contrast >= 4.5, "observed native body text contrast");
    output_root = argv[2];
    require(g_mkdir_with_parents(output_root, 0700) == 0, "output directory");
    gint width, height;
    gtk_window_get_size(GTK_WINDOW(view->window), &width, &height);
    GdkPixbuf *image = gdk_pixbuf_get_from_window(gtk_widget_get_window(view->window), 0, 0, width, height);
    require(image != NULL, "capture actual native window");
    gchar *path = g_build_filename(output_root, "window.png", NULL);
    require(gdk_pixbuf_save(image, path, "png", &error, NULL), "save native pixels");
    g_free(path); g_object_unref(image);
    GKeyFile *report = g_key_file_new();
    g_key_file_set_string(report, "result", "state", state);
    g_key_file_set_string(report, "result", "variant", variant);
    g_key_file_set_string(report, "result", "window", title);
    g_key_file_set_integer(report, "result", "pid", getpid());
    g_key_file_set_integer(report, "result", "assertions", assertions);
    g_key_file_set_double(report, "result", "body_text_contrast", contrast);
    g_key_file_set_integer(report, "result", "widget_scale_factor", gtk_widget_get_scale_factor(view->window));
    g_key_file_set_double(report, "result", "font_dpi", pango_cairo_context_get_resolution(gtk_widget_get_pango_context(view->deck_instance)));
    g_key_file_set_integer(report, "result", "identity_unknown_glyphs", pango_layout_get_unknown_glyphs_count(gtk_label_get_layout(GTK_LABEL(view->instance_summary))));
    g_key_file_set_integer(report, "result", "font_label_observations", font_label_observations);
    g_key_file_set_integer(report, "result", "font_unknown_glyphs", font_unknown_glyphs);
    g_key_file_set_string_list(report, "result", "actions", (const gchar *const *)actions->pdata, actions->len);
    path = g_build_filename(output_root, "native.ini", NULL);
    require(g_key_file_save_to_file(report, path, &error), "save native receipt");
    g_free(path);
    g_timeout_add(100, wait_for_external_probe, application);
    g_application_run(G_APPLICATION(application), 0, NULL);
    gtk_widget_destroy(view->window);
    facman_gtk_view_free(view);
    g_object_unref(application);
    g_key_file_unref(report); g_key_file_unref(input);
    g_ptr_array_unref(actions); g_ptr_array_unref(strings); g_free(title);
    return timed_out ? 3 : 0;
}
