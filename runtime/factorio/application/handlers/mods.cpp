// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "handlers/mods.h"

#include "command_result.h"
#include "flb_factorio_mods.h"

namespace facman::factorio::application::handlers {
ApplicationResult import_mod(ApplicationContext& context, const ImportModRequest& request)
{
    return from_modset_outcome(modsets::import_mod(context.workspace(), request));
}

namespace {
ApplicationResult inventory_result(const char* operation, facman::core::Result<std::string> result)
{
    if (result) { ApplicationResult output; output.output = result.take_value(); return output; }
    return refused(safety_refusal(operation, result.error().code, "Local mod inventory operation was refused",
        result.error().message, result.error().recoverable), result.error().code, result.error().message, result.error().kind);
}
}

ApplicationResult dispatch_mod_inventory(ApplicationContext& context, const ApplicationRequest& request)
{
    const ModInventoryRequest empty;
    const auto& value = request.command == CommandId::mods_list
        ? empty : std::get<ModInventoryRequest>(request.payload);
    switch (request.command) {
    case CommandId::mods_list: return inventory_result("mods.list", mods::inventory_list(context.workspace()));
    case CommandId::mods_index: return inventory_result("mods.index", mods::inventory_index(context.workspace(), value));
    case CommandId::mods_inspect: return inventory_result("mods.inspect", mods::inventory_inspect(context.workspace(), value));
    case CommandId::mods_verify: return inventory_result("mods.verify", mods::inventory_verify(context.workspace(), value));
    case CommandId::mods_explain: return inventory_result("mods.explain", mods::inventory_explain(context.workspace(), value));
    default: return inventory_result("mods.inventory", facman::core::Result<std::string>::failure(
        {"unsupported_operation", "Unsupported local mod inventory command", "mods"}));
    }
}
}
