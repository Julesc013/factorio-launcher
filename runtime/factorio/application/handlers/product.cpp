// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "handlers/product.h"

#include "command_result.h"

namespace facman::factorio::application::handlers {
ApplicationResult inspect_product(ApplicationContext&, const std::string& command)
{
    ApplicationResult result;
    result.output = std::string("{\"schema\":\"factorio.product.v1\",\"command\":") + json_quote(command) +
        ","
        "\"product_id\":\"factorio\",\"display_name\":\"Factorio\","
        "\"public_name\":\"FacMan - unofficial launcher and isolated instance manager for Factorio\","
        "\"binding_id\":\"flb.factorio\",\"unofficial\":true,\"status\":\"ok\","
        "\"capabilities\":[\"install_refs\",\"instances\",\"profiles\",\"artifact_sets\","
        "\"launch_plans\",\"diagnostics\",\"mods\",\"saves\",\"servers\"],"
        "\"boundaries\":{\"bundles_factorio_binaries\":false,\"repairs_foreign_installs\":false,"
        "\"uninstalls_foreign_installs\":false,\"uses_official_branding\":false,"
        "\"default_run_mode\":\"dry-run\"}}";
    return result;
}
}
