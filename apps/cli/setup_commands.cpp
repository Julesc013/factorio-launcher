// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "setup_commands.h"

#include "fl_json.h"

#include <map>
#include <set>
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

std::optional<std::map<std::string, std::string>> exact_repair_apply_options(
    const std::vector<std::string>& args)
{
    static const std::set<std::string> value_options {
        "--archive", "--digest", "--plan-created-at", "--record-digest",
        "--transaction-id", "--applied-at", "--confirm"};
    if (!positional(args, 3) || !positional(args, 4)) return std::nullopt;
    std::map<std::string, std::string> values;
    bool json_seen = false;
    for (std::size_t index = 5; index < args.size(); ++index) {
        const std::string& token = args[index];
        if (token == "--json") {
            if (json_seen) return std::nullopt;
            json_seen = true;
            continue;
        }
        if (value_options.count(token) == 0U || values.count(token) != 0U ||
            index + 1U >= args.size() || args[index + 1U].empty() ||
            args[index + 1U].compare(0, 2, "--") == 0) {
            return std::nullopt;
        }
        values.emplace(token, args[++index]);
    }
    if (values.size() != value_options.size() || values["--confirm"] != "APPLY") {
        return std::nullopt;
    }
    return values;
}

std::optional<std::map<std::string, std::string>> exact_install_apply_options(
    const std::vector<std::string>& args)
{
    static const std::set<std::string> value_options {
        "--version", "--archive", "--target", "--id", "--digest",
        "--plan-created-at", "--transaction-id", "--applied-at", "--confirm"};
    if (!positional(args, 3)) return std::nullopt;
    std::map<std::string, std::string> values;
    bool json_seen = false;
    for (std::size_t index = 4; index < args.size(); ++index) {
        const std::string& token = args[index];
        if (token == "--json") {
            if (json_seen) return std::nullopt;
            json_seen = true;
            continue;
        }
        if (value_options.count(token) == 0U || values.count(token) != 0U ||
            index + 1U >= args.size() || args[index + 1U].empty() ||
            args[index + 1U].compare(0, 2, "--") == 0) return std::nullopt;
        values.emplace(token, args[++index]);
    }
    if (values.size() != value_options.size() || values["--confirm"] != "APPLY") {
        return std::nullopt;
    }
    return values;
}

} // namespace

std::optional<SetupApplyCommand> setup_apply_request(
    const std::string& action,
    const std::vector<std::string>& args)
{
    if (action == "install") {
        auto values = exact_install_apply_options(args);
        if (!values) return std::nullopt;
        return SetupApplyCommand {"installs.install.apply", payload({
            {"version", values->at("--version")}, {"archive", values->at("--archive")},
            {"target_root", values->at("--target")}, {"install_id", values->at("--id")},
            {"plan_id", args[3]}, {"plan_digest", values->at("--digest")},
            {"plan_created_at", values->at("--plan-created-at")},
            {"transaction_id", values->at("--transaction-id")},
            {"applied_at", values->at("--applied-at")},
            {"confirmation", values->at("--confirm")}}),
            "Managed install apply dispatched."};
    }
    if (action == "repair") {
        auto values = exact_repair_apply_options(args);
        if (!values) return std::nullopt;
        return SetupApplyCommand {"installs.repair.apply", payload({
            {"install_id", args[3]}, {"archive", values->at("--archive")},
            {"plan_id", args[4]}, {"plan_digest", values->at("--digest")},
            {"plan_created_at", values->at("--plan-created-at")},
            {"install_record_sha256", values->at("--record-digest")},
            {"transaction_id", values->at("--transaction-id")},
            {"applied_at", values->at("--applied-at")},
            {"confirmation", values->at("--confirm")}}),
            "Managed repair apply dispatched."};
    }
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
