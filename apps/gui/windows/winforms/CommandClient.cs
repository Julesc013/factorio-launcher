// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

using System;
using System.Collections.Generic;
using System.Text;
using System.Threading;
using System.Threading.Tasks;

namespace FacMan.WinForms
{
    public sealed class CommandClient
    {
        private readonly CliProcessClient transport;

        public CommandClient()
            : this(new CliProcessClient())
        {
        }

        public CommandClient(CliProcessClient transport)
        {
            if (transport == null)
            {
                throw new ArgumentNullException("transport");
            }
            this.transport = transport;
        }

        public Task<CommandResult> ExecuteAsync(
            CommandDefinition command,
            IDictionary<string, string> inputs,
            string workspace,
            string configuredCliPath,
            CancellationToken cancellationToken)
        {
            if (command == null)
            {
                throw new ArgumentNullException("command");
            }
            if (inputs == null)
            {
                inputs = new Dictionary<string, string>();
            }

            if (command.Status != CommandStatus.Implemented)
            {
                return Task.FromResult(CommandResult.Refusal(
                    command.Id,
                    command.BackendId,
                    "winforms_command_deferred",
                    command.DeferredReason));
            }

            try
            {
                command.ArgumentBuilder(inputs);
                return transport.InvokeAsync(command, BuildPayload(command, inputs), workspace, configuredCliPath, cancellationToken);
            }
            catch (CommandValidationException ex)
            {
                return Task.FromResult(CommandResult.Refusal(
                    command.Id,
                    command.BackendId,
                    "winforms_input_required",
                    ex.Message));
            }
        }

        private static IDictionary<string, object> BuildPayload(
            CommandDefinition command,
            IDictionary<string, string> inputs)
        {
            Dictionary<string, object> payload = new Dictionary<string, object>();
            string value;
            if (command.Id == "installs.scan")
            {
                List<string> roots = new List<string>();
                if (inputs.TryGetValue("scanPath", out value) && !String.IsNullOrWhiteSpace(value)) roots.Add(value.Trim());
                payload["roots"] = roots;
            }
            else if (command.Id == "installs.import")
            {
                payload["path"] = inputs["installPath"].Trim();
                payload["install_id"] = inputs["installId"].Trim();
            }
            else if (command.Id == "installs.inspect") payload["install_id"] = inputs["installId"].Trim();
            else if (command.Id == "instances.create")
            {
                string name = inputs["instanceName"].Trim();
                payload["display_name"] = name;
                payload["instance_id"] = Slugify(name);
                payload["install_id"] = inputs["installId"].Trim();
                if (inputs.TryGetValue("templateId", out value) && !String.IsNullOrWhiteSpace(value)) payload["template_id"] = value.Trim();
            }
            else if (command.Id == "launch_plan.build" || command.Id == "launch_plan.preflight" || command.Id == "run.preview")
                payload["instance_id"] = inputs["instanceId"].Trim();
            return payload;
        }

        private static string Slugify(string value)
        {
            StringBuilder output = new StringBuilder();
            bool separator = false;
            foreach (char character in value.ToLowerInvariant())
            {
                if (Char.IsLetterOrDigit(character)) { output.Append(character); separator = false; }
                else if (output.Length > 0 && !separator) { output.Append('-'); separator = true; }
            }
            return output.ToString().Trim('-');
        }
    }
}
