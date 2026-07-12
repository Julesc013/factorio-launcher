// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

using System;

namespace FacMan.WinForms
{
    public static class OperationalVisualization
    {
        public static string Render(CommandDefinition command, CommandResult result)
        {
            string kind = VisualizationKind(command == null ? String.Empty : command.Renderer);
            return "View: " + kind + "\r\n" +
                "Risk: " + (command == null ? "unknown" : command.RiskTier) + "\r\n" +
                "Effects: " + (command == null ? "" : String.Join(", ", command.Effects)) + "\r\n\r\n" +
                (result == null ? "No result." : result.ToDisplayText());
        }

        private static string VisualizationKind(string renderer)
        {
            if (renderer.StartsWith("instance_diff", StringComparison.Ordinal)) return "Instance diff";
            if (renderer.StartsWith("snapshots_", StringComparison.Ordinal)) return "Snapshot list or diff";
            if (renderer.StartsWith("modsets_", StringComparison.Ordinal)) return "Modset plan graph";
            if (renderer.StartsWith("saves_", StringComparison.Ordinal)) return "Save index or retention plan";
            if (renderer.StartsWith("servers_", StringComparison.Ordinal)) return "Server plan";
            if (renderer.Contains("recovery") || renderer.Contains("transaction")) return "Transaction and recovery state";
            return "Structured command result";
        }
    }
}
