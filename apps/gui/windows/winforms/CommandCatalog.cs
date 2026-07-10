using System;
using System.Collections.Generic;

namespace FacMan.WinForms
{
    public static class CommandCatalog
    {
        private const string DeferredReason =
            "Deferred in FACMAN-WINFORMS-SHELL-01. The WinForms shell must render the command state without implementing backend behavior.";

        public static IList<CommandDefinition> All()
        {
            List<CommandDefinition> commands = new List<CommandDefinition>();

            commands.Add(Implemented(
                "help",
                "Dashboard",
                "Help",
                "app.help",
                "Render the shared CLI help text.",
                NoInputs(),
                delegate { return Args("--help"); }));
            commands.Add(Implemented(
                "version",
                "Dashboard",
                "Version",
                "app.version",
                "Render the backend version.",
                NoInputs(),
                delegate { return Args("--version"); }));
            commands.Add(Implemented(
                "doctor",
                "Doctor",
                "Doctor",
                "doctor.run",
                "Run workspace checks through the shared backend.",
                NoInputs(),
                delegate { return Args("doctor", "--json"); }));
            commands.Add(Implemented(
                "product.inspect",
                "Dashboard",
                "Product Inspect",
                "product.inspect",
                "Inspect the FacMan product binding.",
                NoInputs(),
                delegate { return Args("product", "inspect", "--json"); }));
            commands.Add(Implemented(
                "command_graph.inspect",
                "Dashboard",
                "Command Graph",
                "command_graph.inspect",
                "Inspect the shared command graph.",
                NoInputs(),
                delegate { return Args("command-graph", "inspect", "--json"); }));
            commands.Add(Implemented(
                "installs.scan",
                "Installs",
                "Scan Installs",
                "installs.scan",
                "Ask the backend to scan for local install candidates.",
                Inputs(Optional("scanPath", "Scan root")),
                delegate(IDictionary<string, string> inputs)
                {
                    List<string> args = Args("installs", "scan", "--json");
                    AddOptional(args, inputs, "scanPath", "--path");
                    return args;
                }));
            commands.Add(Implemented(
                "installs.import",
                "Installs",
                "Import Install",
                "installs.import",
                "Register an existing local install reference through the backend.",
                Inputs(Required("installPath", "Install path"), Required("installId", "Install id")),
                delegate(IDictionary<string, string> inputs)
                {
                    return Args("installs", "import", Require(inputs, "installPath"), "--id", Require(inputs, "installId"), "--json");
                }));
            commands.Add(Implemented(
                "installs.inspect",
                "Installs",
                "Inspect Install",
                "installs.inspect",
                "Inspect a registered install reference.",
                Inputs(Required("installId", "Install id")),
                delegate(IDictionary<string, string> inputs)
                {
                    return Args("installs", "inspect", Require(inputs, "installId"), "--json");
                }));
            commands.Add(Implemented(
                "instances.list",
                "Instances",
                "List Instances",
                "instance.list",
                "List isolated instances from the backend workspace.",
                NoInputs(),
                delegate { return Args("instances", "list", "--json"); }));
            commands.Add(Implemented(
                "instances.create",
                "Instances",
                "Create Instance",
                "instances.create",
                "Create an isolated instance through the backend.",
                Inputs(Required("instanceName", "Instance name"), Required("installId", "Install id"), Optional("templateId", "Template id")),
                delegate(IDictionary<string, string> inputs)
                {
                    List<string> args = Args("instances", "create", Require(inputs, "instanceName"), "--install", Require(inputs, "installId"), "--json");
                    AddOptional(args, inputs, "templateId", "--template");
                    return args;
                }));
            commands.Add(Implemented(
                "launch_plan.build",
                "Launch Plan",
                "Build Launch Plan",
                "launch_plan.build",
                "Build a dry-run launch plan through the backend.",
                Inputs(Required("instanceId", "Instance id")),
                delegate(IDictionary<string, string> inputs)
                {
                    return Args("launch-plan", Require(inputs, "instanceId"), "--json");
                }));
            commands.Add(Implemented(
                "launch_plan.preflight",
                "Launch Plan",
                "Preflight Launch",
                "launch_plan.preflight",
                "Validate the routed launch plan without starting a process.",
                Inputs(Required("instanceId", "Instance id")),
                delegate(IDictionary<string, string> inputs)
                {
                    return Args("launch-plan", Require(inputs, "instanceId"), "--preflight", "--json");
                }));
            commands.Add(Implemented(
                "run.preview",
                "Launch Plan",
                "Run Preview",
                "run.preview",
                "Preview run arguments without launching Factorio.",
                Inputs(Required("instanceId", "Instance id")),
                delegate(IDictionary<string, string> inputs)
                {
                    return Args("run", Require(inputs, "instanceId"), "--json");
                }));
            commands.Add(Implemented(
                "diagnostics.export",
                "Diagnostics",
                "Export Diagnostics",
                "diagnostics.run",
                "Export a diagnostics report from the shared backend.",
                NoInputs(),
                delegate { return Args("diagnostics", "report", "--json"); }));

            commands.Add(Deferred("run.execute", "Launch Plan", "Execute Run", "run.execute"));
            commands.Add(Deferred("modsets.lock", "Diagnostics", "Lock Modset", "modsets.lock"));
            commands.Add(Deferred("saves.backup", "Diagnostics", "Backup Save", "saves.backup"));
            commands.Add(Deferred("export.instance", "Diagnostics", "Export Instance", "export.instance"));
            commands.Add(Deferred("import.instance", "Diagnostics", "Import Instance", "import.instance"));
            commands.Add(Deferred("setup.preview", "Installs", "Setup Preview", "install_local.plan"));

            return commands.AsReadOnly();
        }

