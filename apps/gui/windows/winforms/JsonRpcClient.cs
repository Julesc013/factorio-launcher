using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Text;

namespace FacMan.WinForms
{
    public sealed class JsonRpcClient
    {
        private const int TimeoutMilliseconds = 30000;

        public CommandResult Invoke(
            CommandDefinition command,
            IList<string> arguments,
            string workspace,
            string configuredCliPath)
        {
            string executable = ResolveExecutable(configuredCliPath);
            if (String.IsNullOrWhiteSpace(executable))
            {
                return CommandResult.Refusal(
                    command.Id,
                    command.BackendId,
                    "frontend_backend_unavailable",
                    "No facman CLI executable is configured, colocated with the WinForms app, or available through FACMAN_CLI.");
            }

            List<string> fullArguments = new List<string>();
            if (!String.IsNullOrWhiteSpace(workspace))
            {
                fullArguments.Add("--workspace");
                fullArguments.Add(workspace.Trim());
            }
            foreach (string argument in arguments)
            {
                fullArguments.Add(argument);
            }

            try
            {
                ProcessStartInfo startInfo = new ProcessStartInfo();
                startInfo.FileName = executable;
                startInfo.Arguments = JoinArguments(fullArguments);
                startInfo.UseShellExecute = false;
                startInfo.RedirectStandardOutput = true;
                startInfo.RedirectStandardError = true;
                startInfo.CreateNoWindow = true;
                startInfo.StandardOutputEncoding = Encoding.UTF8;
                startInfo.StandardErrorEncoding = Encoding.UTF8;

                Process process = new Process();
                process.StartInfo = startInfo;
                process.Start();
                string stdout = process.StandardOutput.ReadToEnd();
                string stderr = process.StandardError.ReadToEnd();
                if (!process.WaitForExit(TimeoutMilliseconds))
                {
                    process.Kill();
                    return CommandResult.Refusal(
                        command.Id,
                        command.BackendId,
                        "frontend_backend_timeout",
                        "The backend command did not finish within the WinForms command timeout.");
                }
                return new CommandResult(
                    command.Id,
                    command.BackendId,
                    process.ExitCode,
                    stdout,
                    stderr,
                    false,
                    String.Empty,
                    String.Empty);
            }
            catch (Exception ex)
            {
                return CommandResult.Refusal(
                    command.Id,
                    command.BackendId,
                    "frontend_backend_error",
                    ex.Message);
            }
        }

        private static string ResolveExecutable(string configuredCliPath)
        {
            if (!String.IsNullOrWhiteSpace(configuredCliPath) && File.Exists(configuredCliPath.Trim()))
            {
                return configuredCliPath.Trim();
            }

            string envPath = Environment.GetEnvironmentVariable("FACMAN_CLI");
            if (!String.IsNullOrWhiteSpace(envPath) && File.Exists(envPath.Trim()))
            {
                return envPath.Trim();
            }

            string baseDirectory = AppDomain.CurrentDomain.BaseDirectory;
            string colocatedExe = Path.Combine(baseDirectory, "facman.exe");
            if (File.Exists(colocatedExe))
            {
                return colocatedExe;
            }

            string colocated = Path.Combine(baseDirectory, "facman");
            if (File.Exists(colocated))
            {
                return colocated;
            }

            return "facman";
        }

        private static string JoinArguments(IEnumerable<string> arguments)
        {
            StringBuilder builder = new StringBuilder();
            foreach (string argument in arguments)
            {
                if (builder.Length > 0)
                {
                    builder.Append(' ');
                }
                builder.Append(QuoteArgument(argument));
            }
            return builder.ToString();
        }

        private static string QuoteArgument(string argument)
        {
            if (argument == null)
            {
                return "\"\"";
            }
            if (argument.Length == 0)
            {
                return "\"\"";
            }
            if (argument.IndexOfAny(new[] { ' ', '\t', '\r', '\n', '"' }) < 0)
            {
                return argument;
            }
            return "\"" + argument.Replace("\\", "\\\\").Replace("\"", "\\\"") + "\"";
        }
    }
}
