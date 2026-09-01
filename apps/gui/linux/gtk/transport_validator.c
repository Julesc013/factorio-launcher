// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "transport_validator.h"

#include <string.h>

enum { FACMAN_JSON_MAXIMUM_DEPTH = 64 };

typedef enum {
    FACMAN_JSON_INVALID,
    FACMAN_JSON_OBJECT,
    FACMAN_JSON_ARRAY,
    FACMAN_JSON_STRING,
    FACMAN_JSON_NUMBER,
    FACMAN_JSON_BOOLEAN,
    FACMAN_JSON_NULL
} FacManJsonKind;

typedef struct {
    const gchar *cursor;
    const gchar *end;
    const gchar *error;
    guint depth;
} FacManJsonParser;

typedef struct {
    gchar *schema;
    gchar *request_id;
    gchar *command;
    gchar *outcome;
    gchar *operation_schema;
    gchar *operation_id;
    gchar *attempt_id;
    gchar *operation_outcome;
    gboolean protocol_version;
    gboolean payload;
    gboolean error_member;
    gboolean diagnostics;
    gboolean effects;
    gboolean operation;
    gboolean effects_may_have_occurred;
    gboolean recovery;
} FacManTransportEnvelope;

static gboolean facman_parse_value(FacManJsonParser *parser, FacManJsonKind *kind);

static gboolean facman_json_fail(FacManJsonParser *parser, const gchar *error)
{
    if (parser->error == NULL) parser->error = error;
    return FALSE;
}

static void facman_skip_space(FacManJsonParser *parser)
{
    while (parser->cursor < parser->end &&
           (*parser->cursor == ' ' || *parser->cursor == '\t' ||
            *parser->cursor == '\r' || *parser->cursor == '\n'))
        parser->cursor++;
}

static gboolean facman_take(FacManJsonParser *parser, gchar expected)
{
    facman_skip_space(parser);
    if (parser->cursor >= parser->end || *parser->cursor != expected)
        return facman_json_fail(parser, "unexpected JSON token");
    parser->cursor++;
    return TRUE;
}

static gint facman_hex_digit(gchar value)
{
    if (value >= '0' && value <= '9') return value - '0';
    if (value >= 'a' && value <= 'f') return value - 'a' + 10;
    if (value >= 'A' && value <= 'F') return value - 'A' + 10;
    return -1;
}

static gboolean facman_parse_hex4(FacManJsonParser *parser, gunichar *value)
{
    if ((gsize)(parser->end - parser->cursor) < 4)
        return facman_json_fail(parser, "truncated JSON Unicode escape");
    gunichar decoded = 0;
    for (guint index = 0; index < 4; ++index) {
        gint digit = facman_hex_digit(parser->cursor[index]);
        if (digit < 0) return facman_json_fail(parser, "invalid JSON Unicode escape");
        decoded = (decoded << 4) | (gunichar)digit;
    }
    parser->cursor += 4;
    *value = decoded;
    return TRUE;
}

static gboolean facman_append_unicode(
    FacManJsonParser *parser,
    GString *output,
    gunichar value)
{
    if (value >= 0xD800 && value <= 0xDBFF) {
        if ((gsize)(parser->end - parser->cursor) < 6 ||
            parser->cursor[0] != '\\' || parser->cursor[1] != 'u')
            return facman_json_fail(parser, "unpaired high surrogate in JSON string");
        parser->cursor += 2;
        gunichar low = 0;
        if (!facman_parse_hex4(parser, &low)) return FALSE;
        if (low < 0xDC00 || low > 0xDFFF)
            return facman_json_fail(parser, "invalid low surrogate in JSON string");
        value = 0x10000 + ((value - 0xD800) << 10) + (low - 0xDC00);
    } else if (value >= 0xDC00 && value <= 0xDFFF) {
        return facman_json_fail(parser, "unpaired low surrogate in JSON string");
    }
    if (value == 0 || !g_unichar_validate(value))
        return facman_json_fail(parser, "unsupported Unicode scalar in JSON string");
    g_string_append_unichar(output, value);
    return TRUE;
}

