// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using System.Web.Script.Serialization;

namespace FacMan.WinForms
{
    public sealed class CliProcessClient
    {
        private const int TimeoutMilliseconds = 30000;
        private const int MaximumStdoutCharacters = 16 * 1024 * 1024;
        private const int MaximumStderrCharacters = 64 * 1024;

        public async Task<CommandResult> InvokeAsync(
            CommandDefinition command,
            IDictionary<string, object> payload,
            string workspace,
            string configuredCliPath,
            CancellationToken cancellationToken)
        {
            string operationId = "op-" + Guid.NewGuid().ToString("N");
            string attemptId = "attempt-" + Guid.NewGuid().ToString("N");
            if (cancellationToken.IsCancellationRequested)
            {
                return new CommandResult(
                    command.Id,
                    command.BackendId,
                    1,
                    String.Empty,
                    String.Empty,
                    true,
                    "frontend_backend_cancelled",
                    "The backend command was cancelled before dispatch.",
                    "cancelled",
                    operationId,
                    attemptId,
                    "cancelled_before_dispatch");
            }
            string executable = ResolveExecutable(configuredCliPath);
            if (String.IsNullOrWhiteSpace(executable))
            {
                return CommandResult.Refusal(
                    command.Id,
                    command.BackendId,
                    "frontend_backend_unavailable",
                    "No facman CLI executable is configured, colocated with the WinForms app, or available through FACMAN_CLI.");
            }

            try
            {
                ProcessStartInfo startInfo = CreateStartInfo(executable);
                using (Process process = new Process())
                {
                    process.StartInfo = startInfo;
                    process.Start();
                    JavaScriptSerializer serializer = new JavaScriptSerializer();
                    Dictionary<string, object> request = new Dictionary<string, object>();
                    request["schema"] = "facman.transport_request.v2";
                    request["protocol_version"] = 2;
                    request["request_id"] = attemptId;
                    request["operation_id"] = operationId;
                    request["attempt_id"] = attemptId;
                    request["workspace"] = String.IsNullOrWhiteSpace(workspace) ? String.Empty : workspace.Trim();
                    request["command"] = command.BackendId;
                    request["dry_run"] = command.DryRunDefault;
                    request["payload"] = payload ?? new Dictionary<string, object>();
                    byte[] requestBytes = new UTF8Encoding(false).GetBytes(serializer.Serialize(request));
                    Stream standardInput = process.StandardInput.BaseStream;
                    await standardInput.WriteAsync(
                        requestBytes, 0, requestBytes.Length, CancellationToken.None).ConfigureAwait(false);
                    standardInput.Close();
                    Task<string> stdoutTask = ReadBoundedAsync(process.StandardOutput, MaximumStdoutCharacters);
                    Task<string> stderrTask = ReadBoundedAsync(process.StandardError, MaximumStderrCharacters);
                    Task exitTask = Task.Run(delegate { process.WaitForExit(); });
                    Task timeoutTask = Task.Delay(TimeoutMilliseconds, cancellationToken);
                    Task completed = await Task.WhenAny(exitTask, timeoutTask).ConfigureAwait(false);
                    if (completed != exitTask)
                    {
                        if (process.HasExited)
                        {
                            await exitTask.ConfigureAwait(false);
                            string completedStdout = await stdoutTask.ConfigureAwait(false);
                            string completedStderr = await stderrTask.ConfigureAwait(false);
                            return DecodeResult(
                                command,
                                process.ExitCode,
                                completedStdout,
                                completedStderr,
                                operationId,
                                attemptId)
                                .CancellationRequestedButCompleted();
                        }
                        Terminate(process);
                        await exitTask.ConfigureAwait(false);
                        await Task.WhenAll(stdoutTask, stderrTask).ConfigureAwait(false);
                        string code = cancellationToken.IsCancellationRequested
                            ? "frontend_backend_cancelled"
                            : "frontend_backend_timeout";
                        string reason = cancellationToken.IsCancellationRequested
                            ? "The backend command was cancelled."
                            : "The backend command did not finish within the WinForms command timeout.";
                        return CommandResult.OutcomeUnknown(
                            command.Id,
                            command.BackendId,
                            operationId,
                            attemptId,
                            code,
                            reason + " Its effects are unknown; inspect workspace recovery.");
                    }
                    string stdout = await stdoutTask.ConfigureAwait(false);
                    string stderr = await stderrTask.ConfigureAwait(false);
                    return DecodeResult(
                        command, process.ExitCode, stdout, stderr, operationId, attemptId);
                }
            }
            catch (OperationCanceledException)
            {
                return CommandResult.Refusal(
                    command.Id, command.BackendId, "frontend_backend_cancelled", "The backend command was cancelled.");
            }
            catch (Exception ex)
            {
                return CommandResult.Refusal(command.Id, command.BackendId, "frontend_backend_error", ex.Message);
            }
        }

