// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "fl_preferences.h"

#include "fl_file_io.h"
#include "fl_json.h"
#include "fl_path_safety.h"
#include "fl_transaction.h"
#include "fl_user_paths.h"

#include <algorithm>
#include <cctype>
#include <set>
#include <system_error>
#include <vector>

namespace facman::preferences {
namespace fs = std::filesystem;
namespace json = facman::core::json;
namespace transactions = facman::transaction;
namespace {

constexpr std::uint64_t kMaximumPreferencesBytes = 256U * 1024U;

facman::core::Result<std::string> read_stable(const fs::path& path)
{
    facman::platform::StableInputFile input;
    auto status = input.open_no_follow(path);
    if (!status.ok()) return facman::core::Result<std::string>::failure({status.code, status.detail, path.string()});
    if (input.size() > kMaximumPreferencesBytes) {
        return facman::core::Result<std::string>::failure({
            "preferences_too_large", "Preferences exceed the 256 KiB limit", path.string()});
    }
    std::string text(static_cast<std::size_t>(input.size()), '\0');
    std::uint64_t offset = 0;
    while (offset < input.size()) {
        const std::size_t count = input.read_at(
            offset, text.data() + static_cast<std::size_t>(offset),
            static_cast<std::size_t>(input.size() - offset));
        if (count == 0) {
            return facman::core::Result<std::string>::failure({
                "preferences_read_failed", "Preferences produced a short stable read", path.string()});
        }
        offset += count;
    }
    status = input.revalidate();
    if (!status.ok()) return facman::core::Result<std::string>::failure({status.code, status.detail, path.string()});
    return facman::core::Result<std::string>::success(std::move(text));
}

bool secret_key(const std::string& key)
{
    std::string lower;
    for (unsigned char value : key) lower.push_back(static_cast<char>(std::tolower(value)));
    for (const char* marker : {"token", "password", "cookie", "credential", "secret", "script", "command"}) {
        if (lower.find(marker) != std::string::npos) return true;
    }
    return false;
}

facman::core::Result<std::string> optional_string(const json::Value& object, const char* key)
{
    const json::Value* value = object.find(key);
    if (value == nullptr) return facman::core::Result<std::string>::success({});
    auto result = value->string_value();
    if (!result) return facman::core::Result<std::string>::failure({
        "preferences_type_invalid", std::string("Preference must be a string: ") + key, key});
    return result;
}

facman::core::Result<std::uint32_t> optional_unsigned(const json::Value& object, const char* key)
{
    const json::Value* value = object.find(key);
    if (value == nullptr) return facman::core::Result<std::uint32_t>::success(0);
    auto result = value->unsigned_integer_value();
    if (!result || result.value() > 1000000U) return facman::core::Result<std::uint32_t>::failure({
        "preferences_type_invalid", std::string("Preference must be a bounded unsigned integer: ") + key, key});
    return facman::core::Result<std::uint32_t>::success(static_cast<std::uint32_t>(result.value()));
}

facman::core::Result<std::vector<std::string>> optional_array(const json::Value& object, const char* key)
{
    std::vector<std::string> output;
    const json::Value* value = object.find(key);
    if (value == nullptr) return facman::core::Result<std::vector<std::string>>::success(std::move(output));
    if (!value->is_array() || value->size() > 256U) {
        return facman::core::Result<std::vector<std::string>>::failure({
            "preferences_type_invalid", std::string("Preference must be a string array of at most 256 items: ") + key, key});
    }
    for (std::size_t index = 0; index < value->size(); ++index) {
        const json::Value* item = value->at(index);
        auto text = item == nullptr
            ? facman::core::Result<std::string>::failure({"preferences_type_invalid", "Missing array item", key})
            : item->string_value();
        if (!text || text.value().empty()) return facman::core::Result<std::vector<std::string>>::failure({
            "preferences_type_invalid", std::string("Preference array contains an invalid item: ") + key, key});
        output.push_back(text.take_value());
    }
    return facman::core::Result<std::vector<std::string>>::success(std::move(output));
}

void add_array(json::ObjectBuilder& output, const char* key, const std::vector<std::string>& values)
{
    if (values.empty()) return;
    json::ArrayBuilder array;
    for (const std::string& value : values) array.add_string(value);
    output.add_array(key, array);
}

std::string values_json(const Preferences& preferences)
{
    json::ObjectBuilder output;
    output.add_string("schema", "facman.preferences.v1");
    if (!preferences.preferred_workspace.empty()) output.add_string("preferred_workspace", preferences.preferred_workspace);
    if (!preferences.preferred_transport.empty()) output.add_string("preferred_transport", preferences.preferred_transport);
    if (!preferences.default_instance_template.empty()) output.add_string("default_instance_template", preferences.default_instance_template);
    if (!preferences.default_launch_profile.empty()) output.add_string("default_launch_profile", preferences.default_launch_profile);
    if (!preferences.display_color_policy.empty()) output.add_string("display_color_policy", preferences.display_color_policy);
    if (preferences.tui_page_size != 0) (void)output.add_unsigned_integer("tui_page_size", preferences.tui_page_size);
    if (preferences.command_timeout_seconds != 0) {
        (void)output.add_unsigned_integer("command_timeout_seconds", preferences.command_timeout_seconds);
    }
    if (!preferences.backup_destination.empty()) output.add_string("backup_destination", preferences.backup_destination);
    if (preferences.backup_keep_last != 0) (void)output.add_unsigned_integer("backup_keep_last", preferences.backup_keep_last);
    add_array(output, "discovery_providers", preferences.discovery_providers);
    add_array(output, "discovery_roots", preferences.discovery_roots);
    return output.serialize();
}

facman::core::Result<void> prepare_parent(const fs::path& parent)
{
    std::string detail;
    if (facman::base::path_crosses_link_or_reparse_point(parent, detail)) {
        return facman::core::Result<void>::failure({"preferences_path_unsafe", detail, parent.string()});
    }
    std::error_code error;
    fs::create_directories(parent, error);
    if (error || facman::base::path_crosses_link_or_reparse_point(parent, detail)) {
        return facman::core::Result<void>::failure({
            "preferences_directory_refused", error ? error.message() : detail, parent.string()});
    }
    return facman::core::Result<void>::success();
}

facman::core::Result<void> write_new(const fs::path& path, const std::string& text)
{
    facman::platform::DurableOutputFile output;
    auto status = output.create_exclusive(path, kMaximumPreferencesBytes);
    if (status.ok() && output.write_at(0, text.data(), text.size()) != text.size()) {
        status = facman::platform::IoStatus::failure("preferences_write_failed", "short preferences write");
    }
    if (status.ok()) status = output.flush_file_and_parent();
    if (!status.ok()) {
        output.close_without_flush();
        return facman::core::Result<void>::failure({status.code, status.detail, path.string()});
    }
    return facman::core::Result<void>::success();
}

} // namespace

facman::core::Result<fs::path> preferences_path()
{
    auto paths = facman::platform::user_paths();
    if (!paths || paths.value().config.empty()) return facman::core::Result<fs::path>::failure({
        "preferences_path_unavailable", paths ? "Platform configuration path is empty" : paths.error().message,
        "config", facman::core::OutcomeKind::unavailable});
    return facman::core::Result<fs::path>::success(
        (paths.value().config / "facman" / "preferences.v1.json").lexically_normal());
}

facman::core::Result<Preferences> decode(const std::string& text)
{
    json::Limits limits;
    limits.maximum_bytes = kMaximumPreferencesBytes;
    limits.maximum_depth = 8;
    limits.maximum_nodes = 2048;
    auto document = json::parse(text, limits);
    if (!document || !document.value().is_object()) return facman::core::Result<Preferences>::failure({
        "preferences_document_invalid", document ? "Preferences must be an object" : document.error().message, "preferences"});
    const std::set<std::string> allowed = {
        "schema", "preferred_workspace", "preferred_transport", "default_instance_template",
        "default_launch_profile", "display_color_policy", "tui_page_size", "command_timeout_seconds",
        "backup_destination", "backup_keep_last", "discovery_providers", "discovery_roots",
    };
    for (const std::string& key : document.value().object_keys()) {
        if (allowed.count(key) == 0) return facman::core::Result<Preferences>::failure({
            secret_key(key) ? "preferences_secret_forbidden" : "preferences_field_unsupported",
            "Preferences contain an unsupported field: " + key, key, facman::core::OutcomeKind::invalid_argument});
    }
    auto schema = optional_string(document.value(), "schema");
    if (!schema || schema.value() != "facman.preferences.v1") return facman::core::Result<Preferences>::failure({
        "preferences_version_unsupported", "Preferences must use schema facman.preferences.v1", "schema",
        facman::core::OutcomeKind::invalid_argument});
    Preferences output;
    auto workspace = optional_string(document.value(), "preferred_workspace");
    auto transport = optional_string(document.value(), "preferred_transport");
    auto instance_template = optional_string(document.value(), "default_instance_template");
    auto launch_profile = optional_string(document.value(), "default_launch_profile");
    auto color = optional_string(document.value(), "display_color_policy");
    auto page_size = optional_unsigned(document.value(), "tui_page_size");
    auto timeout = optional_unsigned(document.value(), "command_timeout_seconds");
    auto backup = optional_string(document.value(), "backup_destination");
    auto keep_last = optional_unsigned(document.value(), "backup_keep_last");
    auto providers = optional_array(document.value(), "discovery_providers");
    auto roots = optional_array(document.value(), "discovery_roots");
    if (!workspace || !transport || !instance_template || !launch_profile || !color || !page_size || !timeout ||
        !backup || !keep_last || !providers || !roots) {
        const facman::core::Error* error = nullptr;
        if (!workspace) error = &workspace.error(); else if (!transport) error = &transport.error();
        else if (!instance_template) error = &instance_template.error(); else if (!launch_profile) error = &launch_profile.error();
        else if (!color) error = &color.error(); else if (!page_size) error = &page_size.error();
        else if (!timeout) error = &timeout.error(); else if (!backup) error = &backup.error();
        else if (!keep_last) error = &keep_last.error(); else if (!providers) error = &providers.error(); else error = &roots.error();
        return facman::core::Result<Preferences>::failure(*error);
    }
    output.preferred_workspace = workspace.take_value();
    output.preferred_transport = transport.take_value();
    output.default_instance_template = instance_template.take_value();
    output.default_launch_profile = launch_profile.take_value();
    output.display_color_policy = color.take_value();
    output.tui_page_size = page_size.take_value();
    output.command_timeout_seconds = timeout.take_value();
    output.backup_destination = backup.take_value();
    output.backup_keep_last = keep_last.take_value();
    output.discovery_providers = providers.take_value();
    output.discovery_roots = roots.take_value();
    auto valid = validate(output);
    if (!valid) return facman::core::Result<Preferences>::failure(valid.error());
    return facman::core::Result<Preferences>::success(std::move(output));
}

facman::core::Result<void> validate(const Preferences& preferences)
{
    const std::set<std::string> transports = {"direct", "process", "daemon"};
    const std::set<std::string> colors = {"auto", "always", "never"};
    if (!preferences.preferred_transport.empty() && transports.count(preferences.preferred_transport) == 0) {
        return facman::core::Result<void>::failure({
            "preferences_transport_invalid", "Preferred transport must be direct, process, or daemon", "preferred_transport"});
    }
    if (!preferences.display_color_policy.empty() && colors.count(preferences.display_color_policy) == 0) {
        return facman::core::Result<void>::failure({
            "preferences_color_invalid", "Color policy must be auto, always, or never", "display_color_policy"});
    }
    if (preferences.preferred_transport == "daemon") return facman::core::Result<void>::failure({
        "preferences_transport_unavailable", "Daemon transport is not available", "preferred_transport",
        facman::core::OutcomeKind::unavailable});
    if (preferences.tui_page_size > 1000U || (preferences.tui_page_size != 0U && preferences.tui_page_size < 5U)) {
        return facman::core::Result<void>::failure({
            "preferences_page_size_invalid", "TUI page size must be between 5 and 1000", "tui_page_size"});
    }
    if (preferences.command_timeout_seconds > 86400U ||
        (preferences.command_timeout_seconds != 0U && preferences.command_timeout_seconds < 1U)) {
        return facman::core::Result<void>::failure({
            "preferences_timeout_invalid", "Command timeout must be between 1 and 86400 seconds", "command_timeout_seconds"});
    }
    if (preferences.backup_keep_last > 10000U) return facman::core::Result<void>::failure({
        "preferences_retention_invalid", "Backup keep-last must not exceed 10000", "backup_keep_last"});
    return facman::core::Result<void>::success();
}

std::string encode(const Preferences& preferences) { return values_json(preferences); }

facman::core::Result<Document> inspect()
{
    auto path = preferences_path();
    if (!path) return facman::core::Result<Document>::failure(path.error());
    return inspect_at(path.value());
}

facman::core::Result<Document> inspect_at(const fs::path& path)
{
    Document output;
    output.path = path;
    std::error_code error;
    const fs::file_status status = fs::symlink_status(output.path, error);
    if (error == std::errc::no_such_file_or_directory || status.type() == fs::file_type::not_found) {
        return facman::core::Result<Document>::success(std::move(output));
    }
    if (error || fs::is_symlink(status) || !fs::is_regular_file(status)) return facman::core::Result<Document>::failure({
        "preferences_path_unsafe", "Preferences path is not a real regular file", output.path.string()});
    auto text = read_stable(output.path);
    if (!text) return facman::core::Result<Document>::failure(text.error());
    auto decoded = decode(text.value());
    if (!decoded) return facman::core::Result<Document>::failure(decoded.error());
    output.values = decoded.take_value();
    output.present = true;
    return facman::core::Result<Document>::success(std::move(output));
}

facman::core::Result<std::string> report(const char* operation, const Preferences* proposed, bool reset)
{
    auto path = preferences_path();
    if (!path) return facman::core::Result<std::string>::failure(path.error());
    return report_at(path.value(), operation, proposed, reset);
}

facman::core::Result<std::string> report_at(
    const fs::path& path,
    const char* operation,
    const Preferences* proposed,
    bool reset)
{
    if (proposed != nullptr) {
        auto valid = validate(*proposed);
        if (!valid) return facman::core::Result<std::string>::failure(valid.error());
    }
    auto current = inspect_at(path);
    if (!current) return facman::core::Result<std::string>::failure(current.error());
    json::ObjectBuilder output;
    output.add_string("schema", "facman.preferences_report.v1");
    output.add_string("operation", operation);
    output.add_string("command", operation);
    output.add_string("status", "ok");
    output.add_string("path", facman::platform::path_to_utf8(current.value().path));
    output.add_bool("present", current.value().present);
    output.add_bool("mutation_executed", false);
    output.add_bool("reset", reset);
    auto current_value = json::parse(values_json(current.value().values));
    if (current_value) output.add_value("current", current_value.value());
    if (proposed != nullptr) {
        auto proposed_value = json::parse(values_json(*proposed));
        if (proposed_value) output.add_value("proposed", proposed_value.value());
        output.add_bool("change_required", !current.value().present || values_json(current.value().values) != values_json(*proposed));
    } else output.add_bool("change_required", reset && current.value().present);
    return facman::core::Result<std::string>::success(output.serialize());
}

facman::core::Result<std::string> apply(const fs::path& workspace, const Preferences* proposed, bool reset)
{
    auto path = preferences_path();
    if (!path) return facman::core::Result<std::string>::failure(path.error());
    return apply_at(workspace, path.value(), proposed, reset);
}

facman::core::Result<std::string> apply_at(
    const fs::path& workspace,
    const fs::path& path,
    const Preferences* proposed,
    bool reset)
{
    if (!reset && proposed == nullptr) return facman::core::Result<std::string>::failure({
        "preferences_request_invalid", "Apply requires proposed preferences", "preferences"});
    if (proposed != nullptr) {
        auto valid = validate(*proposed);
        if (!valid) return facman::core::Result<std::string>::failure(valid.error());
    }
    auto current = inspect_at(path);
    if (!current) return facman::core::Result<std::string>::failure(current.error());
    if (reset && !current.value().present) {
        auto result = report_at(path, "preferences.reset.apply", nullptr, true);
        if (!result) return result;
        auto value = json::parse(result.value());
        json::ObjectBuilder output;
        output.add_string("schema", "facman.preferences_report.v1");
        output.add_string("operation", "preferences.reset.apply");
        output.add_string("command", "preferences.reset.apply");
        output.add_string("status", "ok");
        output.add_string("path", facman::platform::path_to_utf8(current.value().path));
        output.add_bool("present", false);
        output.add_bool("change_required", false);
        output.add_bool("mutation_executed", false);
        output.add_bool("reset", true);
        return facman::core::Result<std::string>::success(output.serialize());
    }
    auto parent = prepare_parent(current.value().path.parent_path());
    if (!parent) return facman::core::Result<std::string>::failure(parent.error());
    transactions::Record record;
    record.command_id = reset ? "preferences.reset.apply" : "preferences.apply";
    record.target = current.value().path;
    if (current.value().present) record.sources = {current.value().path};
    record.commit_strategy = reset ? "durable_move_to_backup" : "durable_replace_with_backup";
    auto started = transactions::TransactionSession::begin(workspace, std::move(record));
    if (!started) return facman::core::Result<std::string>::failure(started.error());
    transactions::TransactionSession session = started.take_value();
    const std::string transaction_id = session.record().transaction_id;
    const fs::path backup = current.value().path.parent_path() /
        ("preferences.v1.backup." + transaction_id + ".json");
    if (!session.validated("preferences_validated") || !session.planned("preferences_target_planned")) {
        return facman::core::Result<std::string>::failure({"preferences_journal_failed", session.detail(), workspace.string()});
    }
    if (current.value().present) {
        auto text = read_stable(current.value().path);
        if (!text) { session.failed(text.error().message); return facman::core::Result<std::string>::failure(text.error()); }
        auto backed_up = write_new(backup, text.value());
        if (!backed_up) { session.failed(backed_up.error().message); return facman::core::Result<std::string>::failure(backed_up.error()); }
        session.record().sources.push_back(backup);
    }
    if (!session.staging("backup_complete")) return facman::core::Result<std::string>::failure({
        "preferences_journal_failed", session.detail(), workspace.string()});
    if (reset) {
        if (!session.staged("preferences_backup_staged") || !session.verified("preferences_backup_verified") ||
            !session.committing("preferences_reset_started")) {
            return facman::core::Result<std::string>::failure({
                "preferences_journal_failed", session.detail(), workspace.string()});
        }
        facman::platform::FileIdentity identity;
        facman::platform::IoStatus status;
        {
            facman::platform::StableInputFile target;
            status = target.open_no_follow(current.value().path);
            if (status.ok()) identity = target.identity();
        }
        if (status.ok()) status = facman::platform::remove_exact_object(current.value().path, identity);
        if (!status.ok()) { session.failed(status.detail); return facman::core::Result<std::string>::failure({status.code, status.detail, current.value().path.string()}); }
    } else {
        const fs::path staging = current.value().path.parent_path() /
            (".preferences.v1." + transaction_id + ".staging");
        session.record().staging_roots = {staging};
        auto written = write_new(staging, values_json(*proposed));
        if (!written) { session.failed(written.error().message); return facman::core::Result<std::string>::failure(written.error()); }
        if (!session.staged("preferences_staged") || !session.verified("preferences_staging_verified") ||
            !session.committing("preferences_commit_started")) {
            return facman::core::Result<std::string>::failure({"preferences_journal_failed", session.detail(), workspace.string()});
        }
        auto status = facman::platform::replace_existing_durable(staging, current.value().path);
        if (!status.ok()) { session.failed(status.detail); return facman::core::Result<std::string>::failure({status.code, status.detail, current.value().path.string()}); }
    }
    if (!session.committed("preferences_committed") || !session.complete()) return facman::core::Result<std::string>::failure({
        "preferences_recovery_required", session.detail(), current.value().path.string(),
        facman::core::OutcomeKind::recovery_required});
    json::ObjectBuilder output;
    output.add_string("schema", "facman.preferences_report.v1");
    output.add_string("operation", reset ? "preferences.reset.apply" : "preferences.apply");
    output.add_string("command", reset ? "preferences.reset.apply" : "preferences.apply");
    output.add_string("status", "ok");
    output.add_string("path", facman::platform::path_to_utf8(current.value().path));
    output.add_bool("present", !reset);
    output.add_bool("change_required", true);
    output.add_bool("mutation_executed", true);
    output.add_bool("reset", reset);
    if (current.value().present) output.add_string("backup", facman::platform::path_to_utf8(backup));
    return facman::core::Result<std::string>::success(output.serialize());
}

} // namespace facman::preferences