static gchar *facman_parse_string(FacManJsonParser *parser)
{
    facman_skip_space(parser);
    if (parser->cursor >= parser->end || *parser->cursor != '"') {
        facman_json_fail(parser, "JSON string expected");
        return NULL;
    }
    parser->cursor++;
    GString *output = g_string_new("");
    while (parser->cursor < parser->end) {
        guchar current = (guchar)*parser->cursor++;
        if (current == '"') return g_string_free(output, FALSE);
        if (current < 0x20) {
            facman_json_fail(parser, "unescaped control character in JSON string");
            break;
        }
        if (current != '\\') {
            if (current < 0x80) {
                g_string_append_c(output, (gchar)current);
            } else {
                const gchar *start = parser->cursor - 1;
                const gchar *next = g_utf8_next_char(start);
                g_string_append_len(output, start, next - start);
                parser->cursor = next;
            }
            continue;
        }
        if (parser->cursor >= parser->end) {
            facman_json_fail(parser, "truncated JSON escape");
            break;
        }
        gchar escaped = *parser->cursor++;
        switch (escaped) {
            case '"': g_string_append_c(output, '"'); break;
            case '\\': g_string_append_c(output, '\\'); break;
            case '/': g_string_append_c(output, '/'); break;
            case 'b': g_string_append_c(output, '\b'); break;
            case 'f': g_string_append_c(output, '\f'); break;
            case 'n': g_string_append_c(output, '\n'); break;
            case 'r': g_string_append_c(output, '\r'); break;
            case 't': g_string_append_c(output, '\t'); break;
            case 'u': {
                gunichar value = 0;
                if (!facman_parse_hex4(parser, &value) ||
                    !facman_append_unicode(parser, output, value))
                    goto invalid;
                break;
            }
            default:
                facman_json_fail(parser, "invalid JSON escape");
                goto invalid;
        }
    }
    if (parser->error == NULL) facman_json_fail(parser, "unterminated JSON string");
invalid:
    g_string_free(output, TRUE);
    return NULL;
}

static gboolean facman_parse_literal(
    FacManJsonParser *parser,
    const gchar *literal,
    FacManJsonKind parsed_kind,
    FacManJsonKind *kind)
{
    gsize length = strlen(literal);
    if ((gsize)(parser->end - parser->cursor) < length ||
        memcmp(parser->cursor, literal, length) != 0)
        return facman_json_fail(parser, "invalid JSON literal");
    parser->cursor += length;
    *kind = parsed_kind;
    return TRUE;
}

static gboolean facman_parse_number(FacManJsonParser *parser)
{
    const gchar *cursor = parser->cursor;
    if (cursor < parser->end && *cursor == '-') cursor++;
    if (cursor >= parser->end) return facman_json_fail(parser, "truncated JSON number");
    if (*cursor == '0') {
        cursor++;
        if (cursor < parser->end && g_ascii_isdigit(*cursor))
            return facman_json_fail(parser, "leading zero in JSON number");
    } else if (*cursor >= '1' && *cursor <= '9') {
        while (cursor < parser->end && g_ascii_isdigit(*cursor)) cursor++;
    } else {
        return facman_json_fail(parser, "invalid JSON number");
    }
    if (cursor < parser->end && *cursor == '.') {
        cursor++;
        if (cursor >= parser->end || !g_ascii_isdigit(*cursor))
            return facman_json_fail(parser, "invalid JSON fraction");
        while (cursor < parser->end && g_ascii_isdigit(*cursor)) cursor++;
    }
    if (cursor < parser->end && (*cursor == 'e' || *cursor == 'E')) {
        cursor++;
        if (cursor < parser->end && (*cursor == '+' || *cursor == '-')) cursor++;
        if (cursor >= parser->end || !g_ascii_isdigit(*cursor))
            return facman_json_fail(parser, "invalid JSON exponent");
        while (cursor < parser->end && g_ascii_isdigit(*cursor)) cursor++;
    }
    parser->cursor = cursor;
    return TRUE;
}

