// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "handlers/product.h"

#include "command_result.h"
#include "fl_json.h"

namespace facman::factorio::application::handlers {
ApplicationResult inspect_product(ApplicationContext&, const std::string& command)
{
    facman::core::json::ArrayBuilder capabilities;
    for (const char* capability : {
             "install_refs", "instances", "profiles", "artifact_sets", "launch_plans",
             "diagnostics", "mods", "saves", "servers"}) {
        capabilities.add_string(capability);
    }
    facman::core::json::ObjectBuilder boundaries;
    boundaries.add_bool("bundles_factorio_binaries", false);
    boundaries.add_bool("repairs_foreign_installs", false);
    boundaries.add_bool("uninstalls_foreign_installs", false);
    boundaries.add_bool("uses_official_branding", false);
    boundaries.add_string("default_run_mode", "dry-run");
    facman::core::json::ObjectBuilder output;
    output.add_string("schema", "factorio.product.v1");
    output.add_string("command", command);
    output.add_string("product_id", "factorio");
    output.add_string("display_name", "Factorio");
    output.add_string("public_name", "FacMan - unofficial launcher and isolated instance manager for Factorio");
    output.add_string("binding_id", "flb.factorio");
    output.add_bool("unofficial", true);
    output.add_string("status", "ok");
    output.add_array("capabilities", capabilities);
    output.add_object("boundaries", boundaries);
    ApplicationResult result;
    result.output = output.serialize();
    return result;
}
}
