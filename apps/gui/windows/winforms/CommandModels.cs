// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

using System;
using System.Collections.Generic;
using System.Text;

namespace FacMan.WinForms
{
    public enum CommandStatus
    {
        Implemented,
        StubbedWithRefusal,
        NotSupportedWithReason
    }

    public sealed class CommandInput
    {
        public CommandInput(
            string key,
            string label,
            bool required,
            string type,
            bool repeatable,
            string requestField,
            string defaultValue,
            IEnumerable<string> choices)
        {
            Key = key;
            Label = label;
            Required = required;
            Type = type;
            Repeatable = repeatable;
            RequestField = requestField;
            DefaultValue = defaultValue;
            Choices = new List<string>(choices ?? new string[0]).AsReadOnly();
        }

        public string Key { get; private set; }
        public string Label { get; private set; }
        public bool Required { get; private set; }
        public string Type { get; private set; }
        public bool Repeatable { get; private set; }
        public string RequestField { get; private set; }
        public string DefaultValue { get; private set; }
        public IList<string> Choices { get; private set; }
    }

    public delegate IList<string> CommandArgumentBuilder(IDictionary<string, string> inputs);

    public sealed class CommandDefinition
    {
        public CommandDefinition(
            string id,
            string screen,
            string label,
            string backendId,
            CommandStatus status,
            string description,
            string deferredReason,
            string labelKey,
            string descriptionKey,
            string availability,
            string riskTier,
            bool dryRunDefault,
            IEnumerable<string> effects,
            IEnumerable<CommandInput> inputs,
            string positionalsJson,
            string optionsJson,
            string renderer)
        {
            Id = id;
            Screen = screen;
            Label = label;
            BackendId = backendId;
            Status = status;
            Description = description;
            DeferredReason = deferredReason;
            LabelKey = labelKey;
            DescriptionKey = descriptionKey;
            Availability = availability;
            RiskTier = riskTier;
            DryRunDefault = dryRunDefault;
            Effects = new List<string>(effects).AsReadOnly();
            Inputs = new List<CommandInput>(inputs).AsReadOnly();
            PositionalsJson = positionalsJson;
            OptionsJson = optionsJson;
            Renderer = renderer;
        }

        public string Id { get; private set; }
        public string Screen { get; private set; }
        public string Label { get; private set; }
        public string BackendId { get; private set; }
        public CommandStatus Status { get; private set; }
        public string Description { get; private set; }
        public string DeferredReason { get; private set; }
        public string LabelKey { get; private set; }
        public string DescriptionKey { get; private set; }
        public string Availability { get; private set; }
        public string RiskTier { get; private set; }
        public bool DryRunDefault { get; private set; }
        public IList<string> Effects { get; private set; }
        public IList<CommandInput> Inputs { get; private set; }
        public string PositionalsJson { get; private set; }
        public string OptionsJson { get; private set; }
        public string Renderer { get; private set; }
    }

    public sealed class CommandResult
    {
        private CommandResult(
            string commandId,
            string backendId,
            int exitCode,
            string stdout,
            string stderr,
            bool refused,
            string refusalCode,
            string refusalReason,
            string outcome = null,
            string operationId = null,
            string attemptId = null,
            string operationOutcome = null,
            bool effectsMayHaveOccurred = false,
            bool recoveryRequired = false,
            string recoveryTransactionId = null,
            string recoveryInspectCommand = null)
        {
            CommandId = commandId;
            BackendId = backendId;
            ExitCode = exitCode;
            Stdout = stdout ?? String.Empty;
            Stderr = stderr ?? String.Empty;
            Refused = refused;
            RefusalCode = refusalCode ?? String.Empty;
            RefusalReason = refusalReason ?? String.Empty;
            Outcome = outcome ?? String.Empty;
            OperationId = operationId ?? String.Empty;
            AttemptId = attemptId ?? String.Empty;
            OperationOutcome = operationOutcome ?? String.Empty;
            EffectsMayHaveOccurred = effectsMayHaveOccurred;
            RecoveryRequired = recoveryRequired;
            RecoveryTransactionId = recoveryTransactionId ?? String.Empty;
            RecoveryInspectCommand = recoveryInspectCommand ?? String.Empty;
            CompletedAt = DateTime.UtcNow;
        }