static gboolean facman_parse_array(FacManJsonParser *parser)
{
    if (++parser->depth > FACMAN_JSON_MAXIMUM_DEPTH)
        return facman_json_fail(parser, "JSON nesting limit exceeded");
    if (!facman_take(parser, '[')) return FALSE;
    facman_skip_space(parser);
    if (parser->cursor < parser->end && *parser->cursor == ']') {
        parser->cursor++;
        parser->depth--;
        return TRUE;
    }
    for (;;) {
        FacManJsonKind ignored = FACMAN_JSON_INVALID;
        if (!facman_parse_value(parser, &ignored)) return FALSE;
        facman_skip_space(parser);
        if (parser->cursor < parser->end && *parser->cursor == ']') {
            parser->cursor++;
            parser->depth--;
            return TRUE;
        }
        if (!facman_take(parser, ',')) return FALSE;
    }
}

static gboolean facman_parse_object(FacManJsonParser *parser)
{
    if (++parser->depth > FACMAN_JSON_MAXIMUM_DEPTH)
        return facman_json_fail(parser, "JSON nesting limit exceeded");
    if (!facman_take(parser, '{')) return FALSE;
    GHashTable *members = g_hash_table_new_full(g_str_hash, g_str_equal, g_free, NULL);
    facman_skip_space(parser);
    if (parser->cursor < parser->end && *parser->cursor == '}') {
        parser->cursor++;
        parser->depth--;
        g_hash_table_unref(members);
        return TRUE;
    }
    for (;;) {
        gchar *key = facman_parse_string(parser);
        if (key == NULL) break;
        if (g_hash_table_contains(members, key)) {
            g_free(key);
            facman_json_fail(parser, "duplicate JSON object member");
            break;
        }
        g_hash_table_add(members, key);
        if (!facman_take(parser, ':')) break;
        FacManJsonKind ignored = FACMAN_JSON_INVALID;
        if (!facman_parse_value(parser, &ignored)) break;
        facman_skip_space(parser);
        if (parser->cursor < parser->end && *parser->cursor == '}') {
            parser->cursor++;
            parser->depth--;
            g_hash_table_unref(members);
            return TRUE;
        }
        if (!facman_take(parser, ',')) break;
    }
    g_hash_table_unref(members);
    return FALSE;
}

static gboolean facman_parse_value(FacManJsonParser *parser, FacManJsonKind *kind)
{
    facman_skip_space(parser);
    if (parser->cursor >= parser->end)
        return facman_json_fail(parser, "JSON value expected");
    if (*parser->cursor == '{') {
        *kind = FACMAN_JSON_OBJECT;
        return facman_parse_object(parser);
    }
    if (*parser->cursor == '[') {
        *kind = FACMAN_JSON_ARRAY;
        return facman_parse_array(parser);
    }
    if (*parser->cursor == '"') {
        gchar *value = facman_parse_string(parser);
        if (value == NULL) return FALSE;
        g_free(value);
        *kind = FACMAN_JSON_STRING;
        return TRUE;
    }
    if (*parser->cursor == '-' || g_ascii_isdigit(*parser->cursor)) {
        if (!facman_parse_number(parser)) return FALSE;
        *kind = FACMAN_JSON_NUMBER;
        return TRUE;
    }
    if (*parser->cursor == 't') return facman_parse_literal(parser, "true", FACMAN_JSON_BOOLEAN, kind);
    if (*parser->cursor == 'f') return facman_parse_literal(parser, "false", FACMAN_JSON_BOOLEAN, kind);
    if (*parser->cursor == 'n') return facman_parse_literal(parser, "null", FACMAN_JSON_NULL, kind);
    return facman_json_fail(parser, "invalid JSON value");
}

static gboolean facman_parse_typed_value(
    FacManJsonParser *parser,
    FacManJsonKind first,
    FacManJsonKind second)
{
    FacManJsonKind actual = FACMAN_JSON_INVALID;
    return facman_parse_value(parser, &actual) && (actual == first || actual == second ||
        facman_json_fail(parser, "JSON member has the wrong type"));
}

