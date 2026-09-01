// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "transport_validator.h"

#include <string.h>

static const FacManGtkTransportExpectation kExpectation = {
    "request.test",
    "operation.test",
    "attempt.test",
    "product.inspect",
};

static const gchar *kValidResponse =
    "{\"schema\":\"facman.transport_response.v2\",\"protocol_version\":2,"
    "\"request_id\":\"request.test\",\"command\":\"product.inspect\","
    "\"outcome\":\"ok\",\"payload\":{},\"error\":null,\"diagnostics\":[],\"effects\":[],"
    "\"operation\":{\"schema\":\"ulk.operation_outcome.v1\","
    "\"operation_id\":\"operation.test\",\"attempt_id\":\"attempt.test\","
    "\"outcome\":\"completed\",\"effects_may_have_occurred\":false,"
    "\"recovery\":{\"required\":false,\"transaction_id\":\"\",\"inspect_command\":\"\"}}}";

static void facman_assert_failure(const guint8 *data, gsize size, const gchar *code)
{
    gchar *failure = facman_gtk_transport_validate(
        data, size, NULL, 0, &kExpectation);
    g_assert_nonnull(failure);
    g_assert_nonnull(g_strstr_len(failure, -1, code));
    g_free(failure);
}

static void facman_test_valid_response(void)
{
    gchar *failure = facman_gtk_transport_validate(
        (const guint8 *)kValidResponse, strlen(kValidResponse), NULL, 0, &kExpectation);
    g_assert_null(failure);
}

static void facman_test_invalid_utf8(void)
{
    const guint8 invalid[] = { '{', '}', 0xFF };
    facman_assert_failure(invalid, sizeof invalid, "frontend_backend_invalid_utf8");
}

static void facman_test_trailing_document(void)
{
    gchar *joined = g_strconcat(kValidResponse, "{}", NULL);
    facman_assert_failure(
        (const guint8 *)joined, strlen(joined), "frontend_backend_protocol_invalid");
    g_free(joined);
}

static void facman_test_duplicate_member(void)
{
    const gchar *duplicate =
        "{\"schema\":\"facman.transport_response.v2\",\"schema\":"
        "\"facman.transport_response.v2\"}";
    facman_assert_failure(
        (const guint8 *)duplicate, strlen(duplicate), "frontend_backend_protocol_invalid");
}

static void facman_test_mismatched_request(void)
{
    gchar *mismatched = g_strdup(kValidResponse);
    gchar *member = g_strstr_len(mismatched, -1, "request.test");
    g_assert_nonnull(member);
    memcpy(member, "request.fail", strlen("request.fail"));
    facman_assert_failure(
        (const guint8 *)mismatched,
        strlen(mismatched),
        "frontend_backend_correlation_mismatch");
    g_free(mismatched);
}

static void facman_test_nested_duplicate(void)
{
    gchar *original = g_strdup(kValidResponse);
    gchar *payload = g_strstr_len(original, -1, "\"payload\":{}");
    g_assert_nonnull(payload);
    gchar *duplicate = g_strdup_printf(
        "%.*s\"payload\":{\"a\":1,\"a\":2}%s",
        (int)(payload - original),
        original,
        payload + strlen("\"payload\":{}"));
    facman_assert_failure(
        (const guint8 *)duplicate, strlen(duplicate), "frontend_backend_protocol_invalid");
    g_free(duplicate);
    g_free(original);
}

int main(int argc, char **argv)
{
    g_test_init(&argc, &argv, NULL);
    g_test_add_func("/facman/transport/valid", facman_test_valid_response);
    g_test_add_func("/facman/transport/invalid-utf8", facman_test_invalid_utf8);
    g_test_add_func("/facman/transport/trailing-document", facman_test_trailing_document);
    g_test_add_func("/facman/transport/duplicate-member", facman_test_duplicate_member);
    g_test_add_func("/facman/transport/mismatched-request", facman_test_mismatched_request);
    g_test_add_func("/facman/transport/nested-duplicate", facman_test_nested_duplicate);
    return g_test_run();
}
