// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

using System;
using System.Collections.Generic;
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
                IList<string> arguments = command.ArgumentBuilder(inputs);
                return transport.InvokeAsync(command, arguments, workspace, configuredCliPath, cancellationToken);
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
    }
}
