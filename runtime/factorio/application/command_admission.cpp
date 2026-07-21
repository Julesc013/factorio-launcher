// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "command_admission.h"

#include "command_dispatch.h"

namespace facman::factorio::application {

CommandAdmissionPolicy command_admission_policy(CommandId command)
{
    CommandAdmissionPolicy policy;
    policy.effects.push_back("workspace_read");
    if (writes_persistent_state(command)) policy.effects.push_back("workspace_write");
    switch (command) {
    case CommandId::install_scan:
        policy.capabilities.push_back("install.discover");
        break;
    case CommandId::install_import:
        policy.capabilities.push_back("install.reference.register");
        break;
    case CommandId::installs_describe:
        policy.capabilities.push_back("install.model.inspect");
        break;
    case CommandId::installs_reconcile_plan:
        policy.capabilities.push_back("install.reconciliation.plan");
        break;
    case CommandId::instances_describe:
        policy.capabilities.push_back("instance.model.inspect");
        break;
    case CommandId::instances_readiness:
        policy.capabilities.push_back("instance.readiness.inspect");
        break;
    case CommandId::installs_install_plan:
        policy.effects.push_back("setup_preview");
        policy.capabilities.push_back("install.managed.plan");
        break;
    case CommandId::installs_install_apply:
        policy.effects.push_back("setup_mutation");
        policy.capabilities.push_back("install.managed.apply");
        break;
    case CommandId::launch_plan_build:
    case CommandId::run_preview:
        policy.capabilities.push_back("launch.preview");
        break;
    case CommandId::launch_plan_preflight:
        policy.capabilities.push_back("launch.preflight");
        break;
    case CommandId::run_execute:
        if (!writes_persistent_state(command)) policy.effects.push_back("workspace_write");
        policy.effects.push_back("process_execute");
        policy.capabilities.push_back("launch.execute.instance_isolated");
        policy.capabilities.push_back("launch.execute.hermetic");
        policy.capabilities.push_back("process.execute");
        break;
    case CommandId::mods_search:
        policy.effects.push_back("network_read");
        policy.capabilities.push_back("network.mod_portal.read");
        break;
    case CommandId::mods_install:
    case CommandId::mods_update:
        policy.effects.push_back("network_write");
        policy.effects.push_back("credential_read");
        policy.capabilities.push_back("network.mod_portal.write");
        policy.capabilities.push_back("credential.factorio.read");
        break;
    case CommandId::servers_start:
    case CommandId::servers_stop:
    case CommandId::servers_rcon:
    case CommandId::dev_dump_data:
    case CommandId::dev_dump_icons:
    case CommandId::dev_benchmark:
    case CommandId::dev_instrument_mod:
        policy.effects.push_back("process_execute");
        policy.capabilities.push_back("process.execute");
        break;
    default:
        break;
    }
    return policy;
}

CommandAdmissionDecision admit_command(
    const ApplicationConfiguration& configuration,
    CommandId command)
{
    const CommandAdmissionPolicy policy = command_admission_policy(command);
    for (const std::string& effect : policy.effects) {
        if (effect == "process_execute" && !configuration.process_execution_authorized()) {
            if (command == CommandId::run_execute) {
                return {false, "isolation_not_proven", "real Factorio execution authority has not passed either real-play gate"};
            }
            // Untouched process-shaped domains retain their existing typed
            // refusals while this global seam remains the final authority.
            continue;
        }
        if (effect == "network_read" && !configuration.network_read_authorized()) {
            return {false, "network_forbidden", "Mod Portal network access is not authorised"};
        }
        if (effect == "network_write" && !configuration.network_write_authorized()) {
            return {false, "network_forbidden", "Mod Portal network mutation is not authorised"};
        }
    }
    return {};
}

} // namespace facman::factorio::application
