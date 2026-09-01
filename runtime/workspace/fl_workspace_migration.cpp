// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "fl_workspace_io_internal.h"
#include "fl_workspace_migration_internal.h"

#include "fl_file_io.h"
#include "fl_json.h"
#include "fl_local_operation_lock.h"
#include "fl_path_safety.h"
#include "fl_sha256.h"
#include "fl_system_services.h"
#include "fl_workspace_root_authority.h"

#include <algorithm>
#include <limits>
#include <system_error>
#include <utility>
#include <vector>

namespace facman::workspace {
namespace fs = std::filesystem;
namespace json = facman::core::json;
using persistence_detail::optional_string;
using persistence_detail::parse_record;
using persistence_detail::read_bounded;
using persistence_detail::required_string;
using persistence_detail::write_new_durable;
namespace {

template <typename T>
Result<T> failure(std::string code, std::string message, const fs::path& path = {})
{
    return Result<T>::failure({std::move(code), std::move(message), facman::platform::path_to_utf8(path)});
}

} // namespace

namespace {

constexpr std::size_t kMaximumMigrationActions = 256U;
constexpr std::uint64_t kMaximumMigrationBytes = 64ULL * 1024ULL * 1024ULL;

struct PreparedMigrationAction {
    MigrationAction action;
    std::string source_text;
    std::string target_text;
    std::string source_sha256;
    std::string target_sha256;
    fs::path source_backup;
    fs::path target_payload;
};

struct MigrationJournalAction {
    std::string kind;
    std::string source;
    std::string target;
    std::string source_sha256;
    std::string target_sha256;
};

struct MigrationJournal {
    std::string id;
    std::string state;
    std::size_t completed_actions = 0U;
    std::vector<MigrationJournalAction> actions;
};

bool copy_migration_kind(const std::string& kind)
{
    return kind == "canonicalize_legacy_install_ref" ||
        kind == "canonicalize_legacy_instance_manifest";
}

bool copy_migration_plan(const std::vector<MigrationAction>& actions)
{
    return std::all_of(actions.begin(), actions.end(), [](const MigrationAction& action) {
        return copy_migration_kind(action.kind) && action.source != action.target &&
            action.backup_required && action.journal_required;
    });
}

std::string sha256_text(const std::string& text)
{
    return facman::base::sha256_hex_bytes(
        reinterpret_cast<const unsigned char*>(text.data()), text.size());
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
        if (error) return failure<void>("workspace_directory_create_failed", error.message(), path);
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

Result<void> persist_journal(
    const WorkspaceLayout& layout,
    const MigrationJournal& journal,
    bool create)
{
    const fs::path path = migration_journal_path(layout, journal.id);
    const std::string text = migration_journal_json(journal);
    if (text.size() > 1024U * 1024U) {
        return failure<void>(
            "workspace_migration_apply_unproven", "migration journal exceeds its byte budget", path);
    }
    if (create) {
        auto written = write_new_durable(path, text);
        return written ? Result<void>::success() :
            failure<void>(written.error().code, written.error().message, path);
    }
    return write_replace_durable(path, text);
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

bool sha256_text_valid(const std::string& value)
{
    return value.size() == 64U &&
        std::all_of(value.begin(), value.end(), [](unsigned char ch) {
            return (ch >= '0' && ch <= '9') || (ch >= 'a' && ch <= 'f');
        });
}

Result<MigrationJournal> load_migration_journal(
    const fs::path& path)
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
        journal.actions.push_back({kind.take_value(), source.take_value(), target.take_value(),
            source_sha.take_value(), target_sha.take_value()});
    }
    return Result<MigrationJournal>::success(std::move(journal));
}

Result<void> validate_legacy_install_document(
    const fs::path& source,
    const std::string& expected_id)
{
    auto document = parse_record(source);
    if (!document) return failure<void>(document.error().code, document.error().message, source);
    auto schema = required_string(document.value(), "schema", source);
    auto stored_id = required_string(document.value(), "install_id", source);
    auto root = required_string(document.value(), "root", source);
    if (!root) root = required_string(document.value(), "app_dir", source);
    if (!schema || !stored_id || !root) {
        const auto& problem = !schema ? schema.error() : !stored_id ? stored_id.error() : root.error();
        return failure<void>(problem.code, problem.message, source);
    }
    if ((schema.value() != "factorio.install_ref.v1" &&
         schema.value() != "usk.installed_state.v1") ||
        stored_id.value() != expected_id) {
        return failure<void>(
            schema.value() != "factorio.install_ref.v1" &&
                    schema.value() != "usk.installed_state.v1" ?
                "workspace_record_future_or_unknown_schema" : "workspace_record_id_mismatch",
            schema.value() != "factorio.install_ref.v1" &&
                    schema.value() != "usk.installed_state.v1" ?
                schema.value() : stored_id.value(),
            source);
    }
    return Result<void>::success();
}

Result<std::string> canonical_instance_manifest(
    const fs::path& source,
    const std::string& expected_id)
{
    auto document = parse_record(source);
    if (!document) return failure<std::string>(document.error().code, document.error().message, source);
    const std::string current_schema = optional_string(document.value(), "schema", "factorio.instance.legacy");
    if (current_schema != "factorio.instance.legacy" && current_schema != "factorio.instance.v1") {
        return failure<std::string>(
            "workspace_record_future_or_unknown_schema", current_schema, source);
    }
    auto stored_id = required_string(document.value(), "instance_id", source);
    auto install_ref = required_string(document.value(), "install_ref", source);
    if (!stored_id || !install_ref) {
        const auto& problem = !stored_id ? stored_id.error() : install_ref.error();
        return failure<std::string>(problem.code, problem.message, source);
    }
    if (stored_id.value() != expected_id) {
        return failure<std::string>(
            "workspace_record_id_mismatch", stored_id.value(), source);
    }
    auto parsed_install = InstallId::parse_legacy(install_ref.value());
    if (!parsed_install) {
        return failure<std::string>(
            parsed_install.error().code, parsed_install.error().message, source);
    }
    json::ObjectBuilder output;
    output.add_string("schema", "factorio.instance.v1");
    for (const std::string& key : document.value().object_keys()) {
        if (key == "schema") continue;
        const json::Value* value = document.value().find(key);
        if (value == nullptr || !output.add_value(key, *value)) {
            return failure<std::string>(
                "workspace_manifest_invalid", "legacy instance contains duplicate fields", source);
        }
    }
    return Result<std::string>::success(output.serialize() + "\n");
}

Result<PreparedMigrationAction> prepare_copy_action(
    const WorkspaceLayout& layout,
    const WorkspaceRootInspection& authority,
    const MigrationAction& action)
{
    if (!copy_migration_kind(action.kind) || action.source == action.target) {
        return failure<PreparedMigrationAction>(
            "workspace_migration_action_unsupported",
            "only deterministic legacy-record canonicalization is enabled");
    }
    const auto source_safe = authority.root_authority->validate_descendant(action.source);
    const auto target_safe = authority.root_authority->validate_descendant(action.target, true);
    if (!source_safe.ok() || !target_safe.ok()) {
        const auto& problem = !source_safe.ok() ? source_safe : target_safe;
        return failure<PreparedMigrationAction>(problem.code, problem.detail, action.source);
    }
    facman::platform::PathIdentity source_identity;
    facman::platform::PathIdentity target_identity;
    auto status = facman::platform::inspect_path_no_follow(action.source, source_identity);
    if (!status.ok() || !source_identity.exists || source_identity.reparse_or_link ||
        source_identity.kind != facman::platform::PathObjectKind::regular_file) {
        return failure<PreparedMigrationAction>(
            "workspace_migration_conflict",
            status.ok() ? "migration source is not a plain regular file" : status.detail,
            action.source);
    }
    status = facman::platform::inspect_path_no_follow(action.target, target_identity);
    if (!status.ok() || target_identity.exists) {
        return failure<PreparedMigrationAction>(
            "workspace_migration_conflict",
            status.ok() ? "migration target already exists" : status.detail,
            action.target);
    }
    auto source_text = read_bounded(action.source);
    if (!source_text) {
        return failure<PreparedMigrationAction>(
            source_text.error().code, source_text.error().message, action.source);
    }
    std::string target_text = source_text.value();
    if (action.kind == "canonicalize_legacy_install_ref") {
        auto id = InstallId::parse_legacy(action.source.stem().string());
        if (!id) return failure<PreparedMigrationAction>(id.error().code, id.error().message, action.source);
        auto valid_document = validate_legacy_install_document(action.source, id.value().str());
        if (!valid_document) {
            return failure<PreparedMigrationAction>(
                valid_document.error().code, valid_document.error().message, action.source);
        }
        auto record = InstallRepository(layout).load(id.value());
        if (!record || !record.value().legacy_path ||
            record.value().source_path.lexically_normal() != action.source.lexically_normal()) {
            return failure<PreparedMigrationAction>(
                record ? "workspace_migration_conflict" : record.error().code,
                record ? "legacy install migration source did not resolve exactly" : record.error().message,
                action.source);
        }
    } else {
        auto id = InstanceId::parse_legacy(action.source.parent_path().filename().string());
        if (!id) return failure<PreparedMigrationAction>(id.error().code, id.error().message, action.source);
        auto record = InstanceRepository(layout).load(id.value());
        if (!record || !record.value().legacy_path ||
            record.value().source_path.lexically_normal() != action.source.lexically_normal()) {
            return failure<PreparedMigrationAction>(
                record ? "workspace_migration_conflict" : record.error().code,
                record ? "legacy instance migration source did not resolve exactly" : record.error().message,
                action.source);
        }
        auto canonical = canonical_instance_manifest(action.source, id.value().str());
        if (!canonical) {
            return failure<PreparedMigrationAction>(
                canonical.error().code, canonical.error().message, action.source);
        }
        target_text = canonical.take_value();
    }
    PreparedMigrationAction prepared;
    prepared.action = action;
    prepared.source_text = source_text.take_value();
    prepared.target_text = std::move(target_text);
    prepared.source_sha256 = sha256_text(prepared.source_text);
    prepared.target_sha256 = sha256_text(prepared.target_text);
    return Result<PreparedMigrationAction>::success(std::move(prepared));
}

Result<std::vector<MigrationAction>> collect_migration_actions(const WorkspaceLayout& layout)
{
    std::vector<MigrationAction> actions;
    std::error_code error;
    if (!fs::is_regular_file(layout.manifest(), error) || error) {
        actions.push_back({"create_workspace_identity", {}, layout.manifest(), false, true});
    } else {
        WorkspaceRepository repository(layout);
        auto workspace = repository.load();
        if (!workspace) return failure<std::vector<MigrationAction>>(workspace.error().code, workspace.error().message, layout.manifest());
        if (workspace.value().legacy_local_identity) {
            actions.push_back({"replace_literal_local_workspace_identity", layout.manifest(), layout.manifest(), true, true});
        }
    }

    error.clear();
    if (fs::is_directory(layout.legacy_installs_dir(), error) && !error) {
        for (const fs::directory_entry& entry : fs::directory_iterator(layout.legacy_installs_dir())) {
            const fs::file_status status = entry.symlink_status(error);
            if (error) return failure<std::vector<MigrationAction>>("workspace_migration_scan_failed", error.message(), entry.path());
            if (!fs::is_regular_file(status) || entry.path().extension() != ".json") continue;
            auto id = InstallId::parse_legacy(entry.path().stem().string());
            if (!id) return failure<std::vector<MigrationAction>>(id.error().code, id.error().message, entry.path());
            auto target = layout.install_ref(id.value());
            if (!target) return failure<std::vector<MigrationAction>>(target.error().code, target.error().message, entry.path());
            error.clear();
            if (!fs::exists(target.value(), error) && !error) {
                auto record = InstallRepository(layout).load(id.value());
                if (!record || !record.value().legacy_path ||
                    record.value().source_path.lexically_normal() != entry.path().lexically_normal()) {
                    return failure<std::vector<MigrationAction>>(
                        record ? "workspace_migration_conflict" : record.error().code,
                        record ? "legacy install migration source did not resolve exactly" : record.error().message,
                        entry.path());
                }
                actions.push_back({"canonicalize_legacy_install_ref", entry.path(), target.value(), true, true});
            }
        }
    }

    const fs::path instances = layout.root() / "instances";
    error.clear();
    if (fs::is_directory(instances, error) && !error) {
        for (const fs::directory_entry& entry : fs::directory_iterator(instances)) {
            const fs::file_status status = entry.symlink_status(error);
            if (error) return failure<std::vector<MigrationAction>>("workspace_migration_scan_failed", error.message(), entry.path());
            if (!fs::is_directory(status)) continue;
            const fs::path legacy = entry.path() / "instance.manifest.json";
            const fs::path current = entry.path() / "instance.v1.json";
            if (fs::is_regular_file(legacy, error) && !error && !fs::exists(current, error) && !error) {
                auto id = InstanceId::parse_legacy(entry.path().filename().string());
                if (!id) {
                    return failure<std::vector<MigrationAction>>(
                        id.error().code, id.error().message, entry.path());
                }
                auto record = InstanceRepository(layout).load(id.value());
                if (!record || !record.value().legacy_path ||
                    record.value().source_path.lexically_normal() != legacy.lexically_normal()) {
                    return failure<std::vector<MigrationAction>>(
                        record ? "workspace_migration_conflict" : record.error().code,
                        record ? "legacy instance migration source did not resolve exactly" : record.error().message,
                        legacy);
                }
                actions.push_back({"canonicalize_legacy_instance_manifest", legacy, current, true, true});
            }
            error.clear();
        }
    }
    std::sort(actions.begin(), actions.end(), [](const MigrationAction& left, const MigrationAction& right) {
        if (left.kind != right.kind) return left.kind < right.kind;
        return left.source.generic_string() < right.source.generic_string();
    });
    return Result<std::vector<MigrationAction>>::success(std::move(actions));
}

Result<MigrationReport> migration_report(const WorkspaceLayout& layout, const char* operation)
{
    auto actions = collect_migration_actions(layout);
    if (!actions) return failure<MigrationReport>(actions.error().code, actions.error().message);
    MigrationReport report;
    report.operation = operation;
    report.actions = actions.take_value();
    report.apply_enabled = copy_migration_plan(report.actions);
    if (report.apply_enabled && !report.actions.empty()) {
        auto authority = inspect_workspace_root(layout.root());
        auto workspace = WorkspaceRepository(layout).load();
        report.apply_enabled = authority && workspace &&
            authority.value().state == WorkspaceRootState::facman_owned &&
            authority.value().mutation_allowed &&
            authority.value().workspace_id == workspace.value().id.str();
    }
    return Result<MigrationReport>::success(std::move(report));
}

Result<WorkspaceRootInspection> owned_migration_authority(const WorkspaceLayout& layout)
{
    auto authority = inspect_workspace_root(layout.root());
    if (!authority || authority.value().state != WorkspaceRootState::facman_owned ||
        !authority.value().mutation_allowed || !authority.value().root_authority) {
        return failure<WorkspaceRootInspection>(
            "workspace_migration_conflict",
            "migration apply requires an already-owned workspace root",
            layout.root());
    }
    WorkspaceRepository repository(layout);
    auto workspace = repository.load();
    if (!workspace || workspace.value().id.str() != authority.value().workspace_id) {
        return failure<WorkspaceRootInspection>(
            workspace ? "workspace_migration_conflict" : workspace.error().code,
            workspace ? "workspace manifest and ownership marker identities differ" : workspace.error().message,
            layout.manifest());
    }
    auto stable = revalidate_workspace_root(authority.value());
    if (!stable) {
        return failure<WorkspaceRootInspection>(stable.error().code, stable.error().message, layout.root());
    }
    return authority;
}

bool recognized_migration_lock(const std::string& content)
{
    json::Limits limits;
    limits.maximum_bytes = 4096U;
    limits.maximum_depth = 4U;
    limits.maximum_nodes = 16U;
    limits.maximum_string_bytes = 1024U;
    auto document = json::parse(content, limits);
    if (!document || !document.value().is_object()) return false;
    const json::Value* schema = document.value().find("schema");
    const json::Value* identity = document.value().find("identity");
    if (schema == nullptr || identity == nullptr || !schema->is_string() ||
        !identity->is_string()) return false;
    auto schema_text = schema->string_value();
    auto identity_text = identity->string_value();
    return schema_text && identity_text &&
        schema_text.value() == "facman.workspace_migration_lock.v1" &&
        !identity_text.value().empty();
}

class ScopedMigrationLock {
public:
    Result<void> acquire(const fs::path& path)
    {
        auto result = lock_.create(path);
        if (result.code == facman::base::StableLockCode::exists) {
            facman::base::StableLocalLock stale;
            std::string content;
            auto opened = stale.open_existing(path, 4096U, content);
            if (opened.code == facman::base::StableLockCode::contended) {
                return failure<void>(
                    "workspace_migration_conflict",
                    "another workspace migration owns the migration lock",
                    path);
            }
            if (!opened.acquired() || !recognized_migration_lock(content)) {
                return failure<void>(
                    "workspace_migration_conflict",
                    "existing workspace migration lock is unsafe or unrecognized",
                    path);
            }
            std::string detail;
            if (!stale.remove_exact(detail)) {
                return failure<void>(
                    "workspace_migration_conflict", detail, path);
            }
            result = lock_.create(path);
        }
        if (!result.acquired()) {
            return failure<void>(
                "workspace_migration_conflict", result.detail, path);
        }
        json::ObjectBuilder document;
        document.add_string("schema", "facman.workspace_migration_lock.v1");
        document.add_string("identity", lock_.identity_text());
        std::string detail;
        if (!lock_.write_text(document.serialize() + "\n", detail)) {
            (void)lock_.remove_exact(detail);
            return failure<void>(
                "workspace_migration_conflict", detail, path);
        }
        acquired_ = true;
        return Result<void>::success();
    }

