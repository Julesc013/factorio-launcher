// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT
#include "fl_product_resource_internal.h"
#include "fl_runtime_component.h"
#include <sstream>
namespace facman::package::resource_detail {
namespace {
std::string trim(std::string value)
{
    const auto begin = value.find_first_not_of(" \t\r");
    if (begin == std::string::npos) return {};
    return value.substr(begin, value.find_last_not_of(" \t\r") - begin + 1);
}
std::pair<std::string, std::string> scalar(const std::string& line)
{
    const auto equals = line.find('='); if (equals == std::string::npos) refuse("invalid product TOML scalar");
    auto key = trim(line.substr(0, equals)); auto value = trim(line.substr(equals + 1));
    if (value != "true" && value != "false") {
        if (value.size() < 2 || value.front() != '"' || value.back() != '"') refuse("unsupported product TOML value");
        value = value.substr(1, value.size() - 2);
        if (value.find_first_of("\"\\") != std::string::npos) refuse("unsupported product TOML escaping");
    }
    if (key.empty() || value.find('\0') != std::string::npos) refuse("invalid product TOML field");
    return {key, value};
}
std::map<std::string, std::string> flat(const std::string& bytes)
{
    std::istringstream input(bytes); std::string line; std::map<std::string, std::string> result;
    while (std::getline(input, line)) {
        line = trim(line); if (line.empty()) continue;
        auto value = scalar(line); if (!result.insert(value).second) refuse("duplicate product TOML field");
    }
    return result;
}
std::map<std::string, std::string> workspace_pins(const std::string& bytes)
{
    std::map<std::string, std::string> result, component;
    auto finish = [&] {
        if (component.empty()) return;
        const auto id = component.find("id"); const auto pin = component.find("pin");
        if (id == component.end() || pin == component.end() || !hex(pin->second, 40) || !result.emplace(id->second, pin->second).second)
            refuse("invalid workspace source component");
        component.clear();
    };
    std::istringstream input(bytes); std::string line; bool inside = false;
    while (std::getline(input, line)) {
        line = trim(line); if (line.empty()) continue;
        if (line == "[[component]]") { finish(); inside = true; continue; }
        if (!inside) continue;
        auto value = scalar(line);
        if (!component.insert(value).second) refuse("duplicate workspace component field");
    }
    finish();
    if (result.size() != 3 || !result.count("factorio_binding") || !result.count("universal_launcher") || !result.count("universal_setup"))
        refuse("workspace source component set differs");
    return result;
}
}
void windows_manifest(ProductResourceSnapshot& snapshot, ProductResourceIdentity& identity, Inventory& inventory)
{
    const auto& raw = snapshot.capture("manifest/package.v1.toml");
    const auto values = flat(raw);
    const std::set<std::string> required = {
        "schema", "profile_id", "lane", "target_os", "target_arch", "package_type", "entrypoint", "linkage_model",
        "release_profile", "package_manifest", "workspace_lock", "source_revision", "proof_baseline_revision",
        "universal_launcher_revision", "universal_setup_revision", "artifact_level", "signed", "published",
        "source_dirty", "python_runtime", "bundles_factorio_binaries"};
    if (values.size() != required.size()) refuse("Windows product manifest fields differ");
    for (const auto& key : required) if (!values.count(key)) refuse("missing Windows product manifest field: " + key);
    const std::map<std::string, std::string> fixed = {
        {"schema", "facman.built_package.v1"}, {"profile_id", "windows_product_x64"}, {"target_os", "windows"},
        {"lane", "platform_product_bundle"}, {"release_profile", "release/profiles/windows_product_x64/profile.toml"},
        {"package_manifest", "release/packaging/windows/platform_product.v1.toml"},
        {"target_arch", "x64"}, {"package_type", "portable_zip"}, {"entrypoint", "FacMan.exe"},
        {"linkage_model", "compatibility_bundle"}, {"artifact_level", "built-artifact"},
        {"workspace_lock", "release/index/workspace_lock.v1.toml"}, {"signed", "false"}, {"published", "false"},
        {"python_runtime", "false"}, {"bundles_factorio_binaries", "false"}};
    for (const auto& pair : fixed) if (values.at(pair.first) != pair.second) refuse("Windows product policy mismatch: " + pair.first);
    if (values.at("source_dirty") != "false" && values.at("source_dirty") != "true") refuse("invalid source_dirty flag");
    for (const auto* key : {"source_revision", "proof_baseline_revision", "universal_launcher_revision", "universal_setup_revision"})
        if (!hex(values.at(key), 40)) refuse("invalid Windows product source revision");
    const auto pins = workspace_pins(snapshot.capture("release/index/workspace_lock.v1.toml"));
    if (pins.at("factorio_binding") != values.at("proof_baseline_revision") ||
        pins.at("universal_launcher") != values.at("universal_launcher_revision") || pins.at("universal_setup") != values.at("universal_setup_revision"))
        refuse("Windows product source pins disagree");
    identity.profile = "windows_product_x64"; identity.relative_path = "facman.resources";
    identity.source_revision = values.at("source_revision"); identity.manifest_sha256 = digest(raw);
    const auto& closure = snapshot.capture("manifest/hashes.sha256");
    identity.closure_sha256 = digest(closure); inventory = checksums(closure);
    std::vector<ComponentRecord> components; std::string detail;
    if (!parse_component_manifest(snapshot.capture("manifest/components.v1.json"), components, detail)) refuse(detail);
    std::set<std::string> names, destinations; bool resource = false, terminal = false, gui = false;
    for (const auto& component : components) {
        safe_relative(component.destination);
        if (!names.insert(component.name).second || !destinations.insert(lower(component.destination)).second) refuse("duplicate product component");
        auto found = inventory.find(component.destination);
        if (found == inventory.end() || found->second.sha256 != component.sha256) refuse("product component disagrees with closure");
        found->second.bytes = component.size; found->second.size_known = true;
        if (component.destination == identity.relative_path) {
            resource = component.source_target == "facman.resources" && component.runtime_role == "runtime_required";
        }
        if (component.destination == "bin/facman.exe") terminal = component.source_target == "facman_cli" && component.runtime_role == "runtime_required";
        if (component.destination == "FacMan.exe") gui = component.runtime_role == "runtime_required";
    }
    if (!resource || !terminal || !gui) refuse("Windows product resource/entrypoint roles are incomplete");
    if (!inventory.count("manifest/package.v1.toml") || !inventory.count("manifest/components.v1.json") ||
        !inventory.count("release/index/workspace_lock.v1.toml") || !inventory.count("manifest/build_info.v1.json")) refuse("Windows product metadata closure is incomplete");
    snapshot.verify_inventory(inventory, "manifest/hashes.sha256", identity.relative_path, false);
}
}
