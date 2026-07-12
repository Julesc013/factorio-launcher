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
            string defaultValue)
        {
            Key = key;
            Label = label;
            Required = required;
            Type = type;
            Repeatable = repeatable;
            RequestField = requestField;
            DefaultValue = defaultValue;
        }

        public string Key { get; private set; }
        public string Label { get; private set; }
        public bool Required { get; private set; }
        public string Type { get; private set; }
        public bool Repeatable { get; private set; }
        public string RequestField { get; private set; }
        public string DefaultValue { get; private set; }
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
        public IList<string> Effects { get; private set; }
        public IList<CommandInput> Inputs { get; private set; }
        public string PositionalsJson { get; private set; }
        public string OptionsJson { get; private set; }
        public string Renderer { get; private set; }
    }

    public sealed class CommandResult
    {
        public CommandResult(
            string commandId,
            string backendId,
            int exitCode,
            string stdout,
            string stderr,
            bool refused,
            string refusalCode,
            string refusalReason,
            string outcome = null)
        {
            CommandId = commandId;
            BackendId = backendId;
            ExitCode = exitCode;
            Stdout = stdout ?? String.Empty;
            Stderr = stderr ?? String.Empty;
            Refused = refused;
            RefusalCode = refusalCode ?? String.Empty;
            RefusalReason = refusalReason ?? String.Empty;
            Outcome = String.IsNullOrWhiteSpace(outcome) ? (refused ? "refused" : "ok") : outcome;
            CompletedAt = DateTime.Now;
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
        public DateTime CompletedAt { get; private set; }

        public bool Success
        {
            get { return ExitCode == 0 && !Refused; }
        }

        public static CommandResult Refusal(
            string commandId,
            string backendId,
            string refusalCode,
            string refusalReason)
        {
            return new CommandResult(
                commandId,
                backendId,
                1,
                StructuredRefusalJson(commandId, backendId, refusalCode, refusalReason),
                String.Empty,
                true,
                refusalCode,
                refusalReason);
        }

        public string ToDisplayText()
        {
            StringBuilder builder = new StringBuilder();
            builder.AppendLine("Command: " + CommandId);
            builder.AppendLine("Backend: " + BackendId);
            builder.AppendLine("Exit code: " + ExitCode.ToString());
            builder.AppendLine("Outcome: " + Outcome);
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
