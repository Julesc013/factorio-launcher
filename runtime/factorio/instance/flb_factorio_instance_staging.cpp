// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT
#include "flb_factorio_instance_staging.h"
#include "fl_json.h"
#include "flb_factorio_launch_plan.h"
#include "fl_file_io.h"
namespace facman::factorio::instance {
std::string instance_manifest_json(const facman::workspace::InstanceRecord& instance)
{
    facman::core::json::ObjectBuilder save_policy, concurrency, export_policy, output;
    save_policy.add_string("mode", "instance-local");
    concurrency.add_bool("single_writer", true);
    export_policy.add_bool("portable", true);
    export_policy.add_bool("redact_secrets", true);
    output.add_string("schema", "factorio.instance.v1");
    output.add_string("instance_id", instance.id.str());
    output.add_string("display_name", instance.display_name);
    output.add_string("install_ref", instance.install_ref.str());
    output.add_string("factorio_version", instance.factorio_version);
    output.add_string("local_data_root", facman::platform::path_to_utf8(instance.root.lexically_normal()));
    output.add_string("profile", instance.profile);
    output.add_null("modset");
    output.add_string("template", instance.template_id);
    output.add_object("save_policy", save_policy);
    output.add_null("account_ref");
    output.add_object("concurrency", concurrency);
    output.add_object("export_policy", export_policy);
    return output.serialize();
}
std::string instance_effective_config(const facman::workspace::InstanceRecord& instance,
    const facman::factorio::discovery::InstallRef& install)
{
    launch::InstanceLaunchRef target;
    target.instance_id = instance.id.str();
    target.profile_id = instance.profile;
    target.local_data_root = instance.root;
    target.launch_mode = "gui";
    launch::InstallLaunchRef source;
    source.root = install.root;
    source.executable = install.executable;
    source.ownership = install.ownership;
    source.distribution_origin = install.distribution_origin;
    source.platform_integration = install.platform_integration;
    source.strict_isolation_eligibility = install.strict_isolation_eligibility;
    source.external_state_domains = install.external_state_domains;
    return launch::effective_config_ini(target, source);
}
bool prepare_instance_layout(const std::filesystem::path& staging, std::string& detail)
{
    for (const char* dir : {"config", "mods", "saves", "scenarios", "script-output", "logs",
            "crash", "exports", "cache", "locks"}) {
        std::error_code error;
        std::filesystem::create_directories(staging / dir, error);
        if (error) { detail = error.message(); return false; }
    }
    return true;
}
}
