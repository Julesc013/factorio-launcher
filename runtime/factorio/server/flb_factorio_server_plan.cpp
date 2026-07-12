// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "flb_factorio_server_plan.h"

#include "fl_archive.h"
#include "fl_archive_platform.h"
#include "fl_file_io.h"
#include "fl_json.h"
#include "fl_path_safety.h"
#include "fl_sha256.h"
#include "fl_transaction.h"
#include "fl_workspace_store.h"
#include "flb_factorio_modset_operations.h"
#include "flb_factorio_save_operations.h"

#include <algorithm>
#include <cctype>
#include <filesystem>
#include <set>
#include <system_error>
#include <vector>

namespace facman::factorio::server {
namespace fs = std::filesystem;
namespace json = facman::core::json;
namespace tx = facman::transaction;
namespace {

struct Profile {
    std::string server_id;
    std::string display_name;
    std::string instance_id;
    std::string save_selection;
    std::string launch_profile;
    std::string description;
    std::uint64_t maximum_players = 0;
    std::uint64_t port = 34197;
    bool public_visibility = false;
    bool lan_visibility = true;
    std::uint64_t autosave_interval = 10;
    std::uint64_t autosave_slots = 5;
    std::vector<std::string> tags;
    std::vector<std::string> allowlist_references;
    std::vector<std::string> banlist_references;
    std::vector<std::string> credential_references;
    fs::path path;
};

struct Prepared {
    Profile profile;
    facman::workspace::InstanceRecord instance;
    facman::factorio::saves::operations::SaveRef save;
    std::string server_settings;
    std::string map_generation_settings;
    std::string map_settings;
};

template<typename T>
facman::core::Result<T> failure(
    const std::string& code,
    const std::string& message,
    const fs::path& path = {})
{
    return facman::core::Result<T>::failure(
        {code, message, facman::platform::path_to_utf8(path), facman::core::OutcomeKind::refused});
}

std::string path_text(const fs::path& path)
{
    return facman::platform::path_to_utf8(path.lexically_normal());
}

facman::core::Result<std::string> stable_text(const fs::path& path)
{
    facman::platform::StableInputFile input;
    auto status = input.open_no_follow(path);
    if (!status.ok()) return failure<std::string>("server_profile_read_failed", status.detail, path);
    if (!input.identity().regular_file || input.identity().link_count != 1U || input.size() > 1024U * 1024U) {
        return failure<std::string>("server_profile_read_failed", "Server profile is not a bounded singly-linked regular file", path);
    }
    std::string text(static_cast<std::size_t>(input.size()), '\0');
    std::uint64_t offset = 0;
    while (offset < input.size()) {
        const std::size_t count = input.read_at(offset, text.data() + offset, text.size() - static_cast<std::size_t>(offset));
        if (count == 0) return failure<std::string>("server_profile_read_failed", "Server profile read ended before EOF", path);
        offset += count;
    }
    status = input.revalidate();
    if (!status.ok()) return failure<std::string>("server_profile_drift", status.detail, path);
    return facman::core::Result<std::string>::success(std::move(text));
}

std::string string_field(const json::Value& object, const char* key, const std::string& fallback = {})
{
    const json::Value* field = object.find(key);
    if (field == nullptr) return fallback;
    auto value = field->string_value();
    return value ? value.take_value() : fallback;
}

std::uint64_t unsigned_field(const json::Value& object, const char* key, std::uint64_t fallback)
{
    const json::Value* field = object.find(key);
    if (field == nullptr) return fallback;
    auto value = field->unsigned_integer_value();
    return value ? value.value() : fallback;
}

bool bool_field(const json::Value& object, const char* key, bool fallback)
{
    const json::Value* field = object.find(key);
    if (field == nullptr) return fallback;
    auto value = field->bool_value();
    return value ? value.value() : fallback;
}

std::vector<std::string> string_array(const json::Value& object, const char* key)
{
    std::vector<std::string> output;
    const json::Value* values = object.find(key);
    if (values == nullptr || !values->is_array() || values->size() > 1024U) return output;
    for (std::size_t index = 0; index < values->size(); ++index) {
        const json::Value* item = values->at(index);
        if (item == nullptr) return {};
        auto text = item->string_value();
        if (!text) return {};
        output.push_back(text.take_value());
    }
    return output;
}

bool contains_sensitive_key(const json::Value& value)
{
    if (value.is_object()) {
        for (const std::string& key : value.object_keys()) {
            std::string lowered = key;
            std::transform(lowered.begin(), lowered.end(), lowered.begin(), [](unsigned char ch) {
                return static_cast<char>(std::tolower(ch));
            });
            if (lowered != "credential_references" && (lowered.find("password") != std::string::npos ||
                lowered.find("token") != std::string::npos || lowered.find("secret") != std::string::npos ||
                lowered.find("credential") != std::string::npos)) return true;
            const json::Value* child = value.find(key);
            if (child != nullptr && contains_sensitive_key(*child)) return true;
        }
    }
    if (value.is_array()) for (std::size_t index = 0; index < value.size(); ++index) {
        const json::Value* child = value.at(index);
        if (child != nullptr && contains_sensitive_key(*child)) return true;
    }
    return false;
}

facman::core::Result<Profile> load_profile(const fs::path& workspace, const std::string& id)
{
    auto target = facman::base::managed_file(workspace, "servers", id, ".server.v1.json");
    if (!target.ok() || !fs::is_regular_file(target.path)) return failure<Profile>(
        "unknown_server", "Server profile is not registered");
    auto text = stable_text(target.path);
    if (!text) return failure<Profile>(text.error().code, text.error().message, target.path);
    auto document = json::parse(text.value());
    if (!document || !document.value().is_object() || contains_sensitive_key(document.value())) return failure<Profile>(
        "server_profile_secret_refused", "Server profile is invalid or contains a sensitive plaintext field", target.path);
    const std::string schema = string_field(document.value(), "schema");
    if (schema != "factorio.server_profile.v2" && schema != "factorio.server.v1") return failure<Profile>(
        "server_profile_schema_invalid", "Server profile schema is unsupported", target.path);
    Profile profile;
    profile.path = target.path;
    profile.server_id = string_field(document.value(), "server_id");
    profile.display_name = string_field(document.value(), "display_name", profile.server_id);
    profile.instance_id = string_field(document.value(), "instance_id");
    profile.save_selection = string_field(document.value(), "save_selection");
    profile.launch_profile = string_field(document.value(), "launch_profile", "headless-plan");
    profile.description = string_field(document.value(), "description");
    const json::Value* settings = document.value().find("server_settings");
    if (settings != nullptr && settings->is_object()) {
        profile.maximum_players = unsigned_field(*settings, "maximum_players", 0);
        profile.port = unsigned_field(*settings, "port", 34197);
    }
    const json::Value* visibility = document.value().find("visibility_policy");
    if (visibility != nullptr && visibility->is_object()) {
        profile.public_visibility = bool_field(*visibility, "public", false);
        profile.lan_visibility = bool_field(*visibility, "lan", true);
    }
    const json::Value* autosave = document.value().find("autosave_policy");
    if (autosave != nullptr && autosave->is_object()) {
        profile.autosave_interval = unsigned_field(*autosave, "interval_minutes", 10);
        profile.autosave_slots = unsigned_field(*autosave, "slots", 5);
    }
    profile.tags = string_array(document.value(), "tags");
    profile.allowlist_references = string_array(document.value(), "allowlist_references");
    profile.banlist_references = string_array(document.value(), "banlist_references");
    profile.credential_references = string_array(document.value(), "credential_references");
    if (profile.server_id != id || profile.instance_id.empty()) return failure<Profile>(
        "server_profile_invalid", "Server profile identity or instance reference is invalid", target.path);
    return facman::core::Result<Profile>::success(std::move(profile));
}

json::ArrayBuilder strings(const std::vector<std::string>& values)
{
    json::ArrayBuilder output;
    for (const std::string& value : values) output.add_string(value);
    return output;
}

std::string server_settings(const Profile& profile)
{
    json::ObjectBuilder visibility;
    visibility.add_bool("public", profile.public_visibility);
    visibility.add_bool("lan", profile.lan_visibility);
    json::ObjectBuilder output;
    output.add_string("name", profile.display_name);
    output.add_string("description", profile.description);
    output.add_array("tags", strings(profile.tags));
    (void)output.add_unsigned_integer("max_players", profile.maximum_players);
    output.add_object("visibility", visibility);
    output.add_array("credential_references", strings(profile.credential_references));
    return output.serialize() + "\n";
}

std::string map_generation_settings()
{
    json::ObjectBuilder output;
    output.add_string("preset", "default");
    output.add_bool("deterministic_profile_default", true);
    return output.serialize() + "\n";
}

std::string map_settings()
{
    json::ObjectBuilder output;
    output.add_string("difficulty", "normal");
    return output.serialize() + "\n";
}

facman::core::Result<Prepared> prepare(const fs::path& workspace, const Request& request)
{
    auto profile = load_profile(workspace, request.server_id);
    if (!profile) return failure<Prepared>(profile.error().code, profile.error().message, fs::u8path(profile.error().path));
    auto instance_id = facman::core::InstanceId::parse(profile.value().instance_id);
    if (!instance_id) return failure<Prepared>("unknown_instance", "Server instance reference is invalid");
    auto instance = facman::workspace::InstanceRepository(facman::workspace::WorkspaceLayout(workspace)).load(instance_id.value());
    if (!instance) return failure<Prepared>("unknown_instance", "Server instance is not registered");
    if (profile.value().port == 0 || profile.value().port > 65535 || profile.value().maximum_players > 65535 ||
        profile.value().autosave_interval == 0 || profile.value().autosave_slots == 0) return failure<Prepared>(
            "server_settings_invalid", "Server port, player, or autosave policy is invalid", profile.value().path);
    const std::string save_name = request.save.empty() ? profile.value().save_selection : request.save;
    if (save_name.empty()) return failure<Prepared>("server_save_required", "A structurally valid instance save must be selected");
    auto saves = facman::factorio::saves::operations::list_saves(workspace, {profile.value().instance_id});
    auto* listed = std::get_if<facman::factorio::saves::operations::ListResult>(&saves);
    if (listed == nullptr) return failure<Prepared>("server_save_invalid", "Server instance saves could not be indexed");
    facman::factorio::saves::operations::SaveRef save;
    bool found = false;
    for (const auto& value : listed->saves) if (value.name == save_name || value.file_name == save_name) {
        save = value; found = true; break;
    }
    if (!found || !save.archive_structurally_valid || !save.factorio_save_recognized) return failure<Prepared>(
        "server_save_invalid", "Selected save is missing or not structurally recognized");
    auto modset = facman::factorio::modsets::operations::verify_modset(workspace, {profile.value().instance_id});
    auto* verified = std::get_if<facman::factorio::modsets::operations::VerifyResult>(&modset);
    if (verified == nullptr || !verified->problems.empty()) return failure<Prepared>(
        "server_modset_invalid", "Instance modset must verify before server planning");
    Prepared output;
    output.profile = profile.take_value();
    output.instance = instance.take_value();
    output.save = std::move(save);
    output.server_settings = server_settings(output.profile);
    output.map_generation_settings = map_generation_settings();
    output.map_settings = map_settings();
    return facman::core::Result<Prepared>::success(std::move(output));
}

json::ObjectBuilder profile_json(const Profile& profile)
{
    json::ObjectBuilder output;
    output.add_string("schema", "factorio.server_profile.v2");
    output.add_string("server_id", profile.server_id);
    output.add_string("display_name", profile.display_name);
    output.add_string("instance_id", profile.instance_id);
    output.add_string("save_selection", profile.save_selection);
    output.add_string("launch_profile", profile.launch_profile);
    output.add_string("description", profile.description);
    (void)output.add_unsigned_integer("maximum_players", profile.maximum_players);
    (void)output.add_unsigned_integer("port", profile.port);
    output.add_array("tags", strings(profile.tags));
    output.add_array("allowlist_references", strings(profile.allowlist_references));
    output.add_array("banlist_references", strings(profile.banlist_references));
    output.add_array("credential_references", strings(profile.credential_references));
    return output;
}

std::string plan_json(const Prepared& prepared, const std::string& command, bool portable = false)
{
    auto server = json::parse(prepared.server_settings);
    auto map_gen = json::parse(prepared.map_generation_settings);
    auto map = json::parse(prepared.map_settings);
    json::ArrayBuilder arguments;
    const std::string save_path = portable ? "$FACMAN_INSTANCE_ROOT/saves/" + prepared.save.file_name : path_text(prepared.save.path);
    arguments.add_string("--start-server"); arguments.add_string(save_path);
    arguments.add_string("--server-settings"); arguments.add_string("server-settings.json");
    json::ObjectBuilder launch;
    launch.add_string("mode", "headless-plan");
    launch.add_array("arguments", arguments);
    launch.add_bool("execution_enabled", false);
    json::ArrayBuilder inputs;
    inputs.add_string(save_path);
    inputs.add_string(portable ? "server-profile.v2.json" : path_text(prepared.profile.path));
    inputs.add_string(portable ? "$FACMAN_INSTANCE_ROOT/mods/modset-lock.v1.json" :
        path_text(prepared.instance.root / "mods" / "modset-lock.v1.json"));
    json::ArrayBuilder roots;
    roots.add_string(portable ? "$FACMAN_INSTANCE_ROOT/script-output" : path_text(prepared.instance.root / "script-output"));
    roots.add_string(portable ? "$FACMAN_INSTANCE_ROOT/logs" : path_text(prepared.instance.root / "logs"));
    json::ArrayBuilder effects;
    effects.add_string("read_instance_save"); effects.add_string("read_verified_modset"); effects.add_string("generate_config_only");
    json::ArrayBuilder risks;
    risks.add_string("server execution remains unavailable"); risks.add_string("port is declared but no socket is opened");
    json::ObjectBuilder preflight;
    preflight.add_bool("instance_exists", true); preflight.add_bool("save_structurally_valid", true);
    preflight.add_bool("modset_verified", true); preflight.add_bool("settings_valid", true);
    preflight.add_bool("credential_references_only", true); preflight.add_bool("global_factorio_roots", false);
    json::ObjectBuilder output;
    output.add_string("schema", "factorio.server_plan.v1");
    output.add_string("command", command);
    output.add_string("status", "ok");
    output.add_object("profile", profile_json(prepared.profile));
    if (server) output.add_value("server_settings", server.value()); else output.add_null("server_settings");
    if (map_gen) output.add_value("map_generation_settings", map_gen.value()); else output.add_null("map_generation_settings");
    if (map) output.add_value("map_settings", map.value()); else output.add_null("map_settings");
    output.add_object("effective_launch_plan", launch);
    output.add_array("required_input_files", inputs);
    output.add_array("expected_output_roots", roots);
    (void)output.add_unsigned_integer("port", prepared.profile.port);
    output.add_array("effects", effects); output.add_array("risks", risks); output.add_object("preflight", preflight);
    output.add_bool("process_started", false); output.add_bool("network_socket_opened", false);
    output.add_bool("firewall_changed", false); output.add_bool("mutation_executed", false);
    return output.serialize();
}

bool write_generated(const fs::path& root, const std::string& name, const std::string& text, fs::path& path)
{
    path = root / fs::u8path(name);
    std::string detail;
    return facman::base::write_text_new_atomic(path, text, detail);
}

} // namespace

facman::core::Result<std::string> inspect(const fs::path& workspace, const Request& request)
{
    auto profile = load_profile(workspace, request.server_id);
    if (!profile) return failure<std::string>(profile.error().code, profile.error().message, fs::u8path(profile.error().path));
    json::ObjectBuilder output;
    output.add_string("schema", "factorio.server_profile_report.v1");
    output.add_string("command", "servers.inspect"); output.add_string("status", "ok");
    output.add_object("profile", profile_json(profile.value()));
    output.add_bool("process_started", false); output.add_bool("network_socket_opened", false);
    output.add_bool("firewall_changed", false); output.add_bool("mutation_executed", false);
    return facman::core::Result<std::string>::success(output.serialize());
}

facman::core::Result<std::string> validate(const fs::path& workspace, const Request& request)
{
    auto prepared = prepare(workspace, request);
    if (!prepared) return failure<std::string>(prepared.error().code, prepared.error().message, fs::u8path(prepared.error().path));
    return facman::core::Result<std::string>::success(plan_json(prepared.value(), "servers.validate"));
}

facman::core::Result<std::string> plan(const fs::path& workspace, const Request& request)
{
    auto prepared = prepare(workspace, request);
    if (!prepared) return failure<std::string>(prepared.error().code, prepared.error().message, fs::u8path(prepared.error().path));
    return facman::core::Result<std::string>::success(plan_json(prepared.value(), "servers.plan"));
}

facman::core::Result<std::string> diff(const fs::path& workspace, const Request& request)
{
    auto left = load_profile(workspace, request.server_id);
    auto right = load_profile(workspace, request.other_server_id);
    if (!left || !right) return failure<std::string>("unknown_server", "Both server profiles are required for diff");
    json::ArrayBuilder differences;
    auto add = [&](const char* field, const std::string& lhs, const std::string& rhs) {
        if (lhs == rhs) return;
        json::ObjectBuilder item; item.add_string("field", field); item.add_string("left", lhs); item.add_string("right", rhs);
        differences.add_object(item);
    };
    add("instance_id", left.value().instance_id, right.value().instance_id);
    add("save_selection", left.value().save_selection, right.value().save_selection);
    add("launch_profile", left.value().launch_profile, right.value().launch_profile);
    add("port", std::to_string(left.value().port), std::to_string(right.value().port));
    json::ObjectBuilder output;
    output.add_string("schema", "factorio.server_diff.v1"); output.add_string("command", "servers.diff");
    output.add_string("status", "ok"); output.add_object("left", profile_json(left.value()));
    output.add_object("right", profile_json(right.value())); output.add_array("differences", differences);
    output.add_bool("process_started", false); output.add_bool("network_socket_opened", false);
    output.add_bool("firewall_changed", false); output.add_bool("mutation_executed", false);
    return facman::core::Result<std::string>::success(output.serialize());
}

facman::core::Result<std::string> export_bundle(const fs::path& workspace, const Request& request)
{
    auto prepared = prepare(workspace, request);
    if (!prepared) return failure<std::string>(prepared.error().code, prepared.error().message, fs::u8path(prepared.error().path));
    if (request.output_path.empty() || fs::exists(request.output_path)) return failure<std::string>(
        "server_export_target_invalid", "Server plan export target must be a new path", request.output_path);
    std::error_code error;
    fs::create_directories(request.output_path.parent_path(), error);
    if (error) return failure<std::string>("server_export_write_failed", error.message(), request.output_path);
    const std::string suffix = prepared.value().profile.server_id;
    const fs::path payload = request.output_path.parent_path() / fs::u8path(".server-plan-payload-" + suffix);
    const fs::path staging = request.output_path.parent_path() / fs::u8path(".server-plan-archive-" + suffix);
    if (fs::exists(payload) || fs::exists(staging)) return failure<std::string>("server_export_target_invalid", "Export staging already exists");
    tx::Record transaction;
    transaction.command_id = "servers.export"; transaction.target = request.output_path;
    transaction.sources = {prepared.value().profile.path, prepared.value().save.path};
    transaction.staging_roots = {payload, staging};
    transaction.commit_strategy = "deterministic_secret_free_server_plan_bundle";
    auto started = tx::TransactionSession::begin(workspace, std::move(transaction));
    if (!started) return failure<std::string>("server_export_failed", started.error().message);
    tx::TransactionSession session = started.take_value();
    if (!session.validated("profile_save_modset_and_target_validated") || !session.planned("portable_bundle_planned")) {
        return failure<std::string>("server_export_failed", session.detail());
    }
    auto status = facman::archive::create_owned_staging_root(payload);
    if (!status.ok() || !session.staging("owned_payload_staging_created")) return failure<std::string>(
        "server_export_failed", status.ok() ? session.detail() : status.detail, payload);
    std::vector<facman::archive::WriteEntry> entries;
    fs::path generated;
    const std::string planned = plan_json(prepared.value(), "servers.plan", true);
    for (const auto& file : std::vector<std::pair<std::string, std::string>> {
            {"server-profile.v2.json", profile_json(prepared.value().profile).serialize() + "\n"},
            {"server-settings.json", prepared.value().server_settings},
            {"map-gen-settings.json", prepared.value().map_generation_settings},
            {"map-settings.json", prepared.value().map_settings}, {"server-plan.json", planned + "\n"}}) {
        if (!write_generated(payload, file.first, file.second, generated)) return failure<std::string>(
            "server_export_write_failed", "Generated server configuration could not be staged", payload);
        entries.push_back({file.first, generated, false});
    }
    json::ArrayBuilder hashes;
    for (const auto& entry : entries) {
        json::ObjectBuilder item; item.add_string("path", entry.archive_path);
        item.add_string("sha256", facman::base::sha256_hex_file(entry.source_path)); hashes.add_object(item);
    }
    json::ObjectBuilder manifest;
    manifest.add_string("schema", "factorio.server_plan_bundle.v1");
    manifest.add_string("server_id", prepared.value().profile.server_id);
    manifest.add_array("files", hashes); manifest.add_bool("contains_secrets", false);
    manifest.add_bool("contains_factorio_binary", false); manifest.add_bool("contains_execution_scripts", false);
    manifest.add_bool("contains_save", request.include_save);
    if (!write_generated(payload, "manifest.json", manifest.serialize() + "\n", generated)) return failure<std::string>(
        "server_export_write_failed", "Bundle manifest could not be staged", payload);
    entries.push_back({"manifest.json", generated, false});
    if (request.include_save) entries.push_back({"save/" + prepared.value().save.file_name, prepared.value().save.path, false});
    if (!session.staged("reviewed_secret_free_config_staged")) return failure<std::string>("server_export_failed", session.detail());
    facman::archive::WriteOptions options;
    options.method = facman::archive::CompressionMethod::deflate; options.reproducible = true;
    options.limits = facman::archive::InstanceTransferPolicy::limits();
    facman::archive::WriteResult written;
    status = facman::archive::write_to_new_owned_staging(
        staging, request.output_path.filename().string(), entries, options, written);
    if (!status.ok() || !session.verified("portable_bundle_hashes_verified") || !session.committing("bundle_commit_started")) {
        return failure<std::string>("server_export_failed", status.ok() ? session.detail() : status.detail, staging);
    }
    std::string detail;
    if (!tx::StagedFileCommit::commit(staging, written.archive_path, request.output_path, detail)) return failure<std::string>(
        "server_export_write_failed", detail, request.output_path);
    (void)facman::archive::cleanup_owned_staging_root(payload);
    (void)facman::archive::cleanup_owned_staging_root(staging);
    if (!session.committed("server_plan_bundle_committed") || !session.complete()) return failure<std::string>(
        "server_export_recovery_required", session.detail(), request.output_path);
    json::ObjectBuilder output;
    output.add_string("schema", "factorio.server_export.v1"); output.add_string("command", "servers.export");
    output.add_string("status", "ok"); output.add_string("server_id", prepared.value().profile.server_id);
    output.add_string("path", path_text(request.output_path)); output.add_bool("contains_save", request.include_save);
    output.add_bool("contains_secrets", false); output.add_bool("contains_factorio_binary", false);
    output.add_bool("contains_execution_scripts", false); output.add_bool("process_started", false);
    output.add_bool("network_socket_opened", false); output.add_bool("firewall_changed", false);
    output.add_bool("mutation_executed", true);
    return facman::core::Result<std::string>::success(output.serialize());
}

} // namespace facman::factorio::server