    Result<void> release()
    {
        if (!acquired_) return Result<void>::success();
        std::string detail;
        if (!lock_.remove_exact(detail)) {
            return failure<void>(
                "workspace_migration_conflict",
                "migration lock identity changed before release: " + detail,
                lock_.path());
        }
        acquired_ = false;
        return Result<void>::success();
    }

    ~ScopedMigrationLock()
    {
        if (!acquired_) return;
        std::string ignored;
        (void)lock_.remove_exact(ignored);
    }

private:
    facman::base::StableLocalLock lock_;
    bool acquired_ = false;
};

Result<void> verify_journal_action_shape(
    const WorkspaceLayout& layout,
    const MigrationJournalAction& action,
    fs::path& source,
    fs::path& target)
{
    auto source_path = resolve_relative_path(layout, action.source);
    auto target_path = resolve_relative_path(layout, action.target);
    if (!source_path || !target_path) {
        const auto& problem = !source_path ? source_path.error() : target_path.error();
        return failure<void>(problem.code, problem.message);
    }
    source = source_path.take_value();
    target = target_path.take_value();
    bool exact = false;
    if (action.kind == "canonicalize_legacy_install_ref") {
        auto id = InstallId::parse_legacy(source.stem().string());
        if (id) {
            auto expected_source = layout.legacy_install_ref(id.value());
            auto expected_target = layout.install_ref(id.value());
            exact = expected_source && expected_target &&
                expected_source.value().lexically_normal() == source.lexically_normal() &&
                expected_target.value().lexically_normal() == target.lexically_normal();
        }
    } else if (action.kind == "canonicalize_legacy_instance_manifest") {
        auto id = InstanceId::parse_legacy(source.parent_path().filename().string());
        if (id) {
            auto expected_source = layout.legacy_instance_manifest(id.value());
            auto expected_target = layout.instance_manifest(id.value());
            exact = expected_source && expected_target &&
                expected_source.value().lexically_normal() == source.lexically_normal() &&
                expected_target.value().lexically_normal() == target.lexically_normal();
        }
    }
    return exact ? Result<void>::success() : failure<void>(
        "workspace_migration_action_unsupported",
        "migration journal action does not match a known canonical path pair");
}

Result<std::string> expected_journal_target_payload(
    const MigrationJournalAction& action,
    const fs::path& source,
    const std::string& source_text)
{
    if (action.kind == "canonicalize_legacy_install_ref") {
        auto id = InstallId::parse_legacy(source.stem().string());
        if (!id) return failure<std::string>(id.error().code, id.error().message, source);
        auto valid = validate_legacy_install_document(source, id.value().str());
        if (!valid) return failure<std::string>(valid.error().code, valid.error().message, source);
        return Result<std::string>::success(source_text);
    }
    auto id = InstanceId::parse_legacy(source.parent_path().filename().string());
    if (!id) return failure<std::string>(id.error().code, id.error().message, source);
    return canonical_instance_manifest(source, id.value().str());
}

Result<void> resume_migration_journal(
    const WorkspaceLayout& layout,
    const WorkspaceRootInspection& authority,
    MigrationJournal& journal)
{
    if (journal.state == "complete" || journal.state == "rolled_back") {
        return Result<void>::success();
    }
    if (journal.state == "recovery_required") {
        return failure<void>(
            "workspace_migration_recovery_required",
            "a prior migration journal requires manual recovery",
            migration_journal_path(layout, journal.id));
    }
    const fs::path data_root = migration_data_root(layout, journal.id);
    const auto data_safe = authority.root_authority->validate_descendant(data_root);
    if (!data_safe.ok()) return failure<void>(data_safe.code, data_safe.detail, data_root);
    journal.state = "applying";
    auto persisted = persist_journal(layout, journal, false);
    if (!persisted) return persisted;
    for (std::size_t index = 0U; index < journal.actions.size(); ++index) {
        const MigrationJournalAction& action = journal.actions[index];
        fs::path source;
        fs::path target;
        auto shaped = verify_journal_action_shape(layout, action, source, target);
        if (!shaped) return shaped;
        const auto source_safe = authority.root_authority->validate_descendant(source);
        const auto target_safe = authority.root_authority->validate_descendant(target, true);
        if (!source_safe.ok() || !target_safe.ok()) {
            const auto& problem = !source_safe.ok() ? source_safe : target_safe;
            return failure<void>(problem.code, problem.detail, source);
        }
        const fs::path source_backup = data_root / (std::to_string(index) + ".source.json");
        const fs::path target_payload = data_root / (std::to_string(index) + ".target.json");
        auto current_source = read_bounded(source);
        auto backed_source = read_bounded(source_backup);
        auto payload = read_bounded(target_payload);
        auto expected_payload = current_source ? expected_journal_target_payload(
            action, source, current_source.value()) :
            failure<std::string>(
                "workspace_migration_conflict", "migration source is unreadable", source);
        if (!current_source || !backed_source || !payload ||
            !expected_payload || payload.value() != expected_payload.value() ||
            sha256_text(current_source ? current_source.value() : std::string {}) != action.source_sha256 ||
            sha256_text(backed_source ? backed_source.value() : std::string {}) != action.source_sha256 ||
            sha256_text(payload ? payload.value() : std::string {}) != action.target_sha256) {
            return failure<void>(
                "workspace_migration_conflict",
                "migration source, backup, or staged payload changed during recovery",
                source);
        }
        auto stable = revalidate_workspace_root(authority);
        if (!stable) return failure<void>(stable.error().code, stable.error().message, layout.root());
        facman::platform::PathIdentity target_identity;
        const auto target_status = facman::platform::inspect_path_no_follow(target, target_identity);
        if (!target_status.ok()) return failure<void>(target_status.code, target_status.detail, target);
        if (!target_identity.exists) {
            auto written = write_new_durable(target, payload.value());
            if (!written) return failure<void>(written.error().code, written.error().message, target);
        } else {
            if (target_identity.reparse_or_link ||
                target_identity.kind != facman::platform::PathObjectKind::regular_file) {
                return failure<void>(
                    "workspace_migration_conflict",
                    "migration recovery target is not a plain regular file",
                    target);
            }
            auto current_target = read_bounded(target);
            if (!current_target || sha256_text(current_target.value()) != action.target_sha256) {
                return failure<void>(
                    "workspace_migration_conflict",
                    "migration recovery refuses to replace a divergent target",
                    target);
            }
        }
        journal.completed_actions = index + 1U;
        persisted = persist_journal(layout, journal, false);
        if (!persisted) return persisted;
    }
    auto stable = revalidate_workspace_root(authority);
    if (!stable) return failure<void>(stable.error().code, stable.error().message, layout.root());
    journal.state = "complete";
    return persist_journal(layout, journal, false);
}

Result<void> recover_incomplete_migrations(
    const WorkspaceLayout& layout,
    const WorkspaceRootInspection& authority)
{
    std::error_code error;
    std::vector<fs::path> journals;
    for (fs::directory_iterator iterator(
             migration_root(layout), fs::directory_options::skip_permission_denied, error), end;
         iterator != end && !error; iterator.increment(error)) {
        const fs::file_status status = iterator->symlink_status(error);
        if (error) break;
        const std::string name = iterator->path().filename().string();
        const std::string suffix = ".workspace-migration.v1.json";
        if (fs::is_regular_file(status) && name.size() > suffix.size() &&
            name.compare(name.size() - suffix.size(), suffix.size(), suffix) == 0) {
            journals.push_back(iterator->path());
        }
    }
    if (error) return failure<void>("workspace_migration_scan_failed", error.message(), migration_root(layout));
    std::sort(journals.begin(), journals.end());
    for (const fs::path& path : journals) {
        auto journal = load_migration_journal(path);
        if (!journal) return failure<void>(journal.error().code, journal.error().message, path);
        auto resumed = resume_migration_journal(layout, authority, journal.value());
        if (!resumed) return resumed;
    }
    return Result<void>::success();
}

} // namespace

Result<MigrationReport> migration_detail::inspect(const WorkspaceLayout& layout)
{
    return migration_report(layout, "workspace.migration.inspect");
}

Result<MigrationReport> migration_detail::plan(const WorkspaceLayout& layout)
{
    return migration_report(layout, "workspace.migration.plan");
}

Result<MigrationReport> migration_detail::apply(const WorkspaceLayout& layout)
{
    const WorkspaceLayout& layout_ = layout;
    auto report = migration_report(layout_, "workspace.migration.apply");
    if (!report) return report;
    std::error_code state_error;
    const bool has_migration_state = fs::is_directory(migration_root(layout_), state_error) &&
        !state_error;
    if (report.value().actions.empty() && !has_migration_state) {
        report.value().apply_enabled = true;
        return report;
    }
    if (!report.value().apply_enabled && !report.value().actions.empty()) {
        return failure<MigrationReport>(
            "workspace_migration_action_unsupported",
            "migration apply supports only backup-and-journal-proven legacy record canonicalization");
    }

    auto authority = owned_migration_authority(layout_);
    if (!authority) {
        return failure<MigrationReport>(
            authority.error().code, authority.error().message, authority.error().path);
    }
    auto directory = ensure_owned_directory(authority.value(), layout_.root() / "transactions");
    if (!directory) {
        return failure<MigrationReport>(directory.error().code, directory.error().message, directory.error().path);
    }
    directory = ensure_owned_directory(authority.value(), migration_root(layout_));
    if (!directory) {
        return failure<MigrationReport>(directory.error().code, directory.error().message, directory.error().path);
    }

    ScopedMigrationLock migration_lock;
    auto locked = migration_lock.acquire(migration_root(layout_) / "workspace-migration.lock");
    if (!locked) {
        return failure<MigrationReport>(locked.error().code, locked.error().message, locked.error().path);
    }
    auto recovered = recover_incomplete_migrations(layout_, authority.value());
    if (!recovered) {
        return failure<MigrationReport>(
            recovered.error().code, recovered.error().message, recovered.error().path);
    }

    report = migration_report(layout_, "workspace.migration.apply");
    if (!report) return report;
    if (report.value().actions.empty()) {
        report.value().apply_enabled = true;
        auto released = migration_lock.release();
        return released ? report : failure<MigrationReport>(
            released.error().code, released.error().message, released.error().path);
    }
    if (!report.value().apply_enabled || report.value().actions.size() > kMaximumMigrationActions) {
        return failure<MigrationReport>(
            "workspace_migration_action_unsupported",
            "migration plan contains an unsupported or excessive action set");
    }

    std::vector<PreparedMigrationAction> prepared;
    prepared.reserve(report.value().actions.size());
    std::uint64_t total_bytes = 0U;
    for (const MigrationAction& action : report.value().actions) {
        auto item = prepare_copy_action(layout_, authority.value(), action);
        if (!item) {
            return failure<MigrationReport>(item.error().code, item.error().message, item.error().path);
        }
        const std::uint64_t source_size = static_cast<std::uint64_t>(item.value().source_text.size());
        const std::uint64_t target_size = static_cast<std::uint64_t>(item.value().target_text.size());
        if (source_size > kMaximumMigrationBytes || target_size > kMaximumMigrationBytes ||
            total_bytes > kMaximumMigrationBytes - source_size ||
            total_bytes + source_size > kMaximumMigrationBytes - target_size) {
            return failure<MigrationReport>(
                "workspace_migration_action_unsupported",
                "migration payload set exceeds its aggregate byte budget");
        }
        total_bytes += source_size + target_size;
        prepared.push_back(item.take_value());
    }
    auto stable = revalidate_workspace_root(authority.value());
    if (!stable) {
        return failure<MigrationReport>(stable.error().code, stable.error().message, layout_.root());
    }

    facman::platform::RandomIdGenerator random;
    MigrationJournal journal;
    journal.id = random.next("workspace-migration");
    journal.state = "planned";
    const fs::path data_root = migration_data_root(layout_, journal.id);
    directory = ensure_owned_directory(authority.value(), data_root);
    if (!directory) {
        return failure<MigrationReport>(directory.error().code, directory.error().message, directory.error().path);
    }
    for (std::size_t index = 0U; index < prepared.size(); ++index) {
        PreparedMigrationAction& item = prepared[index];
        item.source_backup = data_root / (std::to_string(index) + ".source.json");
        item.target_payload = data_root / (std::to_string(index) + ".target.json");
        auto source_backup = write_new_durable(item.source_backup, item.source_text);
        if (!source_backup) {
            return failure<MigrationReport>(
                source_backup.error().code, source_backup.error().message, item.source_backup);
        }
        auto target_payload = write_new_durable(item.target_payload, item.target_text);
        if (!target_payload) {
            return failure<MigrationReport>(
                target_payload.error().code, target_payload.error().message, item.target_payload);
        }
        std::string source_relative;
        std::string target_relative;
        if (!safe_relative_text(layout_.root(), item.action.source, source_relative) ||
            !safe_relative_text(layout_.root(), item.action.target, target_relative)) {
            return failure<MigrationReport>(
                "workspace_migration_apply_unproven",
                "migration paths could not be represented relative to the owned workspace");
        }
        journal.actions.push_back({item.action.kind, std::move(source_relative),
            std::move(target_relative), item.source_sha256, item.target_sha256});
    }
    auto journal_written = persist_journal(layout_, journal, true);
    if (!journal_written) {
        return failure<MigrationReport>(
            journal_written.error().code, journal_written.error().message, journal_written.error().path);
    }

    std::vector<std::pair<fs::path, std::string>> created_targets;
    const auto rollback = [&](const std::string& reason, const fs::path& problem_path) -> Result<MigrationReport> {
        bool rollback_complete = true;
        std::string rollback_problem;
        for (auto iterator = created_targets.rbegin(); iterator != created_targets.rend(); ++iterator) {
            facman::platform::StableInputFile target;
            auto opened = target.open_no_follow(iterator->first);
            std::string current;
            bool current_valid = opened.ok() && target.size() <= 1024ULL * 1024ULL;
            if (current_valid) {
                current.assign(static_cast<std::size_t>(target.size()), '\0');
                std::uint64_t offset = 0U;
                while (offset < target.size()) {
                    const std::size_t count = target.read_at(
                        offset,
                        current.data() + static_cast<std::size_t>(offset),
                        static_cast<std::size_t>(target.size() - offset));
                    if (count == 0U) {
                        current_valid = false;
                        break;
                    }
                    offset += count;
                }
                current_valid = current_valid && target.revalidate().ok();
            }
            if (!current_valid || current != iterator->second) {
                rollback_complete = false;
                rollback_problem = "created migration target changed before rollback";
                break;
            }
            const auto removed = facman::platform::remove_exact_object(
                iterator->first, target.identity());
            if (!removed.ok()) {
                rollback_complete = false;
                rollback_problem = removed.detail;
                break;
            }
        }
        journal.state = rollback_complete ? "rolled_back" : "recovery_required";
        auto recorded = persist_journal(layout_, journal, false);
        if (!recorded) {
            rollback_complete = false;
            if (rollback_problem.empty()) rollback_problem = recorded.error().message;
        }
        return failure<MigrationReport>(
            rollback_complete ? "workspace_migration_conflict" : "workspace_migration_recovery_required",
            reason + (rollback_complete ? "; created targets were rolled back" :
                "; migration recovery is required: " + rollback_problem),
            problem_path);
    };

    journal.state = "applying";
    auto journal_updated = persist_journal(layout_, journal, false);
    if (!journal_updated) {
        return rollback(journal_updated.error().message, journal_updated.error().path);
    }
    for (std::size_t index = 0U; index < prepared.size(); ++index) {
        PreparedMigrationAction& item = prepared[index];
        auto current_source = read_bounded(item.action.source);
        if (!current_source || current_source.value() != item.source_text) {
            return rollback("migration source changed after backup", item.action.source);
        }
        stable = revalidate_workspace_root(authority.value());
        if (!stable) return rollback(stable.error().message, layout_.root());
        auto committed = write_new_durable(item.action.target, item.target_text);
        if (!committed) {
            return rollback(committed.error().message, item.action.target);
        }
        created_targets.emplace_back(item.action.target, item.target_text);
        auto verified = read_bounded(item.action.target);
        if (!verified || verified.value() != item.target_text) {
            return rollback("migration target verification failed", item.action.target);
        }
        journal.completed_actions = index + 1U;
        journal_updated = persist_journal(layout_, journal, false);
        if (!journal_updated) {
            return rollback(journal_updated.error().message, journal_updated.error().path);
        }
    }
    journal.state = "complete";
    journal_updated = persist_journal(layout_, journal, false);
    if (!journal_updated) {
        return rollback(journal_updated.error().message, journal_updated.error().path);
    }
    auto remaining = collect_migration_actions(layout_);
    if (!remaining || !remaining.value().empty()) {
        return rollback(
            remaining ? "migration verification still reports pending actions" : remaining.error().message,
            layout_.root());
    }
    stable = revalidate_workspace_root(authority.value());
    if (!stable) return rollback(stable.error().message, layout_.root());
    auto released = migration_lock.release();
    if (!released) {
        return failure<MigrationReport>(
            released.error().code, released.error().message, released.error().path);
    }
    report.value().apply_enabled = true;
    return report;
}

std::string migration_detail::report_json(const MigrationReport& report)
{
    json::ArrayBuilder actions;
    for (const MigrationAction& action : report.actions) {
        json::ObjectBuilder item;
        item.add_string("kind", action.kind);
        item.add_string("source", facman::platform::path_to_utf8(action.source));
        item.add_string("target", facman::platform::path_to_utf8(action.target));
        item.add_bool("backup_required", action.backup_required);
        item.add_bool("journal_required", action.journal_required);
        actions.add_object(item);
    }
    json::ObjectBuilder document;
    document.add_string("schema", "facman.workspace_migration.v1");
    document.add_string("command", report.operation);
    document.add_string("status", report.actions.empty() ? "no_changes" : "changes_detected");
    document.add_bool("apply_enabled", report.apply_enabled);
    document.add_array("actions", actions);
    return document.serialize() + "\n";
}

} // namespace facman::workspace
