// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT
#include "fl_product_resource_internal.h"
namespace facman::package::resource_detail {
namespace {
void boolean(const json::Value& value, const char* key, bool expected)
{
    const auto* field = value.find(key);
    if (!field || !field->is_bool() || field->bool_value().value() != expected) refuse(std::string("product flag mismatch: ") + key);
}
}
void unix_manifest(ProductResourceSnapshot& snapshot, ProductResourceIdentity& identity, Inventory& inventory, bool macos)
{
    const std::string prefix = macos ? "Contents/Resources/manifest/" : "share/facman/manifest/";
    const std::string manifest_path = prefix + "product-stage.v1.json", closure_path = prefix + "MANIFEST.sha256";
    const auto& raw = snapshot.capture(manifest_path); const auto parsed = document(raw);
    fields(parsed, {"schema", "product_id", "product_name", "version", "platform", "architecture", "source_revision", "source_tree",
        "source_dirty", "entrypoints", "terminal_modes", "provider_closure", "portable", "app_installation_mutation",
        "factorio_mutation", "signed", "notarized", "files", "stage_digest"});
    if (text(parsed, "schema") != "facman.platform_product_stage.v1" || text(parsed, "product_id") != "facman" ||
        text(parsed, "product_name") != "FacMan" || text(parsed, "architecture") != "x64" ||
        text(parsed, "platform") != (macos ? "macos" : "linux") || text(parsed, "provider_closure") != "static_in_facman_terminal_host" || text(parsed, "version").empty())
        refuse("Unix product identity mismatch");
    for (const auto* flag : {"app_installation_mutation", "factorio_mutation", "signed", "notarized"}) boolean(parsed, flag, false);
    boolean(parsed, "portable", true);
    const auto* dirty = parsed.find("source_dirty"); if (!dirty || !dirty->is_bool()) refuse("invalid product dirty flag");
    identity.source_revision = text(parsed, "source_revision"); identity.source_tree = text(parsed, "source_tree");
    if (!hex(identity.source_revision, 40) || !hex(identity.source_tree, 40)) refuse("invalid Unix product source identity");
    const auto* entrypoints = parsed.find("entrypoints");
    if (!entrypoints) refuse("missing product entrypoints"); fields(*entrypoints, {"gui", "cli", "tui"});
    const std::string cli = macos ? "FacMan.app/Contents/Helpers/facman" : "facman";
    const std::string gui = macos ? "FacMan.app/Contents/MacOS/FacMan" : "FacMan";
    if (text(*entrypoints, "cli") != cli || text(*entrypoints, "tui") != cli || text(*entrypoints, "gui") != gui) refuse("Unix product entrypoints differ");
    const auto* modes = parsed.find("terminal_modes");
    const char* expected_modes[] = {"human_cli", "json", "rpc", "tui"};
    if (!modes || !modes->is_array() || modes->size() != 4) refuse("Unix terminal modes differ");
    for (std::size_t index = 0; index < 4; ++index) {
        auto mode = modes->at(index)->string_value(); if (!mode || mode.value() != expected_modes[index]) refuse("Unix terminal mode differs");
    }
    const auto* files = parsed.find("files");
    if (!files || !files->is_array() || files->size() == 0 || files->size() > 65536) refuse("invalid Unix product inventory");
    auto canonical = json::canonical_integer_ascii_json(*files);
    if (!canonical) refuse("cannot canonicalize product inventory");
    const auto stage_digest = digest(canonical.value());
    if (stage_digest != text(parsed, "stage_digest")) refuse("Unix stage inventory digest mismatch");
    const auto& raw_closure = snapshot.capture(closure_path); inventory = checksums(raw_closure, !macos);
    identity.profile = macos ? "macos_product_x64" : "linux_product_x64";
    identity.relative_path = macos ? "Contents/Resources/facman.resources" : "share/facman/facman.resources";
    identity.manifest_sha256 = digest(raw); identity.closure_sha256 = digest(raw_closure);
    std::set<std::string> paths, folded; std::string previous;
    for (std::size_t index = 0; index < files->size(); ++index) {
        const auto& item = *files->at(index); fields(item, {"path", "bytes", "sha256", "mode"});
        const auto path = text(item, "path"); safe_relative(path);
        if (path == manifest_path || path == closure_path || (!previous.empty() && path <= previous) || !paths.insert(path).second || !folded.insert(macos ? lower(path) : path).second)
            refuse("unordered, duplicate or self-referential Unix inventory");
        previous = path;
        const auto digest_value = text(item, "sha256"); const auto bytes = number(item, "bytes"), mode = number(item, "mode");
        const auto found = inventory.find(path);
        if (!hex(digest_value, 64) || mode > 0777 || found == inventory.end() || found->second.sha256 != digest_value) refuse("Unix inventory/closure mismatch");
        found->second = Record {digest_value, bytes, mode, true, true};
    }
    const auto manifest = inventory.find(manifest_path);
    if (inventory.size() != paths.size() + 1 || manifest == inventory.end() || manifest->second.sha256 != identity.manifest_sha256)
        refuse("Unix metadata is not closed by the final checksum inventory");
    if (!paths.count(identity.relative_path) || !paths.count(macos ? "Contents/Helpers/facman" : "facman") ||
        !paths.count(macos ? "Contents/MacOS/FacMan" : "FacMan")) refuse("Unix product entrypoint/resource inventory is incomplete");
    for (const auto& entrypoint : {macos ? "Contents/Helpers/facman" : "facman", macos ? "Contents/MacOS/FacMan" : "FacMan"})
        if ((inventory.at(entrypoint).mode & 0111U) == 0) refuse("Unix product entrypoint is not executable");
    snapshot.verify_inventory(inventory, closure_path, identity.relative_path, true);
}
}
