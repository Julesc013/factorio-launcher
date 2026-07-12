// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "handlers/doctor.h"

#include "command_result.h"
#include "fl_json.h"
#include "flb_factorio_discovery.h"

#include <filesystem>
#include <utility>
#include <vector>

namespace facman::factorio::application::handlers {
ApplicationResult run_doctor(ApplicationContext& context, const DoctorRequest& request)
{
    auto installs = context.installs().list();
    auto instances = context.instances().list();
    if (!installs || !instances) {
        const auto& error = !installs ? installs.error() : instances.error();
        return refused(
            safety_refusal("doctor.run", error.code, "Workspace records could not be inspected", error.message, true),
            error.code, error.message);
    }
    const std::size_t incomplete = transactions::incomplete_count(context.workspace());
    std::vector<std::filesystem::path> roots;
    for (const std::string& root : request.roots) roots.push_back(root);
    const auto discovered = request.roots.empty() ? std::vector<facman::factorio::discovery::InstallRef>() :
        facman::factorio::discovery::scan_install_candidates(roots);
    bool invalid_candidates = false;
    for (const auto& install : discovered) if (install.verification_status == "invalid") invalid_candidates = true;
    const bool warning = installs.value().empty() || incomplete != 0 || invalid_candidates;
    facman::core::json::ArrayBuilder problems;
    facman::core::json::ArrayBuilder suggested_fixes;
    facman::core::json::ArrayBuilder warnings;
    if (installs.value().empty()) {
        problems.add_string("no install references registered yet");
        suggested_fixes.add_string("scan or import a Factorio install reference");
        warnings.add_string("no install references registered yet");
    }
    if (invalid_candidates) {
        problems.add_string("invalid Factorio install candidates found");
        suggested_fixes.add_string("inspect invalid candidates and choose a valid Factorio install root");
        warnings.add_string("invalid Factorio install candidates found");
    }
    if (incomplete != 0) {
        problems.add_string("incomplete workspace transactions require recovery inspection");
        suggested_fixes.add_string("run facman workspace recovery inspect --json");
        warnings.add_string("incomplete workspace transactions require recovery inspection");
    }
    facman::core::json::ArrayBuilder checks;
    for (const auto& check : std::vector<std::pair<std::string, std::string>> {
             {"workspace", "ok"},
             {"install_refs", installs.value().empty() ? "warning" : "ok"}}) {
        facman::core::json::ObjectBuilder item;
        item.add_string("id", check.first);
        item.add_string("status", check.second);
        checks.add_object(item);
    }
    if (!request.roots.empty()) {
        facman::core::json::ObjectBuilder item;
        item.add_string("id", "discovery_candidates");
        item.add_string("status", invalid_candidates ? "warning" : "ok");
        checks.add_object(item);
    }
    facman::core::json::ObjectBuilder transaction_check;
    transaction_check.add_string("id", "workspace_transactions");
    transaction_check.add_string("status", incomplete ? "warning" : "ok");
    checks.add_object(transaction_check);
    facman::core::json::ObjectBuilder output;
    output.add_string("schema", "factorio.diagnostic_report.v1");
    output.add_string("command", "doctor.run");
    output.add_string("status", warning ? "warning" : "ok");
    output.add_string("workspace", context.workspace().string());
    output.add_unsigned_integer("registered_installs", installs.value().size());
    output.add_unsigned_integer("instances", instances.value().size());
    output.add_unsigned_integer("incomplete_transactions", incomplete);
    output.add_array("problems", problems);
    output.add_array("suggested_fixes", suggested_fixes);
    output.add_array("checks", checks);
    output.add_array("warnings", warnings);
    if (!request.roots.empty()) {
        auto discovery_report = decode_json_value(
            facman::factorio::discovery::discovery_report_json(discovered));
        if (discovery_report) output.add_value("discovery", discovery_report.value());
    }
    ApplicationResult result;
    result.output = output.serialize();
    return result;
}
}
