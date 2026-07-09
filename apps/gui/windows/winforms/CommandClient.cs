using System;
using System.Collections.Generic;

namespace FacMan.WinForms
{
    public sealed class CommandClient
    {
        private readonly JsonRpcClient transport;

        public CommandClient()
            : this(new JsonRpcClient())
        {
        }

        public CommandClient(JsonRpcClient transport)
        {
            if (transport == null)
            {
                throw new ArgumentNullException("transport");
            }
            this.transport = transport;
        }

        public CommandResult Execute(
            CommandDefinition command,
            IDictionary<string, string> inputs,
            string workspace,
            string configuredCliPath)
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
                return CommandResult.Refusal(
                    command.Id,
                    command.BackendId,
                    "winforms_command_deferred",
                    command.DeferredReason);
            }

            try
            {
                IList<string> arguments = command.ArgumentBuilder(inputs);
                return transport.Invoke(command, arguments, workspace, configuredCliPath);
            }
            catch (CommandValidationException ex)
            {
                return CommandResult.Refusal(
                    command.Id,
                    command.BackendId,
                    "winforms_input_required",
                    ex.Message);
            }
        }
    }
}
