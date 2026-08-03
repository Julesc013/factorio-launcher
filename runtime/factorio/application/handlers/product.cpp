// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "handlers/product.h"

#include "command_result.h"
#include "facman/build_identity.hpp"
#include "fl_json.h"
#include "fl_runtime_verify.h"
#include "generated/command_catalog.h"
#include "generated/version.h"

#include <cstring>
#include <string>

namespace facman::factorio::application::handlers {
namespace {
const facman_generated_command_descriptor* run_execute_descriptor()
{
    for (std::size_t index = 0; index < FACMAN_GENERATED_REGISTERED_COMMAND_COUNT; ++index) {
        const facman_generated_command_descriptor& descriptor =
            facman_generated_registered_commands[index];
        if (std::strcmp(descriptor.command_name, "run.execute") == 0) return &descriptor;
    }
    return nullptr;
}

void add_optional_string(
    facman::core::json::ObjectBuilder& object,
    const char* key,
    const std::string& value)
{
    if (value.empty()) object.add_null(key);
    else object.add_string(key, value);
}
}

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

    const facman::package::RuntimePackageEvidence package =
        facman::package::inspect_runtime_package();
    const bool contract_set_matches_build = package.verified &&
        package.contract_set_sha256 == FACMAN_CONTRACT_SET_SHA256;
    const bool build_matches_package = package.verified &&
        package.source_revision == facman::build_identity::factorio_launcher_revision &&
        package.source_dirty_known &&
        package.source_dirty == facman::build_identity::source_dirty &&
        package.universal_launcher_revision == facman::build_identity::universal_launcher_revision &&
        package.universal_setup_revision == facman::build_identity::universal_setup_revision;

    facman::core::json::ObjectBuilder build;
    build.add_string("source_revision", facman::build_identity::factorio_launcher_revision);
    build.add_bool("source_dirty", facman::build_identity::source_dirty);
    build.add_string("build_identity", facman::build_identity::identity);
    build.add_string(
        "universal_launcher_revision",
        facman::build_identity::universal_launcher_revision);
    build.add_string(
        "universal_setup_revision",
        facman::build_identity::universal_setup_revision);

    facman::core::json::ObjectBuilder transport;
    transport.add_unsigned_integer("protocol_version", 2U);
    transport.add_string("request_schema", "facman.transport_request.v2");
    transport.add_string("response_schema", "facman.transport_response.v2");

    facman::core::json::ObjectBuilder package_identity;
    package_identity.add_string("mode", package.packaged ? "packaged" : "source_checkout");
    package_identity.add_string(
        "integrity",
        package.verified ? "sha256_consistent" : package.packaged ? "verification_failed" : "not_packaged");
    package_identity.add_bool("verified", package.verified);
    add_optional_string(package_identity, "profile_id", package.profile_id);
    add_optional_string(package_identity, "manifest_sha256", package.manifest_sha256);
    add_optional_string(package_identity, "closure_sha256", package.closure_sha256);
    add_optional_string(package_identity, "contract_set_sha256", package.contract_set_sha256);
    package_identity.add_bool("contract_set_matches_build", contract_set_matches_build);
    add_optional_string(package_identity, "backend_relative_path", package.backend_relative_path);
    add_optional_string(package_identity, "backend_sha256", package.backend_sha256);
    add_optional_string(package_identity, "source_revision", package.source_revision);
    if (package.source_dirty_known) package_identity.add_bool("source_dirty", package.source_dirty);
    else package_identity.add_null("source_dirty");
    add_optional_string(
        package_identity,
        "universal_launcher_revision",
        package.universal_launcher_revision);
    add_optional_string(
        package_identity,
        "universal_setup_revision",
        package.universal_setup_revision);
    package_identity.add_bool("build_matches_package", build_matches_package);
    package_identity.add_unsigned_integer("files_verified", package.files_verified);
    package_identity.add_string(
        "authenticity",
        package.packaged ? "not_proven_unsigned" : "not_applicable");
    package_identity.add_string("detail", package.detail);

    const facman_generated_command_descriptor* run_execute = run_execute_descriptor();
    const char* availability = run_execute == nullptr
        ? "catalog_entry_missing"
        : run_execute->availability;
    const char* refusal_code = run_execute == nullptr
        ? "command_catalog_entry_missing"
        : run_execute->availability_refusal_code;
    facman::core::json::ObjectBuilder run_capability;
    run_capability.add_string("command", "run.execute");
    run_capability.add_string("availability", availability);
    run_capability.add_string("refusal_code", refusal_code);
    run_capability.add_bool("enabled", std::strcmp(availability, "available") == 0);

    facman::core::json::ObjectBuilder backend_identity;
    backend_identity.add_string("schema", "facman.backend_identity.v1");
    backend_identity.add_string("product_id", "factorio");
    backend_identity.add_string("binding_id", "flb.factorio");
    backend_identity.add_string("backend_role", "facman_cli");
    backend_identity.add_object("build", build);
    backend_identity.add_object("transport", transport);
    backend_identity.add_string("command_catalog_sha256", FACMAN_COMMAND_CATALOG_SHA256);
    backend_identity.add_string("contract_set_sha256", FACMAN_CONTRACT_SET_SHA256);
    backend_identity.add_object("package", package_identity);
    backend_identity.add_object("run_execute", run_capability);

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
    output.add_object("backend_identity", backend_identity);
    ApplicationResult result;
    result.output = output.serialize();
    return result;
}
}