        private static Task<string> ReadBoundedAsync(StreamReader reader, int maximumCharacters)
        {
            return Task.Run(delegate
            {
                StringBuilder output = new StringBuilder();
                char[] buffer = new char[4096];
                bool exceeded = false;
                int count;
                while ((count = reader.Read(buffer, 0, buffer.Length)) > 0)
                {
                    int remaining = maximumCharacters - output.Length;
                    if (remaining > 0) output.Append(buffer, 0, Math.Min(count, remaining));
                    if (count > remaining) exceeded = true;
                }
                if (exceeded) throw new InvalidDataException("Backend process output exceeded its configured budget.");
                return output.ToString();
            });
        }

        private static ProcessStartInfo CreateStartInfo(string executable)
        {
            ProcessStartInfo startInfo = new ProcessStartInfo();
            startInfo.FileName = executable;
            startInfo.UseShellExecute = false;
            startInfo.RedirectStandardOutput = true;
            startInfo.RedirectStandardError = true;
            startInfo.RedirectStandardInput = true;
            startInfo.CreateNoWindow = true;
            startInfo.StandardOutputEncoding = Encoding.UTF8;
            startInfo.StandardErrorEncoding = Encoding.UTF8;
            startInfo.Arguments = "rpc --stdio";
            return startInfo;
        }

        private static CommandResult DecodeResult(
            CommandDefinition command,
            int exitCode,
            string stdout,
            string stderr,
            string requestOperationId,
            string requestAttemptId)
        {
            string trimmed = (stdout ?? String.Empty).Trim();
            if (!trimmed.StartsWith("{", StringComparison.Ordinal))
            {
                return new CommandResult(
                    command.Id, command.BackendId, exitCode, stdout, stderr, false, String.Empty, String.Empty);
            }
            try
            {
                JavaScriptSerializer serializer = new JavaScriptSerializer();
                Dictionary<string, object> envelope = serializer.DeserializeObject(trimmed) as Dictionary<string, object>;
                Dictionary<string, object> refusal = Member(envelope, "refusal");
                Dictionary<string, object> error = Member(envelope, "error");
                Dictionary<string, object> operation = Member(envelope, "operation");
                Dictionary<string, object> recovery = Member(operation, "recovery");
                Dictionary<string, object> detail = refusal ?? error;
                bool refused = exitCode != 0 || Text(envelope, "outcome") != "ok" || detail != null;
                return new CommandResult(
                    command.Id,
                    command.BackendId,
                    exitCode,
                    stdout,
                    stderr,
                    refused,
                    Text(detail, "code"),
                    Text(detail, detail == refusal ? "reason" : "message"),
                    Text(envelope, "outcome"),
                    TextOr(operation, "operation_id", requestOperationId),
                    TextOr(operation, "attempt_id", requestAttemptId),
                    Text(operation, "outcome"),
                    Boolean(operation, "effects_may_have_occurred"),
                    Boolean(recovery, "required"),
                    Text(recovery, "transaction_id"),
                    Text(recovery, "inspect_command"));
            }
            catch (Exception ex)
            {
                return CommandResult.Refusal(
                    command.Id,
                    command.BackendId,
                    "frontend_backend_response_invalid",
                    "The CLI returned invalid structured JSON: " + ex.Message);
            }
        }

        private static Dictionary<string, object> Member(Dictionary<string, object> value, string key)
        {
            object member;
            return value != null && value.TryGetValue(key, out member)
                ? member as Dictionary<string, object>
                : null;
        }

        private static string Text(Dictionary<string, object> value, string key)
        {
            object member;
            return value != null && value.TryGetValue(key, out member) && member != null
                ? Convert.ToString(member)
                : String.Empty;
        }

        private static string TextOr(
            Dictionary<string, object> value, string key, string fallback)
        {
            string member = Text(value, key);
            return String.IsNullOrWhiteSpace(member) ? fallback : member;
        }

        private static bool Boolean(Dictionary<string, object> value, string key)
        {
            object member;
            return value != null && value.TryGetValue(key, out member) &&
                member is bool && (bool)member;
        }

        private static void Terminate(Process process)
        {
            try
            {
                if (!process.HasExited) process.Kill();
            }
            catch (InvalidOperationException)
            {
            }
        }

        private static string ResolveExecutable(string configuredCliPath)
        {
            if (!String.IsNullOrWhiteSpace(configuredCliPath) && File.Exists(configuredCliPath.Trim()))
                return configuredCliPath.Trim();
            string envPath = Environment.GetEnvironmentVariable("FACMAN_CLI");
            if (!String.IsNullOrWhiteSpace(envPath) && File.Exists(envPath.Trim())) return envPath.Trim();
            string baseDirectory = AppDomain.CurrentDomain.BaseDirectory;
            string colocatedExe = Path.Combine(baseDirectory, "facman.exe");
            if (File.Exists(colocatedExe)) return colocatedExe;
            string colocated = Path.Combine(baseDirectory, "facman");
            if (File.Exists(colocated)) return colocated;
            return "facman";
        }

    }
}
