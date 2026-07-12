// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "handlers/launch.h"

#include "command_result.h"
#include "flb_factorio_discovery.h"

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
    install.verification_status = record.value().verification_status;
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
    launch::InstanceLaunchRef instance_ref {instance.id.str(), instance.profile, instance.root};
    launch::InstallLaunchRef install_ref {install.root, install.executable, install.ownership};
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
    launch::InstanceLaunchRef instance_ref {instance.id.str(), instance.profile, instance.root};
    launch::InstallLaunchRef install_ref {install.root, install.executable, install.ownership};
    ApplicationResult result;
    result.output = launch::preflight_launch(instance_ref, install_ref, "launch_plan.preflight");
    return result;
}

} // namespace facman::factorio::application::handlers
