// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "fl_workspace_migration_internal.h"

#include "fl_workspace_io_internal.h"
#include "fl_file_io.h"
#include "fl_json.h"
#include "fl_path_safety.h"
#include "fl_sha256.h"
#include "fl_system_services.h"

#include <algorithm>
#include <limits>
#include <system_error>
#include <utility>

namespace facman::workspace {
namespace fs = std::filesystem;
namespace json = facman::core::json;
using persistence_detail::parse_record;
using persistence_detail::write_new_durable;
namespace {

template <typename T>
Result<T> failure(std::string code, std::string message, const fs::path& path = {})
{
    return Result<T>::failure({
        std::move(code), std::move(message), facman::platform::path_to_utf8(path)});
}

std::string migration_journal_json(const MigrationJournal& journal)
{
    json::ArrayBuilder actions;
    for (const MigrationJournalAction& action : journal.actions) {
        json::ObjectBuilder item;
        item.add_string("kind", action.kind);
        item.add_string("source", action.source);
        item.add_string("target", action.target);
        item.add_string("source_sha256", action.source_sha256);
        item.add_string("target_sha256", action.target_sha256);
        actions.add_object(item);
    }
    json::ObjectBuilder document;
    document.add_string("schema", "facman.workspace_migration_journal.v1");
    document.add_string("migration_id", journal.id);
    document.add_string("state", journal.state);
    (void)document.add_unsigned_integer(
        "completed_actions", static_cast<std::uint64_t>(journal.completed_actions));
    document.add_array("actions", actions);
    return document.serialize() + "\n";
}

Result<std::string> journal_string(
    const json::Value& object,
    const char* key,
    const fs::path& path)
{
    const json::Value* value = object.find(key);
    if (value == nullptr || !value->is_string()) {
        return failure<std::string>(
            "workspace_migration_apply_unproven",
            std::string("migration journal string is missing: ") + key,
            path);
    }
    auto decoded = value->string_value();
    if (!decoded || decoded.value().empty()) {
        return failure<std::string>(
            "workspace_migration_apply_unproven",
            std::string("migration journal string is invalid: ") + key,
            path);
    }
    return decoded;
}

} // namespace

bool copy_migration_kind(const std::string& kind)
{
    return kind == "canonicalize_legacy_install_ref" ||
        kind == "canonicalize_legacy_instance_manifest";
}

std::string sha256_text(const std::string& text)
{
    return facman::base::sha256_hex_bytes(
        reinterpret_cast<const unsigned char*>(text.data()), text.size());
}

std::string root_identity_digest(
    const WorkspaceLayout& layout,
    const WorkspaceRootInspection& inspection)
{
    facman::platform::PathIdentity identity;
    if (inspection.root_authority) {
        identity = inspection.root_authority->identity();
    } else {
        std::error_code error;
        fs::path parent = layout.root().parent_path();
        if (parent.empty()) parent = fs::current_path(error);
        if (!error) (void)facman::platform::inspect_path_no_follow(parent, identity);
    }
    const std::string material =
        std::string(workspace_root_state_name(inspection.state)) + "\n" +
        facman::platform::path_to_utf8(inspection.canonical_root) + "\n" +
        std::to_string(identity.device) + ":" + std::to_string(identity.object) + ":" +
        std::to_string(static_cast<unsigned int>(identity.kind));
    return sha256_text(material);
}

std::string random_workspace_uuid()
{
    facman::platform::RandomIdGenerator random;
    std::string value = random.next("workspace");
    value = value.substr(value.find('-') + 1);
    value[12] = '4';
    value[16] = "89ab"[static_cast<unsigned char>(value[16]) % 4];
    return value.substr(0, 8) + "-" + value.substr(8, 4) + "-" +
        value.substr(12, 4) + "-" + value.substr(16, 4) + "-" + value.substr(20, 12);
}

fs::path migration_root(const WorkspaceLayout& layout)
{
    return layout.root() / "transactions" / "workspace-migrations";
}

fs::path migration_journal_path(const WorkspaceLayout& layout, const std::string& id)
{
    return migration_root(layout) / (id + ".workspace-migration.v1.json");
}

fs::path migration_data_root(const WorkspaceLayout& layout, const std::string& id)
{
    return migration_root(layout) / (id + ".data");
}

bool safe_relative_text(const fs::path& root, const fs::path& path, std::string& output)
{
    const fs::path normalized_root = root.lexically_normal();
    const fs::path normalized_path = path.lexically_normal();
    const fs::path relative = normalized_path.lexically_relative(normalized_root);
    if (relative.empty() || relative.is_absolute() || relative.has_root_name()) return false;
    for (const fs::path& segment : relative) {
        if (segment.empty() || segment == "." || segment == "..") return false;
    }
    output = relative.generic_u8string();
    return !output.empty() && output.find('\\') == std::string::npos &&
        output.find(':') == std::string::npos;
}

Result<fs::path> resolve_relative_path(
    const WorkspaceLayout& layout,
    const std::string& value)
{
    if (value.empty() || value.find('\\') != std::string::npos ||
        value.find(':') != std::string::npos) {
        return failure<fs::path>(
            "workspace_migration_apply_unproven",
            "migration journal contains a non-portable path");
    }
    const fs::path relative = facman::platform::path_from_utf8(value);
    if (relative.is_absolute() || relative.has_root_name() ||
        relative.lexically_normal() != relative) {
        return failure<fs::path>(
            "workspace_migration_apply_unproven",
            "migration journal path is not normalized and relative");
    }
    for (const fs::path& segment : relative) {
        if (segment.empty() || segment == "." || segment == "..") {
            return failure<fs::path>(
                "workspace_migration_apply_unproven",
                "migration journal path contains an unsafe segment");
        }
    }
    return Result<fs::path>::success((layout.root() / relative).lexically_normal());
}

Result<void> ensure_owned_directory(
    const WorkspaceRootInspection& authority,
    const fs::path& path)
{
    const auto before = authority.root_authority->validate_descendant(path, true);
    if (!before.ok()) return failure<void>(before.code, before.detail, path);
    std::error_code error;
    const fs::file_status status = fs::symlink_status(path, error);
    if (!error && fs::exists(status)) {
        if (!fs::is_directory(status)) {
            return failure<void>(
                "workspace_migration_apply_unproven",
                "migration state path is not a plain directory",
                path);
        }
    } else {
        error.clear();
        fs::create_directory(path, error);
        if (error) {
            return failure<void>("workspace_directory_create_failed", error.message(), path);
        }
    }
    const auto after = authority.root_authority->validate_descendant(path);
    if (!after.ok()) return failure<void>(after.code, after.detail, path);
    return Result<void>::success();
}

Result<void> write_replace_durable(const fs::path& path, const std::string& text)
{
    facman::platform::RandomIdGenerator random;
    const fs::path temporary = path.parent_path() /
        (path.filename().string() + ".next-" + random.next("migration"));
    facman::platform::DurableOutputFile output;
    auto status = output.create_exclusive(temporary, 1024ULL * 1024ULL);
    if (!status.ok()) return failure<void>(status.code, status.detail, temporary);
    if (output.write_at(0U, text.data(), text.size()) != text.size()) {
        output.close_without_flush();
        facman::platform::StableInputFile created;
        if (created.open_no_follow(temporary).ok()) {
            (void)facman::platform::remove_exact_object(temporary, created.identity());
        }
        return failure<void>(
            "workspace_record_write_failed", "short migration journal write", temporary);
    }
    status = output.flush_file_and_parent();
    if (!status.ok()) {
        output.close_without_flush();
        facman::platform::StableInputFile created;
        if (created.open_no_follow(temporary).ok()) {
            (void)facman::platform::remove_exact_object(temporary, created.identity());
        }
        return failure<void>(status.code, status.detail, temporary);
    }
    status = facman::platform::replace_existing_durable(temporary, path);
    if (!status.ok()) {
        facman::platform::StableInputFile created;
        if (created.open_no_follow(temporary).ok()) {
            (void)facman::platform::remove_exact_object(temporary, created.identity());
        }
        return failure<void>(status.code, status.detail, path);
    }
    return Result<void>::success();
}

Result<void> persist_journal(
    const WorkspaceLayout& layout,
    const MigrationJournal& journal,
    bool create)
{
    const fs::path path = migration_journal_path(layout, journal.id);
    const std::string text = migration_journal_json(journal);
    if (text.size() > 1024U * 1024U) {
        return failure<void>(
            "workspace_migration_apply_unproven",
            "migration journal exceeds its byte budget",
            path);
    }
    if (create) {
        auto written = write_new_durable(path, text);
        return written ? Result<void>::success() :
            failure<void>(written.error().code, written.error().message, path);
    }
    return write_replace_durable(path, text);
}

bool sha256_text_valid(const std::string& value)
{
    return value.size() == 64U &&
        std::all_of(value.begin(), value.end(), [](unsigned char ch) {
            return (ch >= '0' && ch <= '9') || (ch >= 'a' && ch <= 'f');
        });
}

Result<MigrationJournal> load_migration_journal(const fs::path& path)
{
    auto document = parse_record(path);
    if (!document) {
        return failure<MigrationJournal>(document.error().code, document.error().message, path);
    }
    auto schema = journal_string(document.value(), "schema", path);
    auto id = journal_string(document.value(), "migration_id", path);
    auto state = journal_string(document.value(), "state", path);
    if (!schema || !id || !state) {
        const auto& problem = !schema ? schema.error() : !id ? id.error() : state.error();
        return failure<MigrationJournal>(problem.code, problem.message, path);
    }
    std::string id_detail;
    if (schema.value() != "facman.workspace_migration_journal.v1" ||
        !facman::base::validate_identifier(id.value(), id_detail) ||
        path.filename() != id.value() + ".workspace-migration.v1.json" ||
        (state.value() != "planned" && state.value() != "applying" &&
         state.value() != "complete" && state.value() != "rolled_back" &&
         state.value() != "recovery_required")) {
        return failure<MigrationJournal>(
            "workspace_migration_apply_unproven",
            "migration journal identity, schema, or state is unsupported",
            path);
    }
    const json::Value* completed = document.value().find("completed_actions");
    const json::Value* actions = document.value().find("actions");
    if (completed == nullptr || !completed->is_number() ||
        actions == nullptr || !actions->is_array() ||
        actions->size() > kMaximumMigrationActions) {
        return failure<MigrationJournal>(
            "workspace_migration_apply_unproven",
            "migration journal action bounds are invalid",
            path);
    }
    auto completed_value = completed->unsigned_integer_value();
    if (!completed_value || completed_value.value() > actions->size() ||
        completed_value.value() > std::numeric_limits<std::size_t>::max()) {
        return failure<MigrationJournal>(
            "workspace_migration_apply_unproven",
            "migration journal completion index is invalid",
            path);
    }
    MigrationJournal journal;
    journal.id = id.take_value();
    journal.state = state.take_value();
    journal.completed_actions = static_cast<std::size_t>(completed_value.value());
    for (std::size_t index = 0U; index < actions->size(); ++index) {
        const json::Value* item = actions->at(index);
        if (item == nullptr || !item->is_object()) {
            return failure<MigrationJournal>(
                "workspace_migration_apply_unproven",
                "migration journal action is not an object",
                path);
        }
        auto kind = journal_string(*item, "kind", path);
        auto source = journal_string(*item, "source", path);
        auto target = journal_string(*item, "target", path);
        auto source_sha = journal_string(*item, "source_sha256", path);
        auto target_sha = journal_string(*item, "target_sha256", path);
        if (!kind || !source || !target || !source_sha || !target_sha ||
            !copy_migration_kind(kind.value()) ||
            !sha256_text_valid(source_sha.value()) ||
            !sha256_text_valid(target_sha.value())) {
            return failure<MigrationJournal>(
                "workspace_migration_apply_unproven",
                "migration journal action is unsupported or corrupt",
                path);
        }
        journal.actions.push_back({
            kind.take_value(), source.take_value(), target.take_value(),
            source_sha.take_value(), target_sha.take_value()});
    }
    return Result<MigrationJournal>::success(std::move(journal));
}

} // namespace facman::workspace