static gboolean facman_parse_exact_two(FacManJsonParser *parser)
{
    facman_skip_space(parser);
    const gchar *start = parser->cursor;
    if (!facman_parse_number(parser)) return FALSE;
    return parser->cursor - start == 1 && *start == '2'
        ? TRUE : facman_json_fail(parser, "transport protocol_version must be 2");
}

static gboolean facman_known_value(const gchar *value, const gchar *const *allowed)
{
    for (guint index = 0; allowed[index] != NULL; ++index)
        if (g_strcmp0(value, allowed[index]) == 0) return TRUE;
    return FALSE;
}

static gboolean facman_parse_recovery(FacManJsonParser *parser)
{
    if (++parser->depth > FACMAN_JSON_MAXIMUM_DEPTH)
        return facman_json_fail(parser, "JSON nesting limit exceeded");
    if (!facman_take(parser, '{')) return FALSE;
    GHashTable *members = g_hash_table_new_full(g_str_hash, g_str_equal, g_free, NULL);
    gboolean required = FALSE;
    gboolean transaction_id = FALSE;
    gboolean inspect_command = FALSE;
    for (;;) {
        facman_skip_space(parser);
        if (parser->cursor < parser->end && *parser->cursor == '}') {
            parser->cursor++;
            parser->depth--;
            gboolean complete = required && transaction_id && inspect_command;
            g_hash_table_unref(members);
            return complete ? TRUE : facman_json_fail(parser, "incomplete operation recovery object");
        }
        gchar *key = facman_parse_string(parser);
        if (key == NULL) break;
        if (g_hash_table_contains(members, key)) {
            g_free(key);
            facman_json_fail(parser, "duplicate recovery member");
            break;
        }
        g_hash_table_add(members, key);
        if (!facman_take(parser, ':')) break;
        if (g_strcmp0(key, "required") == 0) {
            if (!facman_parse_typed_value(parser, FACMAN_JSON_BOOLEAN, FACMAN_JSON_BOOLEAN)) break;
            required = TRUE;
        } else if (g_strcmp0(key, "transaction_id") == 0 ||
                   g_strcmp0(key, "inspect_command") == 0) {
            gchar *value = facman_parse_string(parser);
            if (value == NULL) break;
            if (g_strcmp0(key, "transaction_id") == 0) transaction_id = TRUE;
            else inspect_command = TRUE;
            g_free(value);
        } else {
            facman_json_fail(parser, "unexpected recovery member");
            break;
        }
        facman_skip_space(parser);
        if (parser->cursor < parser->end && *parser->cursor == '}') continue;
        if (!facman_take(parser, ',')) break;
    }
    g_hash_table_unref(members);
    return FALSE;
}

static gboolean facman_parse_operation(
    FacManJsonParser *parser,
    FacManTransportEnvelope *envelope)
{
    static const gchar *const outcomes[] = {
        "cancelled_before_dispatch", "refused_before_effects", "completed",
        "cancellation_requested_but_completed", "recovery_required", "outcome_unknown", NULL
    };
    if (++parser->depth > FACMAN_JSON_MAXIMUM_DEPTH)
        return facman_json_fail(parser, "JSON nesting limit exceeded");
    if (!facman_take(parser, '{')) return FALSE;
    GHashTable *members = g_hash_table_new_full(g_str_hash, g_str_equal, g_free, NULL);
    for (;;) {
        facman_skip_space(parser);
        if (parser->cursor < parser->end && *parser->cursor == '}') {
            parser->cursor++;
            parser->depth--;
            gboolean complete = envelope->operation_schema != NULL &&
                envelope->operation_id != NULL && envelope->attempt_id != NULL &&
                envelope->operation_outcome != NULL &&
                envelope->effects_may_have_occurred && envelope->recovery;
            g_hash_table_unref(members);
            return complete ? TRUE : facman_json_fail(parser, "incomplete transport operation object");
        }
        gchar *key = facman_parse_string(parser);
        if (key == NULL) break;
        if (g_hash_table_contains(members, key)) {
            g_free(key);
            facman_json_fail(parser, "duplicate transport operation member");
            break;
        }
        g_hash_table_add(members, key);
        if (!facman_take(parser, ':')) break;
        if (g_strcmp0(key, "schema") == 0) {
            envelope->operation_schema = facman_parse_string(parser);
        } else if (g_strcmp0(key, "operation_id") == 0) {
            envelope->operation_id = facman_parse_string(parser);
        } else if (g_strcmp0(key, "attempt_id") == 0) {
            envelope->attempt_id = facman_parse_string(parser);
        } else if (g_strcmp0(key, "outcome") == 0) {
            envelope->operation_outcome = facman_parse_string(parser);
            if (envelope->operation_outcome != NULL &&
                !facman_known_value(envelope->operation_outcome, outcomes))
                facman_json_fail(parser, "unknown operation outcome");
        } else if (g_strcmp0(key, "effects_may_have_occurred") == 0) {
            if (!facman_parse_typed_value(parser, FACMAN_JSON_BOOLEAN, FACMAN_JSON_BOOLEAN)) break;
            envelope->effects_may_have_occurred = TRUE;
        } else if (g_strcmp0(key, "recovery") == 0) {
            if (!facman_parse_recovery(parser)) break;
            envelope->recovery = TRUE;
        } else {
            facman_json_fail(parser, "unexpected transport operation member");
        }
        if (parser->error != NULL) break;
        facman_skip_space(parser);
        if (parser->cursor < parser->end && *parser->cursor == '}') continue;
        if (!facman_take(parser, ',')) break;
    }
    g_hash_table_unref(members);
    return FALSE;
}

