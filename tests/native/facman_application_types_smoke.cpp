// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "application_configuration.h"
#include "command_admission.h"
#include "command_dispatch.h"
#include "fl_result.h"

#include <string>
#include <algorithm>
#include <cstdlib>
#include <variant>

namespace {
void set_environment(const char* name, const char* value)
{
#ifdef _WIN32
    _putenv_s(name, value);
#else
    setenv(name, value, 1);
#endif
}
}

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
    set_environment("FACMAN_SETUP_STATE_ROOT", "");
    set_environment("FACMAN_SETUP_ACCEPTANCE_ROOT", "");
    set_environment("FACMAN_SETUP_POLICY_ACTIVATION", "");
    const ApplicationConfiguration setup_missing = ApplicationConfiguration::load({});
    const CommandAdmissionDecision uninstall_denied =
        admit_command(setup_missing, CommandId::installs_uninstall_apply);
    if (uninstall_denied.admitted || uninstall_denied.code != "setup_authority_required") return 14;
    const CommandAdmissionDecision repair_plan_denied =
        admit_command(setup_missing, CommandId::installs_repair_plan);
    const CommandAdmissionDecision repair_apply_denied =
        admit_command(setup_missing, CommandId::installs_repair_apply);
    if (repair_plan_denied.admitted ||
        repair_plan_denied.code != "setup_repair_plan_authority_required" ||
        repair_apply_denied.admitted || repair_apply_denied.code != "setup_authority_required") return 21;
    const CommandAdmissionPolicy repair_plan_policy =
        command_admission_policy(CommandId::installs_repair_plan);
    const CommandAdmissionPolicy repair_apply_policy =
        command_admission_policy(CommandId::installs_repair_apply);
    if (std::find(repair_plan_policy.effects.begin(), repair_plan_policy.effects.end(),
            "setup_preview") == repair_plan_policy.effects.end() ||
        std::find(repair_plan_policy.capabilities.begin(), repair_plan_policy.capabilities.end(),
            "install.managed.repair.plan") == repair_plan_policy.capabilities.end() ||
        std::find(repair_apply_policy.effects.begin(), repair_apply_policy.effects.end(),
            "setup_mutation") == repair_apply_policy.effects.end() ||
        std::find(repair_apply_policy.capabilities.begin(), repair_apply_policy.capabilities.end(),
            "install.managed.repair.apply") == repair_apply_policy.capabilities.end()) return 22;
    for (const CommandId recovery_command : {
            CommandId::installs_recovery_inspect,
            CommandId::installs_recovery_apply}) {
        const CommandAdmissionDecision denied = admit_command(setup_missing, recovery_command);
        if (denied.admitted ||
            denied.code != "setup_uninstall_recovery_authority_required") return 15;
        const CommandAdmissionPolicy recovery_policy = command_admission_policy(recovery_command);
        if (std::find(recovery_policy.effects.begin(), recovery_policy.effects.end(),
                "setup_preview") == recovery_policy.effects.end() ||
            std::find(recovery_policy.capabilities.begin(), recovery_policy.capabilities.end(),
                "install.managed.uninstall.recover") == recovery_policy.capabilities.end() ||
            recovery_policy.capabilities.size() != 1U ||
            recovery_policy.effects.size() !=
                (recovery_command == CommandId::installs_recovery_apply ? 3U : 2U) ||
            (std::find(recovery_policy.effects.begin(), recovery_policy.effects.end(),
                "workspace_write") != recovery_policy.effects.end()) !=
                (recovery_command == CommandId::installs_recovery_apply)) return 16;
    }
    set_environment("FACMAN_SETUP_STATE_ROOT", "state");
    const ApplicationConfiguration setup_incomplete = ApplicationConfiguration::load({});
    const CommandAdmissionDecision incomplete_inspect =
        admit_command(setup_incomplete, CommandId::installs_recovery_inspect);
    const CommandAdmissionDecision incomplete_apply =
        admit_command(setup_incomplete, CommandId::installs_recovery_apply);
    if (incomplete_inspect.admitted || incomplete_apply.admitted ||
        incomplete_inspect.code != "setup_uninstall_recovery_authority_required" ||
        incomplete_apply.code != "setup_uninstall_recovery_authority_required") return 17;
    set_environment("FACMAN_SETUP_ACCEPTANCE_ROOT", "acceptance");
    set_environment("FACMAN_SETUP_POLICY_ACTIVATION", "operator_acceptance_candidate");
    const ApplicationConfiguration setup_present = ApplicationConfiguration::load({});
    if (!admit_command(setup_present, CommandId::installs_uninstall_apply).admitted) return 18;
    if (!admit_command(setup_present, CommandId::installs_repair_plan).admitted ||
        !admit_command(setup_present, CommandId::installs_repair_apply).admitted) return 23;
    if (!admit_command(setup_present, CommandId::installs_recovery_inspect).admitted ||
        !admit_command(setup_present, CommandId::installs_recovery_apply).admitted) return 19;
    const CommandAdmissionPolicy uninstall_policy =
        command_admission_policy(CommandId::installs_uninstall_apply);
    if (std::find(uninstall_policy.capabilities.begin(), uninstall_policy.capabilities.end(),
            "install.managed.uninstall.apply") == uninstall_policy.capabilities.end()) return 20;
    return 0;
}
