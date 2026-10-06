// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT
#include "fl_transaction_pack_import.h"
#include "fl_archive.h"
#include "fl_directory_publication.h"
#include "fl_file_io.h"
#include "fl_path_safety.h"
#include "fl_sha256.h"
#include <algorithm>
#include <array>
#include <map>
#include <set>
namespace facman::transaction {
namespace fs = std::filesystem;
namespace {
const std::set<std::string> directories {"config", "mods", "saves", "scenarios", "script-output",
    "logs", "crash", "exports", "cache", "locks"};
const std::set<std::string> required {"instance.v1.json", "config/config.ini", "mods/modset-lock.v1.json",
    "modset-lock.v1.json", "modpack-manifest.v1.json", "modpack-import.v1.json"};
bool refuse(std::string& detail, const std::string& message) { detail = message; return false; }
bool file_matches(const facman::platform::StableDirectoryObject& directory, const fs::path& leaf,
    const ExpectedFile& expected, std::string& detail)
{
    facman::platform::StableInputFile file;
    auto status = directory.open_child_file_no_follow_pinned(leaf, file);
    if (!status.ok() || !file.identity().regular_file || file.identity().link_count != 1U ||
        file.size() != expected.size) return refuse(detail, "Import file identity or size differs: " + expected.path.str());
    facman::base::Sha256Hasher hash;
    std::array<unsigned char, 65536> block {};
    for (std::uint64_t offset = 0; offset < file.size();) {
        const auto count = static_cast<std::size_t>(std::min<std::uint64_t>(block.size(), file.size() - offset));
        if (file.read_at(offset, block.data(), count) != count) return refuse(detail, "Import file short read");
        hash.update(block.data(), count); offset += count;
    }
    return (hash.finish() == expected.sha256.str() && file.revalidate_path().ok() && directory.revalidate().ok()) ||
        refuse(detail, "Import file changed: " + expected.path.str());
}
bool marker(const facman::platform::StableDirectoryObject& root, const char* leaf,
    const std::string& bytes, bool remove, std::string& detail,
    const facman::platform::FileIdentity* captured = nullptr)
{
    facman::platform::PathIdentity identity;
    auto status = facman::platform::inspect_path_no_follow(root.path() / leaf, identity);
    if (!status.ok()) return refuse(detail, status.detail);
    if (!identity.exists) return true;
    if (identity.reparse_or_link || identity.kind != facman::platform::PathObjectKind::regular_file)
        return refuse(detail, "Import marker is not a plain file");
    facman::platform::StableInputFile file;
    status = root.open_child_file_no_follow_pinned(leaf, file);
    if (!status.ok() || !file.identity().regular_file || file.identity().link_count != 1U || file.size() != bytes.size() ||
        file.identity().device != identity.device || file.identity().object != identity.object ||
        (captured && !file.identity().unchanged(*captured)))
        return refuse(detail, "Import marker is not a bound plain file");
    std::string actual(bytes.size(), '\0');
    if (file.read_at(0, actual.data(), actual.size()) != actual.size() || actual != bytes ||
        !file.revalidate_path().ok()) return refuse(detail, "Import marker bytes differ");
    const auto expected = file.identity();
    file = facman::platform::StableInputFile();
    if (!remove) return true;
    status = root.remove_child_file_no_follow_if_matches(leaf, expected,
        [&](const facman::platform::StableInputFile& held) {
            std::string current(bytes.size(), '\0');
            return held.size() == bytes.size() && held.read_at(0, current.data(), current.size()) == current.size() && current == bytes;
        });
    return status.ok() || refuse(detail, status.detail);
}
bool transaction_marker(const facman::platform::StableDirectoryObject& root,
    const Record& record, bool required_marker, bool remove, std::string& detail)
{
    facman::platform::PathIdentity identity;
    auto status = facman::platform::inspect_path_no_follow(root.path() / transaction_staging_marker_name(), identity);
    if (!status.ok()) return refuse(detail, status.detail);
    if (!identity.exists) return !required_marker || refuse(detail, "Import transaction marker is missing");
    if (identity.reparse_or_link || identity.kind != facman::platform::PathObjectKind::regular_file)
        return refuse(detail, "Import transaction marker is not a plain file");
    facman::platform::StableInputFile file;
    status = root.open_child_file_no_follow_pinned(transaction_staging_marker_name(), file);
    if (!status.ok() || !file.identity().regular_file || file.identity().link_count != 1U || file.size() > 65536U ||
        file.identity().device != identity.device || file.identity().object != identity.object)
        return refuse(detail, "Import transaction marker identity differs");
    if (!verify_staging_ownership(record, root.path(), detail)) return false;
    std::string bytes(static_cast<std::size_t>(file.size()), '\0');
    if (file.read_at(0, bytes.data(), bytes.size()) != bytes.size() || !file.revalidate_path().ok())
        return refuse(detail, "Import transaction marker changed");
    const auto captured = file.identity();
    file = facman::platform::StableInputFile();
    return marker(root, transaction_staging_marker_name(), bytes, remove, detail, &captured);
}
bool paths_bound(const fs::path& workspace, const Record& record, std::string& detail)
{
    auto id = facman::core::InstanceId::parse(record.target.filename().u8string());
    return (id && record.schema_version == 2U && record.command_id == "modsets.import" &&
        record.commit_strategy == "modpack_instance_no_replace_v1" && record.staging_roots.size() == 1U &&
        record.target == workspace / "instances" / id.value().str() &&
        record.staging_roots.front() == workspace / (".facman-pack-import-" + id.value().str()) &&
        !record.effect_parent_identity.empty() && !record.effect_file_identity.empty()) ||
        refuse(detail, "Import journal paths or ownership are not bound to this workspace");
}
}
bool verify_pack_import_tree(const Record& record, const fs::path& path, bool published, std::string& detail)
{
    std::string links;
    if (facman::base::path_crosses_link_or_reparse_point(path, links)) return refuse(detail, links);
    facman::platform::StableDirectoryObject root;
    auto status = root.open_no_follow_for_publication_verification(path);
    if (!status.ok() || directory_effect_identity(root) != record.effect_file_identity)
        return refuse(detail, "Import directory differs from the journaled object");
    std::map<std::string, const ExpectedFile*> files;
    std::uint64_t total = 0;
    for (const auto& item : record.expected_files) {
        const auto& relative = item.path.str();
        const fs::path parsed = fs::u8path(relative);
        const bool allowed = required.count(relative) || (parsed.parent_path() == "mods" &&
            (parsed.extension() == ".zip" || parsed.filename() == "mod-list.json" || parsed.filename() == "mod-settings.dat"));
        if (!allowed || item.size > facman::archive::Limits().maximum_entry_expanded_bytes ||
            total > facman::archive::Limits().maximum_total_expanded_bytes - item.size ||
            !files.emplace(relative, &item).second) return refuse(detail, "Import inventory is unsafe or duplicated");
        total += item.size;
    }
    if (files.size() > 10000U) return refuse(detail, "Import inventory exceeds its bound");
    for (const auto& item : required) if (!files.count(item)) return refuse(detail, "Import inventory is incomplete");
    std::set<std::string> found_files, found_dirs;
    auto scan = [&](const facman::platform::StableDirectoryObject& directory, const std::string& prefix) {
        std::vector<fs::path> names;
        if (!directory.list_child_names_bounded(10010U, names).ok()) return false;
        for (const auto& leaf : names) {
            const auto relative = prefix + leaf.u8string();
            if (prefix.empty() && directories.count(relative)) { found_dirs.insert(relative); continue; }
            if (prefix.empty() && (relative == facman::archive::owned_staging_marker_name() ||
                    relative == transaction_staging_marker_name())) continue;
            const auto expected = files.find(relative);
            if (expected == files.end() || !file_matches(directory, leaf, *expected->second, detail))
                return refuse(detail, detail.empty() ? "Unbound import inventory entry: " + relative : detail);
            found_files.insert(relative);
        }
        return directory.revalidate().ok();
    };
    if (!scan(root, "")) return false;
    for (const auto& name : directories) {
        facman::platform::StableDirectoryObject child;
        if (!root.open_child_directory_no_follow(name, child).ok() || !scan(child, name + "/"))
            return refuse(detail, detail.empty() ? "Import directory inventory differs: " + name : detail);
    }
    if (found_files.size() != files.size() || found_dirs != directories)
        return refuse(detail, "Import inventory has missing entries");
    // Published markers may already have been removed by a prior finalization.
    if (!transaction_marker(root, record, !published, false, detail)) return false;
    return marker(root, facman::archive::owned_staging_marker_name(), "schema=facman.archive_staging.v1\n", false, detail) &&
        root.revalidate().ok();
}
bool finalize_pack_import(const Record& record, std::string& detail)
{
    if (!verify_pack_import_tree(record, record.target, true, detail)) return false;
    facman::platform::StableDirectoryObject root;
    if (!root.open_no_follow(record.target).ok() || directory_effect_identity(root) != record.effect_file_identity)
        return refuse(detail, "Import finalization directory differs from the journaled object");
    if (!marker(root, facman::archive::owned_staging_marker_name(), "schema=facman.archive_staging.v1\n", true, detail)) return false;
    if (!transaction_marker(root, record, false, true, detail)) return false;
    return root.revalidate().ok();
}
bool recover_pack_import(const fs::path& workspace, Record& record, std::string& detail)
{
    if (std::find(record.completed_steps.begin(), record.completed_steps.end(), "pack_inventory_bound") == record.completed_steps.end())
        return refuse(detail, "Incomplete extraction is retained; no complete bound instance is available to resume");
    if (!paths_bound(workspace, record, detail) || !verify_pack_import_install(record, workspace, detail)) return false;
    facman::platform::StableDirectoryObject parent;
    if (!parent.open_no_follow(record.target.parent_path()).ok() ||
        directory_effect_identity(parent) != record.effect_parent_identity)
        return refuse(detail, "Import destination parent differs from its journaled object");
    facman::platform::PathIdentity target, staging;
    if (!facman::platform::inspect_path_no_follow(record.target, target).ok() ||
        !facman::platform::inspect_path_no_follow(record.staging_roots.front(), staging).ok())
        return refuse(detail, "Import publication paths cannot be inspected");
    if (target.exists && staging.exists) return refuse(detail, "Both target and staging exist; all data retained");
    if (!target.exists) {
        if (!staging.exists || !verify_pack_import_tree(record, record.staging_roots.front(), false, detail)) return false;
        if (!advance(workspace, record, "recovery_required", "pack_resume_intent_verified", detail) ||
            !parent.revalidate().ok() || !verify_pack_import_tree(record, record.staging_roots.front(), false, detail)) return false;
        const auto published = facman::platform::publish_directory_no_replace_if_matches(record.staging_roots.front(), record.target,
            record.effect_file_identity, record.effect_parent_identity,
            [&](std::string& error) { return verify_pack_import_tree(record, record.staging_roots.front(), false, error) &&
                verify_pack_import_install(record, workspace, error); });
        if (!published.ok()) return refuse(detail, published.code + ": " + published.detail);
    }
    if (!verify_pack_import_tree(record, record.target, true, detail)) return false;
    if (record.state != State::recovery_required &&
        !advance(workspace, record, "recovery_required", "pack_publication_verified", detail)) return false;
    if (!finalize_pack_import(record, detail) || !complete(workspace, record, detail)) return false;
    record.recovery_actions.push_back("verified_imported_instance_complete");
    return true;
}
}