static gboolean facman_parse_envelope(
    FacManJsonParser *parser,
    FacManTransportEnvelope *envelope)
{
    static const gchar *const outcomes[] = {
        "ok", "refused", "invalid_argument", "unavailable", "not_found", "conflict",
        "cancelled", "timeout", "recovery_required", "internal_error", NULL
    };
    if (++parser->depth > FACMAN_JSON_MAXIMUM_DEPTH)
        return facman_json_fail(parser, "JSON nesting limit exceeded");
    if (!facman_take(parser, '{')) return FALSE;
    GHashTable *members = g_hash_table_new_full(g_str_hash, g_str_equal, g_free, NULL);
    for (;;) {
        facman_skip_space(parser);
        if (parser->cursor < parser->end && *parser->cursor == '}') {
            parser->cursor++;
            parser->depth--;
            gboolean complete = envelope->schema != NULL && envelope->protocol_version &&
                envelope->request_id != NULL && envelope->command != NULL &&
                envelope->outcome != NULL && envelope->payload && envelope->error_member &&
                envelope->diagnostics && envelope->effects && envelope->operation;
            g_hash_table_unref(members);
            return complete ? TRUE : facman_json_fail(parser, "incomplete transport response envelope");
        }
        gchar *key = facman_parse_string(parser);
        if (key == NULL) break;
        if (g_hash_table_contains(members, key)) {
            g_free(key);
            facman_json_fail(parser, "duplicate transport response member");
            break;
        }
        g_hash_table_add(members, key);
        if (!facman_take(parser, ':')) break;
        if (g_strcmp0(key, "schema") == 0) {
            envelope->schema = facman_parse_string(parser);
        } else if (g_strcmp0(key, "protocol_version") == 0) {
            if (!facman_parse_exact_two(parser)) break;
            envelope->protocol_version = TRUE;
        } else if (g_strcmp0(key, "request_id") == 0) {
            envelope->request_id = facman_parse_string(parser);
        } else if (g_strcmp0(key, "command") == 0) {
            envelope->command = facman_parse_string(parser);
        } else if (g_strcmp0(key, "outcome") == 0) {
            envelope->outcome = facman_parse_string(parser);
            if (envelope->outcome != NULL && !facman_known_value(envelope->outcome, outcomes))
                facman_json_fail(parser, "unknown transport outcome");
        } else if (g_strcmp0(key, "payload") == 0) {
            FacManJsonKind ignored = FACMAN_JSON_INVALID;
            if (!facman_parse_value(parser, &ignored)) break;
            envelope->payload = TRUE;
        } else if (g_strcmp0(key, "error") == 0) {
            if (!facman_parse_typed_value(parser, FACMAN_JSON_OBJECT, FACMAN_JSON_NULL)) break;
            envelope->error_member = TRUE;
        } else if (g_strcmp0(key, "diagnostics") == 0 || g_strcmp0(key, "effects") == 0) {
            if (!facman_parse_typed_value(parser, FACMAN_JSON_ARRAY, FACMAN_JSON_ARRAY)) break;
            if (g_strcmp0(key, "diagnostics") == 0) envelope->diagnostics = TRUE;
            else envelope->effects = TRUE;
        } else if (g_strcmp0(key, "operation") == 0) {
            if (!facman_parse_operation(parser, envelope)) break;
            envelope->operation = TRUE;
        } else {
            facman_json_fail(parser, "unexpected transport response member");
        }
        if (parser->error != NULL) break;
        facman_skip_space(parser);
        if (parser->cursor < parser->end && *parser->cursor == '}') continue;
        if (!facman_take(parser, ',')) break;
    }
    g_hash_table_unref(members);
    return FALSE;
}

