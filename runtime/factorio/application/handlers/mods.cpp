// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "handlers/mods.h"

#include "command_result.h"

namespace facman::factorio::application::handlers {
ApplicationResult import_mod(ApplicationContext& context, const ImportModRequest& request)
{
    return from_modset_outcome(modsets::import_mod(context.workspace(), request));
}
}
