// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

using System;
using System.Collections.Generic;
using System.Threading;

namespace FacMan.WinForms.Probe
{
    internal static class Program
    {
        private static int Main(string[] args)
        {
            if (args.Length != 2) return 2;
            string workspace = args[0];
            string cli = args[1];
            FacMan.WinForms.CommandClient client = new FacMan.WinForms.CommandClient();
            IList<Tuple<string, Dictionary<string, string>>> commands =
                new List<Tuple<string, Dictionary<string, string>>>
                {
                    Item("workspace.status"),
                    Item("instances.inspect", "instance_id", "restored"),
                    Item("profiles.inspect", "profile_id", "lifecycle"),
                    Item("mods.list"),
                    Item("modsets.verify", "instance_id", "restored"),
                    Item("saves.index", "instance_id", "restored"),
                    Item("snapshots.list", "instance_id", "journey"),
                    Item("servers.plan", "server_id", "lifecycle", "save", "starter"),
                    Item("workspace.recovery.inspect"),
                };
            foreach (Tuple<string, Dictionary<string, string>> item in commands)
            {
                FacMan.WinForms.CommandDefinition command = FacMan.WinForms.CommandCatalog.Find(item.Item1);
                FacMan.WinForms.CommandResult result = client.ExecuteAsync(
                    command, item.Item2, workspace, cli, CancellationToken.None).GetAwaiter().GetResult();
                if (!result.Success)
                {
                    Console.Error.WriteLine(result.ToDisplayText());
                    return 1;
                }
                Console.WriteLine(item.Item1 + ": PASS");
            }
            return 0;
        }

        private static Tuple<string, Dictionary<string, string>> Item(string command, params string[] values)
        {
            Dictionary<string, string> inputs = new Dictionary<string, string>();
            for (int index = 0; index + 1 < values.Length; index += 2) inputs[values[index]] = values[index + 1];
            return Tuple.Create(command, inputs);
        }
    }
}
