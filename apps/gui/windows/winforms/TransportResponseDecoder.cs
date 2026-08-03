// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

using System;
using System.Collections.Generic;
using System.IO;
using System.Text;

namespace FacMan.WinForms
{
    internal static class TransportResponseDecoder
    {
        private static readonly UTF8Encoding StrictUtf8 = new UTF8Encoding(false, true);
        private static readonly HashSet<string> EnvelopeOutcomes = Set(
            "ok",
            "refused",
            "invalid_argument",
            "unavailable",
            "not_found",
            "conflict",
            "cancelled",
            "timeout",
            "recovery_required",
            "internal_error");
        private static readonly HashSet<string> OperationOutcomes = Set(
            "cancelled_before_dispatch",
            "refused_before_effects",
            "completed",
            "cancellation_requested_but_completed",
            "recovery_required",
            "outcome_unknown");

        internal static CommandResult Decode(
            CommandDefinition command,
            int exitCode,
            byte[] stdoutBytes,
            byte[] stderrBytes,
            TransportIdentity identity,
            int maximumDecodedCharacters)
        {
            string stdout = DecodeUtf8(stdoutBytes, "standard output");
            string stderr = DecodeUtf8(stderrBytes, "standard error");
            Dictionary<string, object> envelope =
                StrictTransportJson.ParseObject(stdout, maximumDecodedCharacters);
            RequireExactMembers(
                envelope,
                "response envelope",
                "schema",
                "protocol_version",
                "request_id",
                "command",
                "outcome",
                "payload",
                "error",
                "diagnostics",
                "effects",
                "operation");
            RequireText(envelope, "schema", "facman.transport_response.v2");
            RequireInteger(envelope, "protocol_version", 2);
            RequireText(envelope, "request_id", identity.RequestId);
            RequireText(envelope, "command", command.BackendId);
            string envelopeOutcome = RequiredText(envelope, "outcome");
            if (!EnvelopeOutcomes.Contains(envelopeOutcome))
                throw Invalid("Response envelope outcome is unknown.");
            RequireArray(envelope, "diagnostics");
            RequireArray(envelope, "effects");

            Dictionary<string, object> error = OptionalObject(envelope, "error");
            if (error != null)
            {
                RequireExactMembers(error, "response error", "code", "message");
                RequiredText(error, "code");
                RequiredText(error, "message");
            }

            Dictionary<string, object> operation = RequiredObject(envelope, "operation");
            RequireExactMembers(
                operation,
                "operation outcome",
                "schema",
                "operation_id",
                "attempt_id",
                "outcome",
                "effects_may_have_occurred",
                "recovery");
            RequireText(operation, "schema", "ulk.operation_outcome.v1");
            RequireText(operation, "operation_id", identity.OperationId);
            RequireText(operation, "attempt_id", identity.AttemptId);
            string operationOutcome = RequiredText(operation, "outcome");
            if (!OperationOutcomes.Contains(operationOutcome))
                throw Invalid("Operation outcome is unknown.");
            bool effectsMayHaveOccurred = RequiredBoolean(
                operation, "effects_may_have_occurred");
            Dictionary<string, object> recovery = RequiredObject(operation, "recovery");
            RequireExactMembers(
                recovery, "operation recovery", "required", "transaction_id", "inspect_command");
            bool recoveryRequired = RequiredBoolean(recovery, "required");
            string transactionId = RequiredTextAllowEmpty(recovery, "transaction_id");
            string inspectCommand = RequiredTextAllowEmpty(recovery, "inspect_command");
            ValidateIdentifier(identity.OperationId, "operation_id");
            ValidateIdentifier(identity.AttemptId, "attempt_id");
            ValidateRecovery(
                operationOutcome,
                effectsMayHaveOccurred,
                recoveryRequired,
                transactionId,
                inspectCommand);
            ValidateEnvelopeConsistency(envelopeOutcome, exitCode, error, operationOutcome);

            bool refused = envelopeOutcome != "ok";
            return CommandResult.ValidatedTerminal(
                command.Id,
                command.BackendId,
                exitCode,
                stdout,
                stderr,
                refused,
                error == null ? String.Empty : RequiredText(error, "code"),
                error == null ? String.Empty : RequiredText(error, "message"),
                envelopeOutcome,
                identity.OperationId,
                identity.AttemptId,
                operationOutcome,
                effectsMayHaveOccurred,
                recoveryRequired,
                transactionId,
                inspectCommand);
        }

        internal static string DecodeDiagnostic(byte[] bytes)
        {
            try
            {
                return DecodeUtf8(bytes, "diagnostic stream");
            }
            catch (InvalidDataException)
            {
                return String.Empty;
            }
        }

        private static void ValidateEnvelopeConsistency(
            string envelopeOutcome,
            int exitCode,
            Dictionary<string, object> error,
            string operationOutcome)
        {
            bool operationCompleted = operationOutcome == "completed" ||
                operationOutcome == "cancellation_requested_but_completed";
            if (envelopeOutcome == "ok")
            {
                if (exitCode != 0 || error != null || !operationCompleted)
                    throw Invalid("Successful envelope contradicts exit, error, or operation outcome.");
            }
            else if (exitCode == 0 || error == null || operationCompleted)
            {
                throw Invalid("Non-success envelope contradicts exit, error, or operation outcome.");
            }
        }

