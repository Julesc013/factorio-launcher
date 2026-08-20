// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "application_configuration.h"
#include "command_admission.h"
#include "command_dispatch.h"
#include "fl_result.h"

#include <string>
#include <algorithm>
#include <variant>

int main()
{
    using namespace facman::factorio::application;
    ApplicationRequest request;
    std::string detail;
    if (!decode_request(
            CommandId::run_execute,
            "{\"instance_id\":\"space-age-main\"}",
            false,
            request,
            detail)) return 1;
    if (!std::holds_alternative<ExecuteRunRequest>(request.payload)) return 2;
    const ExecuteRunRequest& execute = std::get<ExecuteRunRequest>(request.payload);
    if (execute.instance_id.str() != "space-age-main") return 3;
    if (facman::core::outcome_kind_from_name("unavailable") != facman::core::OutcomeKind::unavailable) return 4;
    if (std::string(facman::core::outcome_kind_name(facman::core::OutcomeKind::cancelled)) != "cancelled") return 5;
    if (facman::core::outcome_kind_from_name("outcome_unknown") != facman::core::OutcomeKind::outcome_unknown) return 6;
    if (decode_request(
            CommandId::run_execute,
            "{\"instance_id\":\"../escape\"}",
            false,
            request,
            detail)) return 6;
    const CommandAdmissionPolicy policy = command_admission_policy(CommandId::run_execute);
    if (std::find(policy.effects.begin(), policy.effects.end(), "workspace_write") == policy.effects.end() ||
        std::find(policy.effects.begin(), policy.effects.end(), "process_execute") == policy.effects.end() ||
        std::find(policy.capabilities.begin(), policy.capabilities.end(), "process.execute") == policy.capabilities.end()) return 7;
    const ApplicationConfiguration configuration = ApplicationConfiguration::load({});
    const CommandAdmissionDecision execution = admit_command(configuration, CommandId::run_execute);
    if (execution.admitted || execution.code != "isolation_not_proven") return 8;
    if (!admit_command(configuration, CommandId::run_preview).admitted) return 9;
    if (denied_admission_disposition(CommandId::run_execute, execution) !=
        DeniedAdmissionDisposition::transform_to_product_refusal) return 10;
    if (denied_admission_disposition(CommandId::run_preview, execution) !=
        DeniedAdmissionDisposition::reject) return 11;
    const CommandAdmissionDecision network {
        false, "network_forbidden", "network is not authorised"};
    if (denied_admission_disposition(CommandId::mods_search, network) !=
        DeniedAdmissionDisposition::transform_to_product_refusal) return 12;
    if (denied_admission_disposition(CommandId::saves_list, network) !=
        DeniedAdmissionDisposition::reject) return 13;
    return 0;
}
