// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

using System.Collections.Generic;

namespace FacMan.WinForms
{
    // Stable adapter retained for callers; all records and request mappings are generated.
    public static class CommandCatalog
    {
        public static IList<CommandDefinition> All()
        {
            return GeneratedCommandCatalog.All();
        }

        public static CommandDefinition Find(string commandId)
        {
            return GeneratedCommandCatalog.Find(commandId);
        }
    }
}