        private static void ValidateRecovery(
            string outcome,
            bool effects,
            bool required,
            string transactionId,
            string inspectCommand)
        {
            if (!required &&
                (!String.IsNullOrEmpty(transactionId) || !String.IsNullOrEmpty(inspectCommand)))
                throw Invalid("Non-required recovery contains recovery identity or command.");
            if (required && inspectCommand != "workspace.recovery.inspect")
                throw Invalid("Required recovery must use workspace.recovery.inspect.");
            if ((outcome == "cancelled_before_dispatch" || outcome == "refused_before_effects") &&
                (effects || required))
                throw Invalid("Pre-effect operation outcome contradicts effects or recovery.");
            if ((outcome == "completed" || outcome == "cancellation_requested_but_completed") &&
                required)
                throw Invalid("Completed operation cannot require recovery.");
            if ((outcome == "recovery_required" || outcome == "outcome_unknown") &&
                (!effects || !required))
                throw Invalid("Unknown or recovery-required operation must preserve effects and recovery.");
        }

        private static void ValidateIdentifier(string value, string label)
        {
            if (String.IsNullOrEmpty(value) || value.Length > 128 || !IsIdentifierStart(value[0]))
                throw Invalid(label + " is invalid.");
            foreach (char ch in value)
            {
                if (!IsIdentifierStart(ch) && ch != '.' && ch != '_' && ch != ':' && ch != '-')
                    throw Invalid(label + " is invalid.");
            }
        }

        private static bool IsIdentifierStart(char ch)
        {
            return (ch >= 'A' && ch <= 'Z') || (ch >= 'a' && ch <= 'z') ||
                (ch >= '0' && ch <= '9');
        }

        private static string DecodeUtf8(byte[] bytes, string label)
        {
            try
            {
                return StrictUtf8.GetString(bytes ?? new byte[0]);
            }
            catch (DecoderFallbackException ex)
            {
                throw new InvalidDataException("Backend " + label + " is not strict UTF-8.", ex);
            }
        }

        private static Dictionary<string, object> RequiredObject(
            Dictionary<string, object> value, string key)
        {
            object member;
            Dictionary<string, object> result;
            if (!value.TryGetValue(key, out member) ||
                (result = member as Dictionary<string, object>) == null)
                throw Invalid("Response member '" + key + "' must be an object.");
            return result;
        }

        private static Dictionary<string, object> OptionalObject(
            Dictionary<string, object> value, string key)
        {
            object member;
            if (!value.TryGetValue(key, out member))
                throw Invalid("Response member '" + key + "' is missing.");
            if (member == null) return null;
            Dictionary<string, object> result = member as Dictionary<string, object>;
            if (result == null)
                throw Invalid("Response member '" + key + "' must be an object or null.");
            return result;
        }

        private static void RequireArray(Dictionary<string, object> value, string key)
        {
            object member;
            if (!value.TryGetValue(key, out member) || !(member is object[]))
                throw Invalid("Response member '" + key + "' must be an array.");
        }

        private static bool RequiredBoolean(Dictionary<string, object> value, string key)
        {
            object member;
            if (!value.TryGetValue(key, out member) || !(member is bool))
                throw Invalid("Response member '" + key + "' must be a boolean.");
            return (bool)member;
        }

        private static string RequiredText(Dictionary<string, object> value, string key)
        {
            string text = RequiredTextAllowEmpty(value, key);
            if (String.IsNullOrEmpty(text))
                throw Invalid("Response member '" + key + "' must not be empty.");
            return text;
        }

        private static string RequiredTextAllowEmpty(
            Dictionary<string, object> value, string key)
        {
            object member;
            string text;
            if (!value.TryGetValue(key, out member) || (text = member as string) == null)
                throw Invalid("Response member '" + key + "' must be a string.");
            return text;
        }

        private static void RequireText(
            Dictionary<string, object> value, string key, string expected)
        {
            string actual = RequiredText(value, key);
            if (!String.Equals(actual, expected, StringComparison.Ordinal))
                throw Invalid("Response member '" + key + "' does not match the request.");
        }

        private static void RequireInteger(
            Dictionary<string, object> value, string key, int expected)
        {
            object member;
            if (!value.TryGetValue(key, out member) || !(member is int) || (int)member != expected)
                throw Invalid("Response member '" + key + "' must equal " + expected + ".");
        }

        private static void RequireExactMembers(
            Dictionary<string, object> value, string label, params string[] expected)
        {
            HashSet<string> allowed = new HashSet<string>(expected, StringComparer.Ordinal);
            foreach (string key in expected)
            {
                if (!value.ContainsKey(key)) throw Invalid(label + " is missing member '" + key + "'.");
            }
            foreach (string key in value.Keys)
            {
                if (!allowed.Contains(key)) throw Invalid(label + " contains unknown member '" + key + "'.");
            }
        }

        private static InvalidDataException Invalid(string message)
        {
            return new InvalidDataException(message);
        }

        private static HashSet<string> Set(params string[] values)
        {
            return new HashSet<string>(values, StringComparer.Ordinal);
        }
    }
}
