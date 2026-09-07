// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#pragma once
#include <gtk/gtk.h>
#include <atk/atk.h>

typedef void (*FacManGtkActionHandler)(const gchar *action, gpointer context);

typedef struct {
    const gchar *instance_name;
    const gchar *instance_summary;
    const gchar *installation_summary;
    const gchar *status;
    const gchar *readiness;
    const gchar *activity;
    const gchar *last_run;
    const gchar *operation_id;
    const gchar *primary_label;
    const gchar *primary_accessibility;
    gboolean primary_available;
    gboolean primary_visible;
    const gchar *secondary_label;
} FacManGtkPresentation;

typedef struct {
    GtkApplication *application;
    GtkWidget *window;
    GtkWidget *stack;
    GtkWidget *deck;
    GtkWidget *deck_instance;
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
    gboolean evidence_mode;
    gboolean gallery_mode;
    FacManGtkActionHandler on_action;
    gpointer action_context;
} FacManGtkView;

FacManGtkView *facman_gtk_view_new(GtkApplication *application, gboolean evidence_mode,
    gboolean gallery_mode, FacManGtkActionHandler on_action, gpointer action_context);
void facman_gtk_view_free(FacManGtkView *view);
void facman_gtk_view_render(FacManGtkView *view, const FacManGtkPresentation *presentation);
void facman_gtk_view_page(FacManGtkView *view, const gchar *page);
void facman_gtk_accessibility(GtkWidget *widget, const gchar *name, const gchar *description);
GtkWidget *facman_gtk_label(const gchar *text, gfloat xalign);
void facman_gtk_system_native(FacManGtkView *view);
void facman_gtk_apply_system_native(GtkMenuItem *item, gpointer user_data);
void facman_gtk_apply_oem(GtkMenuItem *item, gpointer user_data);
