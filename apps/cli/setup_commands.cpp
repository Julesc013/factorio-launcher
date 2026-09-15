// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "setup_commands.h"

#include "fl_json.h"

#include <utility>

namespace facman::cli {
namespace {

std::string option(const std::vector<std::string>& args, const std::string& name)
{
    for (std::size_t index = 0; index + 1 < args.size(); ++index) {
        if (args[index] == name) return args[index + 1];
    }
    return {};
}

bool positional(const std::vector<std::string>& args, std::size_t index)
{
    return index < args.size() && !args[index].empty() && args[index].compare(0, 2, "--") != 0;
}

std::string payload(const std::vector<std::pair<std::string, std::string>>& fields)
{
    facman::core::json::ObjectBuilder output;
    for (const auto& field : fields) output.add_string(field.first, field.second);
    return output.serialize();
}

} // namespace

std::optional<SetupApplyCommand> setup_apply_request(
    const std::string& action,
    const std::vector<std::string>& args)
{
    const std::string digest = option(args, "--digest");
    const std::string confirmation = option(args, "--confirm");
    if (!positional(args, 3) || digest.empty() || confirmation != "APPLY") return std::nullopt;
    if (action == "recovery") {
        if (!positional(args, 4)) return std::nullopt;
        return SetupApplyCommand {"installs.recovery.apply", payload({
            {"transaction_id", args[3]}, {"plan_id", args[4]},
            {"plan_digest", digest}, {"confirmation", confirmation}}),
            "Managed uninstall recovery apply dispatched."};
    }
    if (action != "uninstall") {
        return SetupApplyCommand {"installs." + action + ".apply", payload({
            {"plan_id", args[3]}, {"plan_digest", digest}, {"confirmation", confirmation}}),
            "Managed " + action + " apply dispatched."};
    }
    const std::string plan_created_at = option(args, "--plan-created-at");
    const std::string transaction_id = option(args, "--transaction-id");
    const std::string applied_at = option(args, "--applied-at");
    if (!positional(args, 4) || plan_created_at.empty() || transaction_id.empty() || applied_at.empty()) {
        return std::nullopt;
    }
    return SetupApplyCommand {"installs.uninstall.apply", payload({
        {"install_id", args[3]}, {"plan_id", args[4]}, {"plan_digest", digest},
        {"plan_created_at", plan_created_at}, {"transaction_id", transaction_id},
        {"applied_at", applied_at}, {"confirmation", confirmation}}),
        "Managed uninstall apply dispatched."};
}

} // namespace facman::cli