        public string CommandId { get; private set; }
        public string BackendId { get; private set; }
        public int ExitCode { get; private set; }
        public string Stdout { get; private set; }
        public string Stderr { get; private set; }
        public bool Refused { get; private set; }
        public string RefusalCode { get; private set; }
        public string RefusalReason { get; private set; }
        public string Outcome { get; private set; }
        public string OperationId { get; private set; }
        public string AttemptId { get; private set; }
        public string OperationOutcome { get; private set; }
        public bool EffectsMayHaveOccurred { get; private set; }
        public bool RecoveryRequired { get; private set; }
        public string RecoveryTransactionId { get; private set; }
        public string RecoveryInspectCommand { get; private set; }
        public DateTime CompletedAt { get; private set; }

        public bool Success
        {
            get
            {
                return ExitCode == 0 && !Refused && Outcome == "ok" &&
                    (OperationOutcome == "completed" ||
                    OperationOutcome == "cancellation_requested_but_completed");
            }
        }

        public static CommandResult Refusal(
            string commandId,
            string backendId,
            string refusalCode,
            string refusalReason)
        {
            return LocalRefusal(
                commandId,
                backendId,
                refusalCode,
                refusalReason,
                String.Empty,
                String.Empty);
        }

        internal static CommandResult LocalRefusal(
            string commandId,
            string backendId,
            string refusalCode,
            string refusalReason,
            string operationId,
            string attemptId)
        {
            return new CommandResult(
                commandId,
                backendId,
                1,
                StructuredRefusalJson(commandId, backendId, refusalCode, refusalReason),
                String.Empty,
                true,
                refusalCode,
                refusalReason,
                "refused",
                operationId,
                attemptId,
                "refused_before_effects",
                false,
                false,
                String.Empty,
                String.Empty);
        }

        internal static CommandResult CancelledBeforeDispatch(
            string commandId,
            string backendId,
            string operationId,
            string attemptId,
            string reason)
        {
            return new CommandResult(
                commandId,
                backendId,
                1,
                StructuredOperationJson(
                    operationId,
                    attemptId,
                    "cancelled_before_dispatch",
                    false,
                    false,
                    String.Empty,
                    String.Empty),
                String.Empty,
                true,
                "frontend_backend_cancelled",
                reason,
                "cancelled",
                operationId,
                attemptId,
                "cancelled_before_dispatch",
                false,
                false,
                String.Empty,
                String.Empty);
        }

        public static CommandResult OutcomeUnknown(
            string commandId,
            string backendId,
            string operationId,
            string attemptId,
            string errorCode,
            string errorReason,
            string stdout,
            string stderr)
        {
            return new CommandResult(
                commandId,
                backendId,
                1,
                String.IsNullOrEmpty(stdout)
                    ? StructuredOperationJson(
                        operationId,
                        attemptId,
                        "outcome_unknown",
                        true,
                        true,
                        String.Empty,
                        "workspace.recovery.inspect")
                    : stdout,
                stderr,
                true,
                errorCode,
                errorReason,
                "recovery_required",
                operationId,
                attemptId,
                "outcome_unknown",
                true,
                true,
                String.Empty,
                "workspace.recovery.inspect");
        }

        internal static CommandResult ValidatedTerminal(
            string commandId,
            string backendId,
            int exitCode,
            string stdout,
            string stderr,
            bool refused,
            string refusalCode,
            string refusalReason,
            string outcome,
            string operationId,
            string attemptId,
            string operationOutcome,
            bool effectsMayHaveOccurred,
            bool recoveryRequired,
            string recoveryTransactionId,
            string recoveryInspectCommand)
        {
            return new CommandResult(
                commandId,
                backendId,
                exitCode,
                stdout,
                stderr,
                refused,
                refusalCode,
                refusalReason,
                outcome,
                operationId,
                attemptId,
                operationOutcome,
                effectsMayHaveOccurred,
                recoveryRequired,
                recoveryTransactionId,
                recoveryInspectCommand);
        }

