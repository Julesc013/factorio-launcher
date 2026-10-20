// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT
#include "fl_transaction_pack_import.h"
#include "fl_file_io.h"
#include "fl_json.h"
#include "fl_path_safety.h"
#include "fl_sha256.h"
#include "fl_workspace_store.h"
#include <algorithm>
#include <array>
#include <set>
namespace facman::transaction {
namespace fs = std::filesystem;
namespace json = facman::core::json;
namespace {
std::string text(const json::Value& object, const char* key)
{
    const auto* value = object.find(key);
    return value && value->string_value() ? value->string_value().value() : std::string();
}
bool hash_file(const fs::path& path, std::string& digest, std::uint64_t& size, std::string& detail)
{
    if (facman::base::path_crosses_link_or_reparse_point(path, detail)) return false;
    facman::platform::StableInputFile input;
    auto status = input.open_no_follow_pinned(path);
    if (!status.ok() || input.identity().link_count != 1U || input.size() > 16ULL * 1024ULL * 1024ULL) {
        detail = "Import install metadata must be a bounded plain file"; return false;
    }
    facman::base::Sha256Hasher hash;
    std::array<unsigned char, 65536> block {};
    size = input.size();
    for (std::uint64_t offset = 0; offset < size;) {
        const auto count = static_cast<std::size_t>(std::min<std::uint64_t>(block.size(), size - offset));
        if (input.read_at(offset, block.data(), count) != count) { detail = "Import install metadata short read"; return false; }
        hash.update(block.data(), count); offset += count;
    }
    digest = hash.finish();
    return input.revalidate_path().ok();
}
}
bool bind_pack_import_install(Record& record, const fs::path& workspace, const std::string& install_id,
    const std::vector<fs::path>& metadata, std::string& detail)
{
    auto id = facman::core::InstallId::parse_legacy(install_id);
    if (!id) { detail = "Import install id is invalid"; return false; }
    auto loaded = facman::workspace::InstallRepository(facman::workspace::WorkspaceLayout(workspace)).load(id.value());
    if (!loaded || metadata.size() > 4096U) { detail = "Import registered install is unavailable"; return false; }
    facman::platform::StableDirectoryObject root;
    if (!root.open_no_follow(loaded.value().root).ok()) { detail = "Import install root is unsafe"; return false; }
    std::vector<fs::path> paths {loaded.value().source_path};
    paths.insert(paths.end(), metadata.begin(), metadata.end());
    json::ArrayBuilder files;
    for (const auto& path : paths) {
        std::string sha;
        std::uint64_t size = 0;
        if (!hash_file(path, sha, size, detail)) return false;
        json::ObjectBuilder file;
        file.add_string("path", facman::platform::path_to_utf8(path));
        file.add_string("sha256", sha);
        (void)file.add_unsigned_integer("size", size);
        files.add_object(file);
    }
    json::ObjectBuilder context;
    context.add_string("schema", "facman.modpack_import_install.v1");
    context.add_string("install_id", install_id);
    context.add_string("root_identity", directory_effect_identity(root));
    context.add_array("files", files);
    const auto binding = context.serialize();
    if (binding.size() > 128U * 1024U) { detail = "Import install binding exceeds the journal budget"; return false; }
    record.operation_context = binding;
    return verify_pack_import_install(record, workspace, detail);
}
bool verify_pack_import_install(const Record& record, const fs::path& workspace, std::string& detail)
{
    auto document = json::parse(record.operation_context);
    if (!document || text(document.value(), "schema") != "facman.modpack_import_install.v1") {
        detail = "Import installation binding is malformed"; return false;
    }
    auto id = facman::core::InstallId::parse_legacy(text(document.value(), "install_id"));
    if (!id) { detail = "Import install id is invalid"; return false; }
    auto loaded = facman::workspace::InstallRepository(facman::workspace::WorkspaceLayout(workspace)).load(id.value());
    if (!loaded || record.sources.size() != 2U || loaded.value().root != record.sources[1]) {
        detail = "Import installation binding no longer matches registration"; return false;
    }
    const auto& install = loaded.value();
    if (!fs::is_regular_file(install.executable) ||
        facman::base::path_crosses_link_or_reparse_point(install.executable, detail)) return false;
    facman::platform::StableDirectoryObject root;
    if (!root.open_no_follow(install.root).ok() || directory_effect_identity(root) != text(document.value(), "root_identity")) {
        detail = "Import installation directory changed"; return false;
    }
    const auto* files = document.value().find("files");
    if (!files || !files->is_array() || files->size() == 0U || files->size() > 4097U) {
        detail = "Import installation inventory is unbound"; return false;
    }
    std::set<fs::path> seen;
    for (std::size_t i = 0; i < files->size(); ++i) {
        const auto* file = files->at(i);
        const auto path = facman::platform::path_from_utf8(text(*file, "path"));
        const bool metadata = path.filename() == "info.json" && path.parent_path().parent_path() == install.root / "data";
        const auto* expected_size = file->find("size");
        if ((i == 0U ? path != install.source_path : !metadata) || !seen.insert(path).second ||
            !expected_size || !expected_size->unsigned_integer_value()) {
            detail = "Import install inventory path is not a registered source or built-in metadata"; return false;
        }
        std::string sha;
        std::uint64_t size = 0;
        if (!hash_file(path, sha, size, detail) || sha != text(*file, "sha256") ||
            size != expected_size->unsigned_integer_value().value()) {
            detail = "Import install registration or built-in metadata changed"; return false;
        }
    }
    return root.revalidate().ok();
}
}
