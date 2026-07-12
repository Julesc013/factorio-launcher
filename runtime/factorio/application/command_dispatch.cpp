// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "command_dispatch.h"

#include "fl_json.h"
#include "fl_file_io.h"

#include <algorithm>
#include <cctype>
#include <cstdint>
#include <filesystem>
#include <set>
#include <stdexcept>
#include <utility>

namespace facman::factorio::application {
namespace json = facman::core::json;
namespace fs = std::filesystem;

namespace {
bool reject_duplicate_top_level_fields(const std::string& text, std::string& detail)
{
    std::set<std::string> keys;
    std::size_t position = 0;
    while (position < text.size() && std::isspace(static_cast<unsigned char>(text[position]))) ++position;
    if (position >= text.size() || text[position] != '{') return true;
    ++position;
    bool expect_key = true;
    int object_depth = 1;
    int array_depth = 0;
    while (position < text.size() && object_depth > 0) {
        const char ch = text[position];
        if (ch == '"') {
            const std::size_t start = position++;
            bool escaped = false;
            while (position < text.size()) {
                const char current = text[position++];
                if (escaped) { escaped = false; continue; }
                if (current == '\\') { escaped = true; continue; }
                if (current == '"') break;
            }
            if (object_depth == 1 && array_depth == 0 && expect_key) {
                auto decoded = json::parse(text.substr(start, position - start));
                if (decoded && decoded.value().is_string()) {
                    const std::string key = decoded.value().string_value().value();
                    if (!keys.insert(key).second) {
                        detail = "request payload contains duplicate field: " + key;
                        return false;
                    }
                    expect_key = false;
                }
            }
            continue;
        }
        if (ch == '{') ++object_depth;
        else if (ch == '}') --object_depth;
        else if (ch == '[') ++array_depth;
        else if (ch == ']') --array_depth;
        else if (ch == ',' && object_depth == 1 && array_depth == 0) expect_key = true;
        ++position;
    }
    return true;
}

bool validate_fields(const json::Value& object, const std::set<std::string>& allowed, std::string& detail)
{
    for (const std::string& key : object.object_keys()) {
        if (allowed.count(key) == 0) {
            detail = "request payload contains an unsupported field: " + key;
            return false;
        }
    }
    return true;
}

bool required_string(const json::Value& object, const char* key, std::string& value, std::string& detail)
{
    const json::Value* field = object.find(key);
    if (field == nullptr) {
        detail = std::string("request payload is missing non-empty string field: ") + key;
        return false;
    }
    auto text = field->string_value();
    if (!text) {
        detail = std::string("request payload field must be a string: ") + key;
        return false;
    }
    if (text.value().empty()) {
        detail = std::string("request payload field must be a non-empty string: ") + key;
        return false;
    }
    value = text.take_value();
    return true;
}

bool optional_string(const json::Value& object, const char* key, std::string& value, std::string& detail)
{
    const json::Value* field = object.find(key);
    if (field == nullptr) return true;
    auto text = field->string_value();
    if (!text) {
        detail = std::string("request payload field must be a string: ") + key;
        return false;
    }
    value = text.take_value();
    return true;
}

bool optional_string_array(const json::Value& object, const char* key, std::vector<std::string>& values, std::string& detail)
{
    const json::Value* field = object.find(key);
    if (field == nullptr) return true;
    if (!field->is_array() || field->size() > 256U) {
        detail = std::string("request payload field must be a string array of at most 256 items: ") + key;
        return false;
    }
    for (std::size_t index = 0; index < field->size(); ++index) {
        const json::Value* item = field->at(index);
        if (item == nullptr) { detail = "request payload array item is unavailable"; return false; }
        auto text = item->string_value();
        if (!text) { detail = std::string("request payload array contains a non-string item: ") + key; return false; }
        values.push_back(text.take_value());
    }
    return true;
}

bool optional_unsigned_string(
    const json::Value& object,
    const char* key,
    std::uint32_t& value,
    std::string& detail)
{
    std::string text;
    if (!optional_string(object, key, text, detail)) return false;
    if (text.empty()) return true;
    if (!std::all_of(text.begin(), text.end(), [](unsigned char ch) { return std::isdigit(ch) != 0; })) {
        detail = std::string("request payload field must be an unsigned integer string: ") + key;
        return false;
    }
    try {
        const unsigned long parsed = std::stoul(text);
        if (parsed > 1000000UL) throw std::out_of_range("preference limit");
        value = static_cast<std::uint32_t>(parsed);
    } catch (...) {
        detail = std::string("request payload field exceeds its numeric budget: ") + key;
        return false;
    }
    return true;
}

bool optional_unsigned_64_string(
    const json::Value& object,
    const char* key,
    std::uint64_t& value,
    std::string& detail)
{
    std::string text;
    if (!optional_string(object, key, text, detail)) return false;
    if (text.empty()) return true;
    if (!std::all_of(text.begin(), text.end(), [](unsigned char ch) { return std::isdigit(ch) != 0; })) {
        detail = std::string("request payload field must be an unsigned integer string: ") + key;
        return false;
    }
    try {
        value = std::stoull(text);
    } catch (...) {
        detail = std::string("request payload field exceeds its numeric budget: ") + key;
        return false;
    }
    return true;
}

const char* service_operation(CommandId command) noexcept
{
    switch (command) {
#include "generated/command_names.inc"
    default: return "";
    }
}

CommandId service_command(const std::string& operation) noexcept
{
    const std::string& value = operation;
#include "generated/command_lookup.inc"
    return CommandId::unsupported;
}

bool decode_service_request(
    CommandId command,
    const json::Value& payload,
    ServiceOperationRequest& typed,
    std::string& detail)
{
    typed.operation = service_operation(command);
    std::set<std::string> allowed;
    switch (command) {
    case CommandId::package_verify: allowed = {"path"}; break;
    case CommandId::installs_install_version: allowed = {"version", "archive"}; break;
    case CommandId::installs_verify:
    case CommandId::installs_repair:
    case CommandId::installs_uninstall: allowed = {"id"}; break;
    case CommandId::mods_search: allowed = {"query"}; break;
    case CommandId::mods_install: allowed = {"query", "instance_id"}; break;
    case CommandId::mods_update: allowed = {"instance_id"}; break;
    case CommandId::servers_list:
    case CommandId::dev_bug_report:
    case CommandId::dev_dump_data:
    case CommandId::dev_dump_icons:
    case CommandId::dev_benchmark:
    case CommandId::dev_instrument_mod: break;
    case CommandId::servers_create: allowed = {"name", "id", "instance_id"}; break;
    case CommandId::servers_start:
    case CommandId::servers_stop:
    case CommandId::servers_rcon: allowed = {"id"}; break;
    case CommandId::diagnostics_redact: allowed = {"path"}; break;
    default: detail = "unsupported service command"; return false;
    }
    if (!validate_fields(payload, allowed, detail)) return false;
    if (!optional_string(payload, "name", typed.name, detail) ||
        !optional_string(payload, "id", typed.id, detail) ||
        !optional_string(payload, "instance_id", typed.instance_id, detail) ||
        !optional_string(payload, "path", typed.path, detail) ||
        !optional_string(payload, "query", typed.query, detail) ||
        !optional_string(payload, "version", typed.version, detail) ||
        !optional_string(payload, "archive", typed.archive, detail)) return false;
    if (command == CommandId::installs_install_version && typed.version.empty()) {
        detail = "request payload is missing non-empty string field: version"; return false;
    }
    if ((command == CommandId::installs_verify || command == CommandId::installs_repair || command == CommandId::installs_uninstall ||
         command == CommandId::servers_start || command == CommandId::servers_stop || command == CommandId::servers_rcon) && typed.id.empty()) {
        detail = "request payload is missing non-empty string field: id"; return false;
    }
    if (command == CommandId::servers_create && (typed.name.empty() || typed.instance_id.empty())) {
        detail = "servers.create requires non-empty name and instance_id fields"; return false;
    }
    if (command == CommandId::diagnostics_redact && typed.path.empty()) {
        detail = "request payload is missing non-empty string field: path"; return false;
    }
    return true;
}
}

CommandId command_id(ulk_string_view command)
{
    const std::string value(command.data, command.data + command.size);
#include "generated/command_lookup.inc"
    return CommandId::unsupported;
}

bool writes_persistent_state(CommandId command) noexcept
{
    switch (command) {
#include "generated/command_writes.inc"
    default: return false;
    }
}

bool decode_request(CommandId command, const std::string& text, bool dry_run, ApplicationRequest& request, std::string& detail)
{
    request.command = command;
    request.dry_run = dry_run;
    if (command == CommandId::unsupported) { request.payload = std::monostate {}; return true; }
    json::Limits limits;
    limits.maximum_bytes = 64U * 1024U;
    limits.maximum_depth = 16U;
    limits.maximum_nodes = 2048U;
    limits.maximum_string_bytes = 32U * 1024U;
    const std::string source = text.empty() ? "{}" : text;
    if (!reject_duplicate_top_level_fields(source, detail)) return false;
    auto document = json::parse(source, limits);
    if (!document) { detail = document.error().message; return false; }
    if (!document.value().is_object()) { detail = "request payload must be a JSON object"; return false; }
    const json::Value& payload = document.value();

    switch (command) {
    case CommandId::product_inspect:
    case CommandId::install_list:
    case CommandId::instance_list:
    case CommandId::setup_preview:
    case CommandId::workspace_status:
    case CommandId::workspace_paths:
    case CommandId::capabilities_inspect:
    case CommandId::doctor_explain:
        if (!validate_fields(payload, {}, detail)) return false;
        request.payload = std::monostate {}; return true;
    case CommandId::onboarding_plan: {
        if (!validate_fields(payload, {"preferred_install", "instance_display_name", "template_id", "workspace"}, detail)) return false;
        OnboardingPlanRequest typed;
        if (!optional_string(payload, "preferred_install", typed.preferred_install, detail) ||
            !optional_string(payload, "instance_display_name", typed.instance_display_name, detail) ||
            !optional_string(payload, "template_id", typed.template_id, detail) ||
            !optional_string(payload, "workspace", typed.workspace, detail)) return false;
        request.payload = std::move(typed); return true;
    }
    case CommandId::launch_plan_explain:
    case CommandId::modsets_explain: {
        if (!validate_fields(payload, {"instance_id"}, detail)) return false;
        std::string value;
        if (!required_string(payload, "instance_id", value, detail)) return false;
        auto instance_id = facman::core::InstanceId::parse_legacy(value);
        if (!instance_id) { detail = instance_id.error().message; return false; }
        ExplainInstanceRequest typed;
        typed.instance_id = instance_id.take_value();
        request.payload = std::move(typed); return true;
    }
    case CommandId::doctor_run: {
        if (!validate_fields(payload, {"roots"}, detail)) return false;
        DoctorRequest typed;
        if (!optional_string_array(payload, "roots", typed.roots, detail)) return false;
        request.payload = std::move(typed); return true;
    }
    case CommandId::preferences_validate:
    case CommandId::preferences_plan:
    case CommandId::preferences_apply: {
        if (!validate_fields(payload, {
                "preferred_workspace", "preferred_transport", "default_instance_template",
                "default_launch_profile", "display_color_policy", "tui_page_size",
                "command_timeout_seconds", "backup_destination", "backup_keep_last",
                "discovery_providers", "discovery_roots"}, detail)) return false;
        PreferencesRequest typed;
        if (!optional_string(payload, "preferred_workspace", typed.values.preferred_workspace, detail) ||
            !optional_string(payload, "preferred_transport", typed.values.preferred_transport, detail) ||
            !optional_string(payload, "default_instance_template", typed.values.default_instance_template, detail) ||
            !optional_string(payload, "default_launch_profile", typed.values.default_launch_profile, detail) ||
            !optional_string(payload, "display_color_policy", typed.values.display_color_policy, detail) ||
            !optional_unsigned_string(payload, "tui_page_size", typed.values.tui_page_size, detail) ||
            !optional_unsigned_string(payload, "command_timeout_seconds", typed.values.command_timeout_seconds, detail) ||
            !optional_string(payload, "backup_destination", typed.values.backup_destination, detail) ||
            !optional_unsigned_string(payload, "backup_keep_last", typed.values.backup_keep_last, detail) ||
            !optional_string_array(payload, "discovery_providers", typed.values.discovery_providers, detail) ||
            !optional_string_array(payload, "discovery_roots", typed.values.discovery_roots, detail)) return false;
        request.payload = std::move(typed); return true;
    }
    case CommandId::legacy_setup_operation:
    case CommandId::legacy_utility_operation: {
        if (!validate_fields(payload, {"operation", "name", "id", "instance_id", "path", "query", "version", "archive"}, detail)) return false;
        ServiceOperationRequest typed;
        if (!required_string(payload, "operation", typed.operation, detail) ||
            !optional_string(payload, "name", typed.name, detail) ||
            !optional_string(payload, "id", typed.id, detail) ||
            !optional_string(payload, "instance_id", typed.instance_id, detail) ||
            !optional_string(payload, "path", typed.path, detail) ||
            !optional_string(payload, "query", typed.query, detail) ||
            !optional_string(payload, "version", typed.version, detail) ||
            !optional_string(payload, "archive", typed.archive, detail)) return false;
        const CommandId normalized = service_command(typed.operation);
        if (normalized == CommandId::unsupported) { detail = "unsupported compatibility operation"; return false; }
        typed.operation = service_operation(normalized);
        request.command = normalized;
        request.payload = std::move(typed); return true;
    }
    case CommandId::package_verify:
    case CommandId::installs_install_version:
    case CommandId::installs_verify:
    case CommandId::installs_repair:
    case CommandId::installs_uninstall:
    case CommandId::mods_search:
    case CommandId::mods_install:
    case CommandId::mods_update:
    case CommandId::servers_list:
    case CommandId::servers_create:
    case CommandId::servers_start:
    case CommandId::servers_stop:
    case CommandId::servers_rcon:
    case CommandId::diagnostics_redact:
    case CommandId::dev_bug_report:
    case CommandId::dev_dump_data:
    case CommandId::dev_dump_icons:
    case CommandId::dev_benchmark:
    case CommandId::dev_instrument_mod: {
        ServiceOperationRequest typed;
        if (!decode_service_request(command, payload, typed, detail)) return false;
        request.payload = std::move(typed); return true;
    }
    case CommandId::run_execute:
        if (!validate_fields(payload, {"instance_id"}, detail)) return false;
        {
            ExecuteRunRequest typed;
            std::string instance_id;
            if (!optional_string(payload, "instance_id", instance_id, detail)) return false;
            if (!instance_id.empty()) {
                auto parsed = facman::core::InstanceId::parse_legacy(instance_id);
                if (!parsed) { detail = parsed.error().message; return false; }
                typed.instance_id = parsed.take_value();
            }
            request.payload = std::move(typed); return true;
        }
    case CommandId::install_scan: {
        if (!validate_fields(payload, {"roots"}, detail)) return false;
        ScanInstallRefsRequest typed;
        if (!optional_string_array(payload, "roots", typed.roots, detail)) return false;
        request.payload = std::move(typed); return true;
    }
    case CommandId::install_import: {
        if (!validate_fields(payload, {"path", "install_id"}, detail)) return false;
        ImportInstallRefRequest typed;
        if (!required_string(payload, "path", typed.path, detail) || !required_string(payload, "install_id", typed.install_id, detail)) return false;
        request.payload = std::move(typed); return true;
    }
    case CommandId::install_inspect: {
        if (!validate_fields(payload, {"install_id"}, detail)) return false;
        InspectInstallRefRequest typed;
        if (!required_string(payload, "install_id", typed.install_id, detail)) return false;
        request.payload = std::move(typed); return true;
    }
    case CommandId::instance_create: {
        if (!validate_fields(payload, {"display_name", "instance_id", "install_id", "template_id"}, detail)) return false;
        CreateInstanceRequest typed;
        if (!required_string(payload, "display_name", typed.display_name, detail) ||
            !required_string(payload, "instance_id", typed.instance_id, detail) ||
            !required_string(payload, "install_id", typed.install_id, detail) ||
            !optional_string(payload, "template_id", typed.template_id, detail)) return false;
        request.payload = std::move(typed); return true;
    }
    case CommandId::instances_inspect:
    case CommandId::instances_verify:
    case CommandId::instances_archive: {
        if (!validate_fields(payload, {"instance_id"}, detail)) return false;
        InspectInstanceRequest typed;
        if (!required_string(payload, "instance_id", typed.instance_id, detail)) return false;
        if (command == CommandId::instances_archive) {
            ArchiveInstanceRequest archive_request {typed.instance_id};
            request.payload = std::move(archive_request);
        } else request.payload = std::move(typed);
        return true;
    }
    case CommandId::instances_diff: {
        if (!validate_fields(payload, {"left_instance_id", "right_ref"}, detail)) return false;
        DiffInstanceRequest typed;
        if (!required_string(payload, "left_instance_id", typed.left_instance_id, detail) ||
            !required_string(payload, "right_ref", typed.right_ref, detail)) return false;
        request.payload = std::move(typed); return true;
    }
    case CommandId::instances_clone: {
        if (!validate_fields(payload, {"source_instance_id", "destination_instance_id", "display_name", "install_ref"}, detail)) return false;
        CloneInstanceRequest typed;
        if (!required_string(payload, "source_instance_id", typed.source_instance_id, detail) ||
            !required_string(payload, "destination_instance_id", typed.destination_instance_id, detail) ||
            !optional_string(payload, "display_name", typed.display_name, detail) ||
            !optional_string(payload, "install_ref", typed.install_ref, detail)) return false;
        request.payload = std::move(typed); return true;
    }
    case CommandId::instances_rename: {
        if (!validate_fields(payload, {"instance_id", "display_name"}, detail)) return false;
        RenameInstanceRequest typed;
        if (!required_string(payload, "instance_id", typed.instance_id, detail) ||
            !required_string(payload, "display_name", typed.display_name, detail)) return false;
        request.payload = std::move(typed); return true;
    }
    case CommandId::instances_restore: {
        if (!validate_fields(payload, {"archive_id", "new_instance_id"}, detail)) return false;
        RestoreInstanceRequest typed;
        if (!required_string(payload, "archive_id", typed.archive_id, detail) ||
            !optional_string(payload, "new_instance_id", typed.new_instance_id, detail)) return false;
        request.payload = std::move(typed); return true;
    }
    case CommandId::snapshots_create: {
        if (!validate_fields(payload, {"instance_id", "snapshot_id", "saves"}, detail)) return false;
        CreateSnapshotRequest typed;
        if (!required_string(payload, "instance_id", typed.instance_id, detail) ||
            !required_string(payload, "snapshot_id", typed.snapshot_id, detail) ||
            !optional_string_array(payload, "saves", typed.saves, detail)) return false;
        request.payload = std::move(typed); return true;
    }
    case CommandId::snapshots_list: {
        if (!validate_fields(payload, {"instance_id"}, detail)) return false;
        ListSnapshotsRequest typed;
        if (!required_string(payload, "instance_id", typed.instance_id, detail)) return false;
        request.payload = std::move(typed); return true;
    }
    case CommandId::snapshots_inspect:
    case CommandId::snapshots_verify: {
        if (!validate_fields(payload, {"instance_id", "snapshot_id"}, detail)) return false;
        SnapshotRequest typed;
        if (!required_string(payload, "instance_id", typed.instance_id, detail) ||
            !required_string(payload, "snapshot_id", typed.snapshot_id, detail)) return false;
        request.payload = std::move(typed); return true;
    }
    case CommandId::snapshots_diff: {
        if (!validate_fields(payload, {"instance_id", "left_snapshot_id", "right_snapshot_id"}, detail)) return false;
        DiffSnapshotRequest typed;
        if (!required_string(payload, "instance_id", typed.instance_id, detail) ||
            !required_string(payload, "left_snapshot_id", typed.left_snapshot_id, detail) ||
            !required_string(payload, "right_snapshot_id", typed.right_snapshot_id, detail)) return false;
        request.payload = std::move(typed); return true;
    }
    case CommandId::snapshots_restore: {
        if (!validate_fields(payload, {"snapshot_ref", "target_instance_id"}, detail)) return false;
        RestoreSnapshotRequest typed; std::string path;
        if (!required_string(payload, "snapshot_ref", path, detail) ||
            !required_string(payload, "target_instance_id", typed.target_instance_id, detail)) return false;
        typed.snapshot_ref = path;
        request.payload = std::move(typed); return true;
    }
    case CommandId::snapshots_retention_plan:
    case CommandId::snapshots_retention_apply: {
        if (!validate_fields(payload, {"instance_id", "keep_last", "keep_daily", "keep_weekly", "maximum_total_bytes", "minimum_age_days"}, detail)) return false;
        SnapshotRetentionRequest typed;
        if (!required_string(payload, "instance_id", typed.instance_id, detail) ||
            !optional_unsigned_string(payload, "keep_last", typed.keep_last, detail) ||
            !optional_unsigned_string(payload, "keep_daily", typed.keep_daily, detail) ||
            !optional_unsigned_string(payload, "keep_weekly", typed.keep_weekly, detail) ||
            !optional_unsigned_64_string(payload, "maximum_total_bytes", typed.maximum_total_bytes, detail) ||
            !optional_unsigned_string(payload, "minimum_age_days", typed.minimum_age_days, detail)) return false;
        request.payload = std::move(typed); return true;
    }
    case CommandId::launch_plan_build:
    case CommandId::launch_plan_preflight:
    case CommandId::run_preview: {
        if (!validate_fields(payload, {"instance_id"}, detail)) return false;
        BuildLaunchPlanRequest typed;
        if (!required_string(payload, "instance_id", typed.instance_id, detail)) return false;
        request.payload = std::move(typed); return true;
    }
    case CommandId::mods_import: {
        if (!validate_fields(payload, {"source_path", "instance_id"}, detail)) return false;
        ImportModRequest typed; std::string path;
        if (!required_string(payload, "source_path", path, detail) || !required_string(payload, "instance_id", typed.instance_id, detail)) return false;
        typed.source_path = facman::platform::path_from_utf8(path); request.payload = std::move(typed); return true;
    }
    case CommandId::modsets_lock:
    case CommandId::modsets_verify: {
        if (!validate_fields(payload, {"instance_id"}, detail)) return false;
        ModsetInstanceRequest typed;
        if (!required_string(payload, "instance_id", typed.instance_id, detail)) return false;
        request.payload = std::move(typed); return true;
    }
    case CommandId::modsets_export: {
        if (!validate_fields(payload, {"instance_id", "output_path"}, detail)) return false;
        ExportModsetRequest typed; std::string path;
        if (!required_string(payload, "instance_id", typed.instance_id, detail) || !required_string(payload, "output_path", path, detail)) return false;
        typed.output_path = facman::platform::path_from_utf8(path); request.payload = std::move(typed); return true;
    }
    case CommandId::saves_list: {
        if (!validate_fields(payload, {"instance_id"}, detail)) return false;
        ListSavesRequest typed;
        if (!required_string(payload, "instance_id", typed.instance_id, detail)) return false;
        request.payload = std::move(typed); return true;
    }
    case CommandId::saves_backup: {
        if (!validate_fields(payload, {"instance_id", "save", "output_path"}, detail)) return false;
        BackupSaveRequest typed; std::string output;
        if (!required_string(payload, "instance_id", typed.instance_id, detail) || !required_string(payload, "save", typed.save, detail) ||
            !optional_string(payload, "output_path", output, detail)) return false;
        if (!output.empty()) typed.output_path = facman::platform::path_from_utf8(output);
        request.payload = std::move(typed); return true;
    }
    case CommandId::saves_clone: {
        if (!validate_fields(payload, {"source_instance_id", "target_instance_id", "save"}, detail)) return false;
        CloneSaveRequest typed;
        if (!required_string(payload, "source_instance_id", typed.source_instance_id, detail) ||
            !required_string(payload, "target_instance_id", typed.target_instance_id, detail) ||
            !required_string(payload, "save", typed.save, detail)) return false;
        request.payload = std::move(typed); return true;
    }
    case CommandId::instance_export: {
        if (!validate_fields(payload, {"instance_id", "output_path"}, detail)) return false;
        ExportInstanceRequest typed; std::string path;
        if (!required_string(payload, "instance_id", typed.instance_id, detail) || !required_string(payload, "output_path", path, detail)) return false;
        typed.output_path = facman::platform::path_from_utf8(path); request.payload = std::move(typed); return true;
    }
    case CommandId::instance_import: {
        if (!validate_fields(payload, {"source_path", "instance_id"}, detail)) return false;
        ImportInstanceRequest typed; std::string path;
        if (!required_string(payload, "source_path", path, detail) || !optional_string(payload, "instance_id", typed.instance_id_override, detail)) return false;
        typed.source_path = facman::platform::path_from_utf8(path); request.payload = std::move(typed); return true;
    }
    case CommandId::diagnostics_export: {
        if (!validate_fields(payload, {"instance_id", "output_path"}, detail)) return false;
        ExportDiagnosticRequest typed; std::string path;
        if (!required_string(payload, "instance_id", typed.instance_id, detail) || !required_string(payload, "output_path", path, detail)) return false;
        typed.output_path = facman::platform::path_from_utf8(path); request.payload = std::move(typed); return true;
    }
    case CommandId::recovery_inspect:
    case CommandId::preferences_inspect:
    case CommandId::preferences_reset_plan:
    case CommandId::preferences_reset_apply:
    case CommandId::migration_inspect:
    case CommandId::migration_plan:
    case CommandId::migration_apply:
        if (!validate_fields(payload, {}, detail)) return false;
        request.payload = RecoveryRequest {}; return true;
    case CommandId::recovery_plan:
    case CommandId::recovery_apply: {
        if (!validate_fields(payload, {"transaction_id"}, detail)) return false;
        RecoveryRequest typed;
        if (!required_string(payload, "transaction_id", typed.transaction_id, detail)) return false;
        request.payload = std::move(typed); return true;
    }
    default: detail = "unsupported command"; return false;
    }
}

} // namespace facman::factorio::application