        public CommandResult CancellationRequestedButCompleted()
        {
            if (OperationOutcome != "completed") return this;
            return new CommandResult(
                CommandId,
                BackendId,
                ExitCode,
                Stdout,
                Stderr,
                Refused,
                RefusalCode,
                RefusalReason,
                Outcome,
                OperationId,
                AttemptId,
                "cancellation_requested_but_completed",
                EffectsMayHaveOccurred,
                false,
                String.Empty,
                String.Empty);
        }

        public string ToDisplayText()
        {
            StringBuilder builder = new StringBuilder();
            builder.AppendLine("Command: " + CommandId);
            builder.AppendLine("Backend: " + BackendId);
            builder.AppendLine("Exit code: " + ExitCode.ToString());
            builder.AppendLine("Outcome: " + Outcome);
            builder.AppendLine("Operation ID: " + OperationId);
            builder.AppendLine("Attempt ID: " + AttemptId);
            builder.AppendLine("Operation outcome: " + OperationOutcome);
            builder.AppendLine("Effects may have occurred: " + EffectsMayHaveOccurred.ToString());
            if (RecoveryRequired)
            {
                builder.AppendLine("Recovery: required");
                builder.AppendLine("Inspect command: " + RecoveryInspectCommand);
            }
            builder.AppendLine("Completed: " + CompletedAt.ToString("u"));
            if (Refused)
            {
                builder.AppendLine("Refusal: " + RefusalCode);
                builder.AppendLine("Reason: " + RefusalReason);
            }
            if (!String.IsNullOrWhiteSpace(Stdout))
            {
                builder.AppendLine();
                builder.AppendLine("stdout:");
                builder.AppendLine(Stdout.TrimEnd());
            }
            if (!String.IsNullOrWhiteSpace(Stderr))
            {
                builder.AppendLine();
                builder.AppendLine("stderr:");
                builder.AppendLine(Stderr.TrimEnd());
            }
            return builder.ToString();
        }

        private static string StructuredRefusalJson(
            string commandId,
            string backendId,
            string refusalCode,
            string refusalReason)
        {
            return "{\r\n" +
                "  \"schema\": \"common.refusal.v1\",\r\n" +
                "  \"operation\": \"" + JsonEscape(commandId) + "\",\r\n" +
                "  \"backend_id\": \"" + JsonEscape(backendId) + "\",\r\n" +
                "  \"code\": \"" + JsonEscape(refusalCode) + "\",\r\n" +
                "  \"reason\": \"" + JsonEscape(refusalReason) + "\",\r\n" +
                "  \"recoverable\": true\r\n" +
                "}";
        }

        private static string StructuredOperationJson(
            string operationId,
            string attemptId,
            string operationOutcome,
            bool effectsMayHaveOccurred,
            bool recoveryRequired,
            string transactionId,
            string inspectCommand)
        {
            return "{\r\n" +
                "  \"schema\": \"ulk.operation_outcome.v1\",\r\n" +
                "  \"operation_id\": \"" + JsonEscape(operationId) + "\",\r\n" +
                "  \"attempt_id\": \"" + JsonEscape(attemptId) + "\",\r\n" +
                "  \"outcome\": \"" + JsonEscape(operationOutcome) + "\",\r\n" +
                "  \"effects_may_have_occurred\": " +
                    (effectsMayHaveOccurred ? "true" : "false") + ",\r\n" +
                "  \"recovery\": {\r\n" +
                "    \"required\": " + (recoveryRequired ? "true" : "false") + ",\r\n" +
                "    \"transaction_id\": \"" + JsonEscape(transactionId) + "\",\r\n" +
                "    \"inspect_command\": \"" + JsonEscape(inspectCommand) + "\"\r\n" +
                "  }\r\n" +
                "}";
        }

        private static string JsonEscape(string value)
        {
            if (value == null)
            {
                return String.Empty;
            }
            return value.Replace("\\", "\\\\").Replace("\"", "\\\"");
        }
    }

    public sealed class CommandValidationException : Exception
    {
        public CommandValidationException(string message)
            : base(message)
        {
        }
    }
}
