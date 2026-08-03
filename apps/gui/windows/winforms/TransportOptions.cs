// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

using System;
using System.Collections.Generic;
using System.Text;
using System.Web.Script.Serialization;

namespace FacMan.WinForms
{
    public sealed class TransportOptions
    {
        public const int DefaultMaximumRequestBytes = 1024 * 1024;
        public const int DefaultMaximumStdoutBytes = 16 * 1024 * 1024;
        public const int DefaultMaximumStderrBytes = 64 * 1024;

        public TransportOptions()
            : this(
                DefaultMaximumRequestBytes,
                DefaultMaximumStdoutBytes,
                DefaultMaximumStderrBytes,
                TimeSpan.FromSeconds(30),
                TimeSpan.FromSeconds(2),
                TimeSpan.FromMilliseconds(150))
        {
        }

        public TransportOptions(
            int maximumRequestBytes,
            int maximumStdoutBytes,
            int maximumStderrBytes,
            TimeSpan operationTimeout,
            TimeSpan cleanupReserve,
            TimeSpan cancellationCompletionGrace)
        {
            if (maximumRequestBytes <= 0) throw new ArgumentOutOfRangeException("maximumRequestBytes");
            if (maximumStdoutBytes <= 0) throw new ArgumentOutOfRangeException("maximumStdoutBytes");
            if (maximumStderrBytes <= 0) throw new ArgumentOutOfRangeException("maximumStderrBytes");
            if (operationTimeout <= TimeSpan.Zero) throw new ArgumentOutOfRangeException("operationTimeout");
            if (cleanupReserve <= TimeSpan.Zero || cleanupReserve >= operationTimeout)
                throw new ArgumentOutOfRangeException("cleanupReserve");
            if (cancellationCompletionGrace < TimeSpan.Zero ||
                cancellationCompletionGrace >= operationTimeout - cleanupReserve)
                throw new ArgumentOutOfRangeException("cancellationCompletionGrace");

            MaximumRequestBytes = maximumRequestBytes;
            MaximumStdoutBytes = maximumStdoutBytes;
            MaximumStderrBytes = maximumStderrBytes;
            OperationTimeout = operationTimeout;
            CleanupReserve = cleanupReserve;
            CancellationCompletionGrace = cancellationCompletionGrace;
        }

        public int MaximumRequestBytes { get; private set; }
        public int MaximumStdoutBytes { get; private set; }
        public int MaximumStderrBytes { get; private set; }
        public TimeSpan OperationTimeout { get; private set; }
        public TimeSpan CleanupReserve { get; private set; }
        public TimeSpan CancellationCompletionGrace { get; private set; }
    }

    internal sealed class TransportIdentity
    {
        internal TransportIdentity(string operationId, string attemptId)
        {
            if (String.IsNullOrWhiteSpace(operationId))
                throw new ArgumentException("Operation identity is required.", "operationId");
            if (String.IsNullOrWhiteSpace(attemptId))
                throw new ArgumentException("Attempt identity is required.", "attemptId");
            OperationId = operationId;
            AttemptId = attemptId;
            RequestId = attemptId;
        }

        internal string OperationId { get; private set; }
        internal string AttemptId { get; private set; }
        internal string RequestId { get; private set; }

        internal static TransportIdentity Create()
        {
            return new TransportIdentity(
                "op-" + Guid.NewGuid().ToString("N"),
                "attempt-" + Guid.NewGuid().ToString("N"));
        }
    }

    internal static class TransportRequestEncoder
    {
        private static readonly UTF8Encoding StrictUtf8 = new UTF8Encoding(false, true);

        internal static byte[] Encode(
            CommandDefinition command,
            IDictionary<string, object> payload,
            string workspace,
            TransportIdentity identity)
        {
            Dictionary<string, object> request = new Dictionary<string, object>();
            request["schema"] = "facman.transport_request.v2";
            request["protocol_version"] = 2;
            request["request_id"] = identity.RequestId;
            request["operation_id"] = identity.OperationId;
            request["attempt_id"] = identity.AttemptId;
            request["workspace"] = String.IsNullOrWhiteSpace(workspace)
                ? String.Empty
                : workspace.Trim();
            request["command"] = command.BackendId;
            request["dry_run"] = command.DryRunDefault;
            request["payload"] = payload ?? new Dictionary<string, object>();
            JavaScriptSerializer serializer = new JavaScriptSerializer();
            serializer.MaxJsonLength = TransportOptions.DefaultMaximumRequestBytes * 2;
            return StrictUtf8.GetBytes(serializer.Serialize(request));
        }
    }

    internal enum TransportDispatchState
    {
        NotStarted,
        ProcessStartedRequestNotWritten,
        RequestWriteStartedDispatchUncertain,
        RequestWrittenResponsePending,
        TerminalResponseValidated,
        TerminationPending,
        Terminated
    }
}
