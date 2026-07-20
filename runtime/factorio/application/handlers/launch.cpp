// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "handlers/launch.h"

#include "command_result.h"
#include "flb_factorio_discovery.h"
#include "flb_factorio_profiles.h"
#include "handlers/unavailable.h"

namespace facman::factorio::application::handlers {
namespace discovery = facman::factorio::discovery;

namespace {
bool load_install(ApplicationContext& context, const std::string& id, discovery::InstallRef& install)
{
    auto parsed_id = facman::core::InstallId::parse_legacy(id);
    if (!parsed_id) return false;
    auto record = context.installs().load(parsed_id.value());
    if (!record) return false;
    install.install_id = record.value().id.str();
    install.root = record.value().root;
    install.executable = record.value().executable;
    install.version = record.value().version;
    install.ownership = record.value().ownership;
    install.source = record.value().source;
    install.platform = record.value().platform;
    install.distribution_origin = record.value().distribution_origin;
    install.platform_integration = record.value().platform_integration;
    install.strict_isolation_eligibility = record.value().strict_isolation_eligibility;
    install.external_state_domains = record.value().external_state_domains;
    install.setup_state_ref = record.value().setup_state_ref;
    install.lifecycle_status = record.value().lifecycle_status;
    install.last_verification_identity = record.value().last_verification_identity;
    install.state_revision = record.value().state_revision;
    install.verification_status = record.value().verification_status;
    discovery::classify_install_isolation(install);
    discovery::classify_install_layout(install);
    return true;
}

ApplicationResult load_refs(
    ApplicationContext& context,
    const BuildLaunchPlanRequest& request,
    facman::workspace::InstanceRecord& instance,
    discovery::InstallRef& install,
    const std::string& operation)
{
    auto parsed_id = facman::core::InstanceId::parse(request.instance_id);
    if (!parsed_id) return refused(
        safety_refusal(operation, parsed_id.error().code, "Instance id is not portable", parsed_id.error().message, false),
        parsed_id.error().code, parsed_id.error().message);
    auto loaded = context.instances().load(parsed_id.value());
    if (!loaded) return refused(
        safety_refusal(operation, "unknown_instance", "Instance is not registered", request.instance_id, true),
        "unknown_instance", "Instance is not registered");
    instance = loaded.take_value();
    if (!load_install(context, instance.install_ref.str(), install)) return refused(
        safety_refusal(operation, "unknown_install", "Install reference is not registered", instance.install_ref.str(), true),
        "unknown_install", "Install reference is not registered");
    return {};
}
}

ApplicationResult preview_launch(ApplicationContext& context, const BuildLaunchPlanRequest& request, const std::string& command)
{
    facman::workspace::InstanceRecord instance;
    discovery::InstallRef install;
    ApplicationResult loaded = load_refs(context, request, instance, install, "launch_plan.preview");
    if (loaded.status != ULK_STATUS_OK) return loaded;
    auto effective = profiles::effective_profile_for_instance(context.workspace(), instance.id.str(), instance.profile);
    if (!effective) return refused(
        safety_refusal(command, effective.error().code, "Effective profile is invalid", effective.error().message, true),
        effective.error().code, effective.error().message);
    launch::InstanceLaunchRef instance_ref {
        instance.id.str(), instance.profile, instance.root, effective.value().settings.launch_mode,
        effective.value().launch_arguments};
    launch::InstallLaunchRef install_ref {
        install.root,
        install.executable,
        install.ownership,
        install.distribution_origin,
        install.platform_integration,
        install.strict_isolation_eligibility,
        install.external_state_domains,
    };
    ApplicationResult result;
    result.output = launch::build_launch_plan(instance_ref, install_ref, command);
    return result;
}

ApplicationResult preflight_launch(ApplicationContext& context, const BuildLaunchPlanRequest& request)
{
    facman::workspace::InstanceRecord instance;
    discovery::InstallRef install;
    ApplicationResult loaded = load_refs(context, request, instance, install, "launch_plan.preflight");
    if (loaded.status != ULK_STATUS_OK) return loaded;
    auto effective = profiles::effective_profile_for_instance(context.workspace(), instance.id.str(), instance.profile);
    if (!effective) return refused(
        safety_refusal("launch_plan.preflight", effective.error().code, "Effective profile is invalid", effective.error().message, true),
        effective.error().code, effective.error().message);
    launch::InstanceLaunchRef instance_ref {
        instance.id.str(), instance.profile, instance.root, effective.value().settings.launch_mode,
        effective.value().launch_arguments};
    launch::InstallLaunchRef install_ref {
        install.root,
        install.executable,
        install.ownership,
        install.distribution_origin,
        install.platform_integration,
        install.strict_isolation_eligibility,
        install.external_state_domains,
    };
    ApplicationResult result;
    result.output = launch::preflight_launch(instance_ref, install_ref, "launch_plan.preflight");
    return result;
}

ApplicationResult refuse_execute(
    ApplicationContext& context,
    const ExecuteRunRequest& request,
    const CommandAdmissionDecision& admission)
{
    std::string code = "isolation_not_proven";
    std::string detail = request.instance_id.empty()
        ? "real Factorio write isolation has not been proven"
        : "real Factorio write isolation has not been proven for instance " + request.instance_id.str();
    if (!request.instance_id.empty()) {
        auto instance = context.instances().load(request.instance_id);
        if (instance) {
            auto record = context.installs().load(instance.value().install_ref);
            if (record) {
                discovery::InstallRef install;
                install.root = record.value().root;
                install.source = record.value().source;
                install.distribution_origin = record.value().distribution_origin;
                install.platform_integration = record.value().platform_integration;
                install.strict_isolation_eligibility = record.value().strict_isolation_eligibility;
                install.external_state_domains = record.value().external_state_domains;
                discovery::classify_install_isolation(install);
                if (install.distribution_origin == "steam" || install.platform_integration == "steam") {
                    code = "steam_external_state_not_isolated";
                    detail = "Steam-managed external state is not isolated for instance " + request.instance_id.str();
                }
            }
        }
    }
    if (code == "isolation_not_proven" && !admission.admitted) {
        code = admission.code;
        detail = admission.reason;
        if (!request.instance_id.empty()) detail += " for instance " + request.instance_id.str();
    }
    return unavailable(context, "run.execute", code, detail);
}

} // namespace facman::factorio::application::handlers