static void facman_envelope_clear(FacManTransportEnvelope *envelope)
{
    g_free(envelope->schema);
    g_free(envelope->request_id);
    g_free(envelope->command);
    g_free(envelope->outcome);
    g_free(envelope->operation_schema);
    g_free(envelope->operation_id);
    g_free(envelope->attempt_id);
    g_free(envelope->operation_outcome);
}

gchar *facman_gtk_transport_validate(
    const guint8 *stdout_data,
    gsize stdout_size,
    const guint8 *stderr_data,
    gsize stderr_size,
    const FacManGtkTransportExpectation *expectation)
{
    if (expectation == NULL || expectation->request_id == NULL ||
        expectation->operation_id == NULL || expectation->attempt_id == NULL ||
        expectation->command == NULL)
        return g_strdup("frontend_backend_protocol_invalid: missing local correlation identity");
    if (stdout_data == NULL || stdout_size == 0)
        return g_strdup("frontend_backend_protocol_invalid: backend returned no JSON response");
    if (!g_utf8_validate((const gchar *)stdout_data, stdout_size, NULL))
        return g_strdup("frontend_backend_invalid_utf8: stdout is not strict UTF-8");
    if (stderr_size > 0 && (stderr_data == NULL ||
        !g_utf8_validate((const gchar *)stderr_data, stderr_size, NULL)))
        return g_strdup("frontend_backend_invalid_utf8: stderr is not strict UTF-8");

    FacManJsonParser parser = {
        (const gchar *)stdout_data,
        (const gchar *)stdout_data + stdout_size,
        NULL,
        0,
    };
    FacManTransportEnvelope envelope = {0};
    gboolean parsed = facman_parse_envelope(&parser, &envelope);
    facman_skip_space(&parser);
    if (parsed && parser.cursor != parser.end) {
        parsed = FALSE;
        facman_json_fail(&parser, "trailing data after transport response");
    }
    gboolean contract_valid = parsed &&
        g_strcmp0(envelope.schema, "facman.transport_response.v2") == 0 &&
        g_strcmp0(envelope.operation_schema, "ulk.operation_outcome.v1") == 0;
    gboolean correlated = contract_valid &&
        g_strcmp0(envelope.request_id, expectation->request_id) == 0 &&
        g_strcmp0(envelope.operation_id, expectation->operation_id) == 0 &&
        g_strcmp0(envelope.attempt_id, expectation->attempt_id) == 0 &&
        g_strcmp0(envelope.command, expectation->command) == 0;
    gchar *failure = NULL;
    if (!parsed) {
        failure = g_strdup_printf(
            "outcome_unknown: frontend_backend_protocol_invalid: %s",
            parser.error != NULL ? parser.error : "malformed transport response");
    } else if (!contract_valid) {
        failure = g_strdup(
            "outcome_unknown: frontend_backend_protocol_invalid: response schema is not admitted");
    } else if (!correlated) {
        failure = g_strdup(
            "outcome_unknown: frontend_backend_correlation_mismatch: response identity does not "
            "match the dispatched request");
    }
    facman_envelope_clear(&envelope);
    return failure;
}