        public static CommandDefinition Find(string commandId)
        {
            foreach (CommandDefinition command in All())
            {
                if (String.Equals(command.Id, commandId, StringComparison.Ordinal))
                {
                    return command;
                }
            }
            throw new CommandValidationException("Unknown command id: " + commandId);
        }

        private static CommandDefinition Implemented(
            string id,
            string screen,
            string label,
            string backendId,
            string description,
            IEnumerable<CommandInput> inputs,
            CommandArgumentBuilder argumentBuilder)
        {
            return new CommandDefinition(
                id,
                screen,
                label,
                backendId,
                CommandStatus.Implemented,
                description,
                String.Empty,
                inputs,
                argumentBuilder);
        }

        private static CommandDefinition Deferred(string id, string screen, string label, string backendId)
        {
            return new CommandDefinition(
                id,
                screen,
                label,
                backendId,
                CommandStatus.NotSupportedWithReason,
                "Deferred command.",
                DeferredReason,
                NoInputs(),
                delegate { return Args(); });
        }

        private static IList<CommandInput> NoInputs()
        {
            return new List<CommandInput>().AsReadOnly();
        }

        private static IList<CommandInput> Inputs(params CommandInput[] inputs)
        {
            return new List<CommandInput>(inputs).AsReadOnly();
        }

        private static CommandInput Required(string key, string label)
        {
            return new CommandInput(key, label, true);
        }

        private static CommandInput Optional(string key, string label)
        {
            return new CommandInput(key, label, false);
        }

        private static List<string> Args(params string[] args)
        {
            return new List<string>(args);
        }

        private static string Require(IDictionary<string, string> inputs, string key)
        {
            string value;
            if (!inputs.TryGetValue(key, out value) || String.IsNullOrWhiteSpace(value))
            {
                throw new CommandValidationException("Missing required input: " + key);
            }
            return value.Trim();
        }

        private static void AddOptional(List<string> args, IDictionary<string, string> inputs, string key, string flag)
        {
            string value;
            if (inputs.TryGetValue(key, out value) && !String.IsNullOrWhiteSpace(value))
            {
                args.Add(flag);
                args.Add(value.Trim());
            }
        }
    }
}
