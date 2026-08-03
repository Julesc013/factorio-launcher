// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "generated_live_presentation.h"

#include <glib.h>

int main(int argc, char **argv)
{
    gchar *document = NULL;
    gsize document_size = 0;
    GError *error = NULL;

    g_assert_cmpint(argc, ==, 3);
    g_assert_true(g_file_get_contents(argv[1], &document, &document_size, &error));
    g_assert_no_error(error);
    g_assert_cmpuint(document_size, >, 0);

    gchar *envelope_schema = facman_record_text(document, "schema");
    gchar *payload_schema = facman_payload_text(document, "schema");
    gchar *session_id = facman_payload_text(document, "session_id");

    g_assert_cmpstr(envelope_schema, ==, "facman.transport_response.v2");
    g_assert_cmpstr(payload_schema, ==, "factorio.launch_session.v1");
    g_assert_cmpstr(session_id, ==, "session.completed.fixture");
    g_assert_true(facman_payload_boolean(document, "complete"));

    g_free(session_id);
    g_free(payload_schema);
    g_free(envelope_schema);
    g_free(document);

    document = NULL;
    document_size = 0;
    g_assert_true(g_file_get_contents(argv[2], &document, &document_size, &error));
    g_assert_no_error(error);
    g_assert_true(facman_payload_recovery_required(document));
    gchar *recovery_id = facman_payload_recovery_text(document, "transaction_id");
    g_assert_cmpstr(recovery_id, ==, "tx.recovery.fixture");
    g_free(recovery_id);
    g_free(document);
    return 0;
}
