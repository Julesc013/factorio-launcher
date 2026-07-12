// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "flb_factorio_profiles.h"

#include "fl_file_io.h"
#include "fl_json.h"
#include "fl_path_safety.h"
#include "fl_sha256.h"
#include "fl_system_services.h"
#include "fl_transaction.h"
#include "fl_workspace_store.h"

#include <algorithm>
#include <set>
#include <system_error>

namespace facman::factorio::profiles {
namespace fs = std::filesystem;
namespace json = facman::core::json;
namespace tx = facman::transaction;
namespace {

constexpr std::size_t kMaximumProfileBytes = 1024U * 1024U;

struct Profile {
    std::string id;
    std::string template_id;
    Settings settings;
    bool shipped = false;
    fs::path source;
};

facman::core::Result<std::string> failure(
    const std::string& code,
    const std::string& message,
    const fs::path& path = {},
    facman::core::OutcomeKind kind = facman::core::OutcomeKind::refused,
    bool recoverable = true)
{
    facman::core::Error error {code, message, facman::platform::path_to_utf8(path), kind};
    error.recoverable = recoverable && kind != facman::core::OutcomeKind::recovery_required;
    error.retryable = error.recoverable;
    return facman::core::Result<std::string>::failure(std::move(error));
}

template<typename T>
facman::core::Result<T> typed_failure(
    const std::string& code,
    const std::string& message,
    const fs::path& path = {})
{
    return facman::core::Result<T>::failure(
        {code, message, facman::platform::path_to_utf8(path), facman::core::OutcomeKind::refused});
}

std::string object_string(const json::Value& object, const char* key)
{
    const json::Value* field = object.find(key);
    if (field == nullptr) return {};
    auto value = field->string_value();
    return value ? value.take_value() : std::string {};
}

facman::core::Result<std::string> stable_text(const fs::path& path)
{
    facman::platform::StableInputFile input;
    auto status = input.open_no_follow(path);
    if (!status.ok()) return typed_failure<std::string>("profile_read_failed", status.detail, path);
    if (!input.identity().regular_file || input.identity().link_count != 1U || input.size() > kMaximumProfileBytes) {
        return typed_failure<std::string>("profile_read_failed", "Profile is not a bounded singly-linked regular file", path);
    }
    std::string text(static_cast<std::size_t>(input.size()), '\0');
    std::uint64_t offset = 0;
    while (offset < input.size()) {
        const std::size_t read = input.read_at(offset, text.data() + offset, text.size() - static_cast<std::size_t>(offset));
        if (read == 0) return typed_failure<std::string>("profile_read_failed", "Profile read stopped before EOF", path);
        offset += read;
    }
    status = input.revalidate();
    if (!status.ok()) return typed_failure<std::string>("profile_read_failed", status.detail, path);
    return facman::core::Result<std::string>::success(std::move(text));
}

bool valid_save_name(const std::string& value)
{
    return !value.empty() && value.size() <= 255U && value.find('/') == std::string::npos &&
        value.find('\\') == std::string::npos && fs::path(value).extension() == ".zip";
}

const std::set<std::string>& safe_arguments()
{
    static const std::set<std::string> values = {
        "--disable-audio", "--force-opengl", "--force-d3d", "--low-vram", "--no-log-rotation",
    };
    return values;
}

facman::core::Result<void> validate_settings(const Settings& settings)
{
    if (settings.window_mode != "windowed" && settings.window_mode != "fullscreen") return facman::core::Result<void>::failure(
        {"profile_window_mode_invalid", "Window mode must be windowed or fullscreen", "window_mode"});
    if (settings.graphics_quality != "low" && settings.graphics_quality != "medium" && settings.graphics_quality != "high") {
        return facman::core::Result<void>::failure(
            {"profile_graphics_quality_invalid", "Graphics quality must be low, medium, or high", "graphics_quality"});
    }
    if (settings.audio != "enabled" && settings.audio != "disabled") return facman::core::Result<void>::failure(
        {"profile_audio_invalid", "Audio must be enabled or disabled", "audio"});
    if (settings.selection_mode != "none" && settings.selection_mode != "load-save" &&
        settings.selection_mode != "benchmark-save") return facman::core::Result<void>::failure(
            {"profile_selection_invalid", "Selection mode is not allowlisted", "selection_mode"});
    if (settings.selection_mode == "none" ? !settings.selection.empty() : !valid_save_name(settings.selection)) {
        return facman::core::Result<void>::failure(
            {"profile_selection_invalid", "Selection must be an instance-local save archive name", "selection"});
    }
    if (settings.launch_mode != "gui" && settings.launch_mode != "headless-plan" && settings.launch_mode != "benchmark-preview") {
        return facman::core::Result<void>::failure(
            {"profile_launch_mode_invalid", "Launch mode is not an allowlisted planning mode", "launch_mode"});
    }
    if (settings.benchmark_ticks > 100000000U ||
        (settings.launch_mode == "benchmark-preview" && (settings.benchmark_ticks == 0 || settings.selection_mode != "benchmark-save"))) {
        return facman::core::Result<void>::failure(
            {"profile_benchmark_invalid", "Benchmark preview requires a selected save and bounded non-zero ticks", "benchmark_ticks"});
    }
    if (settings.additional_arguments.size() > 32U) return facman::core::Result<void>::failure(
        {"profile_arguments_invalid", "Additional argument count exceeds 32", "additional_arguments"});
    std::set<std::string> unique;
    for (const std::string& argument : settings.additional_arguments) {
        if (safe_arguments().count(argument) == 0 || !unique.insert(argument).second) return facman::core::Result<void>::failure(
            {"profile_arguments_invalid", "Additional argument is duplicate, reserved, or not allowlisted", argument});
    }
    return facman::core::Result<void>::success();
}

facman::core::Result<Settings> apply_patch(Settings settings, const Patch& patch)
{
    if (!patch.window_mode.empty()) settings.window_mode = patch.window_mode;
    if (!patch.graphics_quality.empty()) settings.graphics_quality = patch.graphics_quality;
    if (!patch.audio.empty()) settings.audio = patch.audio;
    if (!patch.selection_mode.empty()) settings.selection_mode = patch.selection_mode;
    if (!patch.selection.empty()) settings.selection = patch.selection;
    if (!patch.launch_mode.empty()) settings.launch_mode = patch.launch_mode;
    if (!patch.benchmark_ticks.empty()) {
        if (!std::all_of(patch.benchmark_ticks.begin(), patch.benchmark_ticks.end(), [](unsigned char ch) { return ch >= '0' && ch <= '9'; })) {
            return typed_failure<Settings>("profile_benchmark_invalid", "Benchmark ticks must be an unsigned integer");
        }
        try {
            const unsigned long value = std::stoul(patch.benchmark_ticks);
            if (value > 100000000UL) throw std::out_of_range("benchmark ticks");
            settings.benchmark_ticks = static_cast<std::uint32_t>(value);
        } catch (...) {
            return typed_failure<Settings>("profile_benchmark_invalid", "Benchmark ticks exceed the allowed range");
        }
    }
    if (!patch.additional_arguments.empty()) {
        std::set<std::string> existing(settings.additional_arguments.begin(), settings.additional_arguments.end());
        for (const std::string& value : patch.additional_arguments) if (existing.insert(value).second) {
            settings.additional_arguments.push_back(value);
        }
    }
    auto valid = validate_settings(settings);
    if (!valid) return typed_failure<Settings>(valid.error().code, valid.error().message, fs::u8path(valid.error().path));
    return facman::core::Result<Settings>::success(std::move(settings));
}

json::ObjectBuilder settings_builder(const Settings& settings)
{
    json::ArrayBuilder arguments;
    for (const std::string& value : settings.additional_arguments) arguments.add_string(value);
    json::ObjectBuilder output;
    output.add_string("window_mode", settings.window_mode);
    output.add_string("graphics_quality", settings.graphics_quality);
    output.add_string("audio", settings.audio);
    output.add_string("selection_mode", settings.selection_mode);
    if (settings.selection.empty()) output.add_null("selection"); else output.add_string("selection", settings.selection);
    output.add_string("launch_mode", settings.launch_mode);
    (void)output.add_unsigned_integer("benchmark_ticks", settings.benchmark_ticks);
    output.add_array("additional_arguments", arguments);
    return output;
}

std::string profile_json(const Profile& profile)
{
    json::ObjectBuilder portability;
    portability.add_bool("machine_local_paths", false);
    portability.add_bool("credentials", false);
    portability.add_bool("scripts", false);
    json::ObjectBuilder output;
    output.add_string("schema", "factorio.launch_profile.v1");
    output.add_string("profile_id", profile.id);
    output.add_string("template_id", profile.template_id);
    output.add_object("settings", settings_builder(profile.settings));
    output.add_object("portability", portability);
    return output.serialize() + "\n";
}

std::string template_json()
{
    json::ObjectBuilder directories;
    for (const char* value : {"config", "mods", "saves", "scenarios", "script-output", "logs", "crash", "exports", "cache", "locks"}) {
        directories.add_string(value, "instance-local");
    }
    json::ObjectBuilder policies;
    policies.add_string("mods", "instance-local-lockfile");
    policies.add_string("saves", "instance-local-explicit-selection");
    policies.add_string("logs", "instance-local-rotating");
    policies.add_string("backups", "workspace-owned-retention");
    json::ObjectBuilder forbidden;
    forbidden.add_bool("shell_commands", true);
    forbidden.add_bool("arbitrary_executables", true);
    forbidden.add_bool("setup_mutation", true);
    forbidden.add_bool("network_endpoints", true);
    forbidden.add_bool("credentials", true);
    forbidden.add_bool("scripts", true);
    json::ObjectBuilder output;
    output.add_string("schema", "factorio.instance_template.v1");
    output.add_string("command", "templates.inspect");
    output.add_string("template_id", "vanilla");
    output.add_string("display_name_default", "Vanilla instance");
    output.add_object("directory_policy", directories);
    output.add_object("content_policy", policies);
    output.add_string("launch_mode", "gui");
    output.add_object("safe_settings", settings_builder(Settings {}));
    output.add_object("forbidden_capabilities", forbidden);
    output.add_bool("mutation_executed", false);
    return output.serialize();
}

facman::core::Result<Profile> parse_profile(const fs::path& path, const std::string& expected_id)
{
    auto text = stable_text(path);
    if (!text) return typed_failure<Profile>(text.error().code, text.error().message, path);
    json::Limits limits;
    limits.maximum_bytes = kMaximumProfileBytes;
    limits.maximum_depth = 8;
    limits.maximum_nodes = 1024;
    auto document = json::parse(text.value(), limits);
    if (!document || !document.value().is_object() || object_string(document.value(), "schema") != "factorio.launch_profile.v1") {
        return typed_failure<Profile>("profile_document_invalid", "Profile document schema is invalid", path);
    }
    Profile profile;
    profile.id = object_string(document.value(), "profile_id");
    profile.template_id = object_string(document.value(), "template_id");
    profile.source = path;
    const json::Value* settings = document.value().find("settings");
    if (profile.id != expected_id || profile.template_id != "vanilla" || settings == nullptr || !settings->is_object()) {
        return typed_failure<Profile>("profile_document_invalid", "Profile identity, template, or settings are invalid", path);
    }
    profile.settings.window_mode = object_string(*settings, "window_mode");
    profile.settings.graphics_quality = object_string(*settings, "graphics_quality");
    profile.settings.audio = object_string(*settings, "audio");
    profile.settings.selection_mode = object_string(*settings, "selection_mode");
    const json::Value* selection = settings->find("selection");
    if (selection != nullptr && !selection->is_null()) profile.settings.selection = object_string(*settings, "selection");
    profile.settings.launch_mode = object_string(*settings, "launch_mode");
    const json::Value* ticks = settings->find("benchmark_ticks");
    auto tick_value = ticks == nullptr ? facman::core::Result<std::uint64_t>::failure(
        {"profile_document_invalid", "Benchmark ticks are missing", "benchmark_ticks"}) : ticks->unsigned_integer_value();
    const json::Value* arguments = settings->find("additional_arguments");
    if (!tick_value || tick_value.value() > 100000000U || arguments == nullptr || !arguments->is_array() || arguments->size() > 32U) {
        return typed_failure<Profile>("profile_document_invalid", "Profile numeric or argument settings are invalid", path);
    }
    profile.settings.benchmark_ticks = static_cast<std::uint32_t>(tick_value.value());
    for (std::size_t index = 0; index < arguments->size(); ++index) {
        const json::Value* item = arguments->at(index);
        auto value = item == nullptr ? facman::core::Result<std::string>::failure(
            {"profile_document_invalid", "Profile argument is missing", "additional_arguments"}) : item->string_value();
        if (!value) return typed_failure<Profile>("profile_document_invalid", "Profile argument is not a string", path);
        profile.settings.additional_arguments.push_back(value.take_value());
    }
    auto valid = validate_settings(profile.settings);
    if (!valid) return typed_failure<Profile>(valid.error().code, valid.error().message, path);
    return facman::core::Result<Profile>::success(std::move(profile));
}

facman::core::Result<Profile> load_profile(const fs::path& workspace, const std::string& id)
{
    std::string detail;
    if (!facman::base::validate_identifier(id, detail)) return typed_failure<Profile>("profile_id_invalid", detail);
    if (id == "gui") {
        Profile profile;
        profile.id = "gui";
        profile.template_id = "vanilla";
        profile.shipped = true;
        return facman::core::Result<Profile>::success(std::move(profile));
    }
    auto root = facman::base::managed_directory(workspace, "profiles", id);
    if (!root.ok()) return typed_failure<Profile>(root.code, root.detail, root.path);
    const fs::path path = root.path / "profile.v1.json";
    if (!fs::is_regular_file(path)) return typed_failure<Profile>("unknown_profile", "Launch profile is not registered", path);
    return parse_profile(path, id);
}

std::vector<std::string> launch_arguments(const Settings& settings)
{
    std::vector<std::string> output;
    if (settings.audio == "disabled") output.push_back("--disable-audio");
    if (settings.selection_mode == "load-save") {
        output.push_back("--load-game");
        output.push_back("$FACMAN_INSTANCE_ROOT/saves/" + settings.selection);
    } else if (settings.selection_mode == "benchmark-save") {
        output.push_back("--benchmark");
        output.push_back("$FACMAN_INSTANCE_ROOT/saves/" + settings.selection);
        output.push_back("--benchmark-ticks");
        output.push_back(std::to_string(settings.benchmark_ticks));
    }
    for (const std::string& argument : settings.additional_arguments) {
        if (std::find(output.begin(), output.end(), argument) == output.end()) output.push_back(argument);
    }
    return output;
}

std::string profile_report(const std::string& command, const Profile& profile, bool mutation)
{
    json::ObjectBuilder output;
    output.add_string("schema", "factorio.launch_profile_report.v1");
    output.add_string("command", command);
    output.add_string("status", "ok");
    output.add_string("profile_id", profile.id);
    output.add_string("template_id", profile.template_id);
    output.add_bool("shipped", profile.shipped);
    output.add_object("settings", settings_builder(profile.settings));
    output.add_bool("portable", true);
    output.add_bool("arbitrary_execution", false);
    output.add_bool("mutation_executed", mutation);
    return output.serialize();
}

facman::core::Result<void> write_profile_new(const fs::path& workspace, const Profile& profile)
{
    auto root = facman::base::managed_directory(workspace, "profiles", profile.id);
    if (!root.ok()) return facman::core::Result<void>::failure({root.code, root.detail, facman::platform::path_to_utf8(root.path)});
    if (fs::exists(root.path)) return facman::core::Result<void>::failure(
        {"profile_target_exists", "Profile target already exists", facman::platform::path_to_utf8(root.path)});
    fs::path staging = root.path;
    staging += ".facman-staging";
    if (fs::exists(staging)) return facman::core::Result<void>::failure(
        {"profile_staging_exists", "Profile staging target already exists", facman::platform::path_to_utf8(staging)});
    std::error_code error;
    fs::create_directories(staging, error);
    std::string detail;
    if (error || !facman::base::write_text_new_atomic(staging / ".facman-staging.v1", "facman-profile-staging-v1\n", detail) ||
        !facman::base::write_text_new_atomic(staging / "profile.v1.json", profile_json(profile), detail) ||
        !facman::base::commit_directory_no_clobber(staging, root.path, detail)) {
        std::string cleanup;
        (void)facman::base::remove_owned_staging_tree(staging, ".facman-staging.v1", cleanup);
        return facman::core::Result<void>::failure(
            {"profile_write_failed", error ? error.message() : detail, facman::platform::path_to_utf8(root.path)});
    }
    fs::remove(root.path / ".facman-staging.v1", error);
    if (error) return facman::core::Result<void>::failure(
        {"profile_write_failed", error.message(), facman::platform::path_to_utf8(root.path)});
    return facman::core::Result<void>::success();
}

std::string instance_manifest(const facman::workspace::InstanceRecord& instance, const std::string& profile_id)
{
    json::ObjectBuilder concurrency;
    concurrency.add_bool("single_writer", true);
    json::ObjectBuilder output;
    output.add_string("schema", "factorio.instance.v1");
    output.add_string("instance_id", instance.id.str());
    output.add_string("display_name", instance.display_name);
    output.add_string("install_ref", instance.install_ref.str());
    output.add_string("factorio_version", instance.factorio_version);
    output.add_string("local_data_root", facman::platform::path_to_utf8(instance.root));
    output.add_string("profile", profile_id);
    output.add_string("template", instance.template_id);
    output.add_object("concurrency", concurrency);
    return output.serialize() + "\n";
}

std::string overrides_json(const EffectiveRequest& request)
{
    json::ArrayBuilder arguments;
    for (const std::string& value : request.overrides.additional_arguments) arguments.add_string(value);
    json::ObjectBuilder values;
    if (!request.overrides.window_mode.empty()) values.add_string("window_mode", request.overrides.window_mode);
    if (!request.overrides.graphics_quality.empty()) values.add_string("graphics_quality", request.overrides.graphics_quality);
    if (!request.overrides.audio.empty()) values.add_string("audio", request.overrides.audio);
    if (!request.overrides.selection_mode.empty()) values.add_string("selection_mode", request.overrides.selection_mode);
    if (!request.overrides.selection.empty()) values.add_string("selection", request.overrides.selection);
    if (!request.overrides.launch_mode.empty()) values.add_string("launch_mode", request.overrides.launch_mode);
    if (!request.overrides.benchmark_ticks.empty()) values.add_string("benchmark_ticks", request.overrides.benchmark_ticks);
    if (!request.overrides.additional_arguments.empty()) values.add_array("additional_arguments", arguments);
    json::ObjectBuilder output;
    output.add_string("schema", "factorio.instance_overrides.v1");
    output.add_string("instance_id", request.instance_id);
    output.add_string("profile_id", request.profile_id);
    output.add_object("values", values);
    return output.serialize() + "\n";
}

std::string effective_report(
    const std::string& command,
    const EffectiveRequest& request,
    const EffectiveProfile& effective,
    bool mutation,
    const std::string& transaction_id = {})
{
    json::ArrayBuilder arguments;
    for (const std::string& value : effective.launch_arguments) arguments.add_string(value);
    json::ObjectBuilder output;
    output.add_string("schema", "factorio.effective_profile.v1");
    output.add_string("command", command);
    output.add_string("status", "ok");
    output.add_string("instance_id", request.instance_id);
    output.add_string("profile_id", effective.profile_id);
    output.add_string("template_id", effective.template_id);
    output.add_object("settings", settings_builder(effective.settings));
    output.add_array("launch_arguments", arguments);
    output.add_bool("reserved_arguments_controlled_by_facman", true);
    output.add_bool("execution_enabled", false);
    output.add_bool("mutation_executed", mutation);
    if (!transaction_id.empty()) output.add_string("transaction_id", transaction_id);
    return output.serialize();
}

} // namespace

facman::core::Result<EffectiveProfile> effective_profile(
    const fs::path& workspace,
    const std::string& profile_id,
    const Patch& overrides)
{
    auto loaded = load_profile(workspace, profile_id.empty() ? "gui" : profile_id);
    if (!loaded) return typed_failure<EffectiveProfile>(loaded.error().code, loaded.error().message, fs::u8path(loaded.error().path));
    auto settings = apply_patch(loaded.value().settings, overrides);
    if (!settings) return typed_failure<EffectiveProfile>(settings.error().code, settings.error().message, fs::u8path(settings.error().path));
    EffectiveProfile output;
    output.profile_id = loaded.value().id;
    output.template_id = loaded.value().template_id;
    output.settings = settings.take_value();
    output.launch_arguments = launch_arguments(output.settings);
    return facman::core::Result<EffectiveProfile>::success(std::move(output));
}

facman::core::Result<EffectiveProfile> effective_profile_for_instance(
    const fs::path& workspace,
    const std::string& instance_id,
    const std::string& profile_id)
{
    auto parsed = facman::core::InstanceId::parse(instance_id);
    if (!parsed) return typed_failure<EffectiveProfile>(parsed.error().code, parsed.error().message);
    const fs::path path = workspace / "instances" / fs::u8path(parsed.value().str()) / "instance-overrides.v1.json";
    if (!fs::exists(path)) return effective_profile(workspace, profile_id);
    auto text = stable_text(path);
    if (!text) return typed_failure<EffectiveProfile>(text.error().code, text.error().message, path);
    auto document = json::parse(text.value());
    if (!document || !document.value().is_object() ||
        object_string(document.value(), "schema") != "factorio.instance_overrides.v1" ||
        object_string(document.value(), "instance_id") != parsed.value().str() ||
        object_string(document.value(), "profile_id") != profile_id) {
        return typed_failure<EffectiveProfile>("profile_overrides_invalid", "Instance profile overrides are invalid", path);
    }
    const json::Value* values = document.value().find("values");
    if (values == nullptr || !values->is_object()) return typed_failure<EffectiveProfile>(
        "profile_overrides_invalid", "Instance profile override values are missing", path);
    Patch patch;
    patch.window_mode = object_string(*values, "window_mode");
    patch.graphics_quality = object_string(*values, "graphics_quality");
    patch.audio = object_string(*values, "audio");
    patch.selection_mode = object_string(*values, "selection_mode");
    patch.selection = object_string(*values, "selection");
    patch.launch_mode = object_string(*values, "launch_mode");
    patch.benchmark_ticks = object_string(*values, "benchmark_ticks");
    const json::Value* arguments = values->find("additional_arguments");
    if (arguments != nullptr) {
        if (!arguments->is_array() || arguments->size() > 32U) return typed_failure<EffectiveProfile>(
            "profile_overrides_invalid", "Instance profile override arguments are invalid", path);
        for (std::size_t index = 0; index < arguments->size(); ++index) {
            const json::Value* item = arguments->at(index);
            auto value = item == nullptr ? facman::core::Result<std::string>::failure(
                {"profile_overrides_invalid", "Override argument is missing", "additional_arguments"}) : item->string_value();
            if (!value) return typed_failure<EffectiveProfile>("profile_overrides_invalid", value.error().message, path);
            patch.additional_arguments.push_back(value.take_value());
        }
    }
    return effective_profile(workspace, profile_id, patch);
}

facman::core::Result<std::string> templates_list(const fs::path&)
{
    json::ArrayBuilder templates;
    templates.add_string("vanilla");
    json::ObjectBuilder output;
    output.add_string("schema", "factorio.instance_templates.v1");
    output.add_string("command", "templates.list");
    output.add_array("templates", templates);
    output.add_bool("mutation_executed", false);
    return facman::core::Result<std::string>::success(output.serialize());
}

facman::core::Result<std::string> templates_inspect(const fs::path&, const IdRequest& request)
{
    if (request.id != "vanilla") return failure("unknown_template", "Instance template is not shipped");
    return facman::core::Result<std::string>::success(template_json());
}

facman::core::Result<std::string> templates_validate(const fs::path& workspace, const IdRequest& request)
{
    auto inspected = templates_inspect(workspace, request);
    if (!inspected) return inspected;
    json::ObjectBuilder output;
    output.add_string("schema", "factorio.instance_template_validation.v1");
    output.add_string("command", "templates.validate");
    output.add_string("template_id", request.id);
    output.add_string("status", "pass");
    output.add_bool("arbitrary_execution", false);
    output.add_bool("mutation_executed", false);
    return facman::core::Result<std::string>::success(output.serialize());
}

facman::core::Result<std::string> profiles_list(const fs::path& workspace)
{
    json::ArrayBuilder profiles;
    profiles.add_string("gui");
    const fs::path root = workspace / "profiles";
    std::error_code error;
    if (fs::exists(root, error) && !error) {
        std::vector<std::string> ids;
        for (fs::directory_iterator item(root, error), end; item != end && !error; item.increment(error)) {
            if (!item->is_directory(error)) continue;
            const std::string id = item->path().filename().string();
            if (fs::is_regular_file(item->path() / "profile.v1.json", error) && !error) ids.push_back(id);
        }
        if (error) return failure("profile_list_failed", error.message(), root);
        std::sort(ids.begin(), ids.end());
        for (const std::string& id : ids) profiles.add_string(id);
    }
    if (error) return failure("profile_list_failed", error.message(), root);
    json::ObjectBuilder output;
    output.add_string("schema", "factorio.launch_profiles.v1");
    output.add_string("command", "profiles.list");
    output.add_array("profiles", profiles);
    output.add_bool("mutation_executed", false);
    return facman::core::Result<std::string>::success(output.serialize());
}

facman::core::Result<std::string> profiles_inspect(const fs::path& workspace, const IdRequest& request)
{
    auto profile = load_profile(workspace, request.id);
    if (!profile) return failure(profile.error().code, profile.error().message, fs::u8path(profile.error().path));
    facman::workspace::InstanceRepository instances {facman::workspace::WorkspaceLayout(workspace)};
    auto referenced = instances.list();
    if (!referenced) return failure("profile_reference_check_failed", referenced.error().message, workspace);
    for (const auto& instance : referenced.value()) if (instance.profile == request.id) return failure(
        "profile_in_use", "Profile is selected by instance " + instance.id.str(), instance.source_path);
    return facman::core::Result<std::string>::success(profile_report("profiles.inspect", profile.value(), false));
}

facman::core::Result<std::string> profiles_create(const fs::path& workspace, const CreateRequest& request)
{
    if (tx::incomplete_count(workspace) != 0U) return failure(
        "profile_transaction_recovery_required", "Workspace transaction recovery is required", workspace,
        facman::core::OutcomeKind::recovery_required, false);
    std::string detail;
    if (!facman::base::validate_identifier(request.profile_id, detail) || request.profile_id == "gui") {
        return failure("profile_id_invalid", request.profile_id == "gui" ? "The shipped gui profile is immutable" : detail);
    }
    if (request.template_id != "vanilla") return failure("unknown_template", "Instance template is not shipped");
    auto settings = apply_patch(Settings {}, request.values);
    if (!settings) return failure(settings.error().code, settings.error().message, fs::u8path(settings.error().path));
    Profile profile {request.profile_id, request.template_id, settings.take_value(), false, {}};
    auto written = write_profile_new(workspace, profile);
    if (!written) return failure(written.error().code, written.error().message, fs::u8path(written.error().path));
    return facman::core::Result<std::string>::success(profile_report("profiles.create", profile, true));
}

facman::core::Result<std::string> profiles_clone(const fs::path& workspace, const CloneRequest& request)
{
    auto source = load_profile(workspace, request.source_profile_id);
    if (!source) return failure(source.error().code, source.error().message, fs::u8path(source.error().path));
    Profile profile = source.value();
    profile.id = request.destination_profile_id;
    profile.shipped = false;
    profile.source.clear();
    std::string detail;
    if (!facman::base::validate_identifier(profile.id, detail) || profile.id == "gui") return failure("profile_id_invalid", detail);
    auto written = write_profile_new(workspace, profile);
    if (!written) return failure(written.error().code, written.error().message, fs::u8path(written.error().path));
    return facman::core::Result<std::string>::success(profile_report("profiles.clone", profile, true));
}

facman::core::Result<std::string> profiles_diff(const fs::path& workspace, const DiffRequest& request)
{
    auto left = load_profile(workspace, request.left_profile_id);
    auto right = load_profile(workspace, request.right_profile_id);
    if (!left || !right) {
        const auto& problem = !left ? left.error() : right.error();
        return failure(problem.code, problem.message, fs::u8path(problem.path));
    }
    const std::vector<std::pair<std::string, std::pair<std::string, std::string>>> fields = {
        {"window_mode", {left.value().settings.window_mode, right.value().settings.window_mode}},
        {"graphics_quality", {left.value().settings.graphics_quality, right.value().settings.graphics_quality}},
        {"audio", {left.value().settings.audio, right.value().settings.audio}},
        {"selection_mode", {left.value().settings.selection_mode, right.value().settings.selection_mode}},
        {"selection", {left.value().settings.selection, right.value().settings.selection}},
        {"launch_mode", {left.value().settings.launch_mode, right.value().settings.launch_mode}},
        {"benchmark_ticks", {std::to_string(left.value().settings.benchmark_ticks), std::to_string(right.value().settings.benchmark_ticks)}},
    };
    json::ArrayBuilder differences;
    for (const auto& field : fields) if (field.second.first != field.second.second) {
        json::ObjectBuilder item;
        item.add_string("field", field.first);
        item.add_string("left", field.second.first);
        item.add_string("right", field.second.second);
        differences.add_object(item);
    }
    if (left.value().settings.additional_arguments != right.value().settings.additional_arguments) {
        json::ObjectBuilder item;
        item.add_string("field", "additional_arguments");
        item.add_string("left", "different");
        item.add_string("right", "different");
        differences.add_object(item);
    }
    json::ObjectBuilder output;
    output.add_string("schema", "factorio.launch_profile_diff.v1");
    output.add_string("command", "profiles.diff");
    output.add_string("left_profile_id", request.left_profile_id);
    output.add_string("right_profile_id", request.right_profile_id);
    output.add_array("differences", differences);
    output.add_bool("mutation_executed", false);
    return facman::core::Result<std::string>::success(output.serialize());
}

facman::core::Result<std::string> profiles_plan(const fs::path& workspace, const EffectiveRequest& request)
{
    auto instance_id = facman::core::InstanceId::parse(request.instance_id);
    if (!instance_id) return failure(instance_id.error().code, instance_id.error().message);
    facman::workspace::InstanceRepository repository {facman::workspace::WorkspaceLayout(workspace)};
    auto instance = repository.load(instance_id.value());
    if (!instance) return failure("unknown_instance", "Instance is not registered", workspace);
    auto effective = effective_profile(workspace, request.profile_id, request.overrides);
    if (!effective) return failure(effective.error().code, effective.error().message, fs::u8path(effective.error().path));
    return facman::core::Result<std::string>::success(effective_report("profiles.plan", request, effective.value(), false));
}

facman::core::Result<std::string> profiles_apply(const fs::path& workspace, const EffectiveRequest& request)
{
    if (tx::incomplete_count(workspace) != 0U) return failure(
        "profile_transaction_recovery_required", "Workspace transaction recovery is required", workspace,
        facman::core::OutcomeKind::recovery_required, false);
    auto planned = profiles_plan(workspace, request);
    if (!planned) return planned;
    auto instance_id = facman::core::InstanceId::parse(request.instance_id);
    facman::workspace::InstanceRepository repository {facman::workspace::WorkspaceLayout(workspace)};
    auto instance = repository.load(instance_id.value());
    auto effective = effective_profile(workspace, request.profile_id, request.overrides);
    if (!instance || !effective) return failure("profile_apply_invalid", "Effective profile inputs changed during planning", workspace);
    tx::Record record;
    record.command_id = "profiles.apply";
    record.target = instance.value().source_path;
    record.sources = {instance.value().source_path};
    if (effective.value().profile_id != "gui") record.sources.push_back(
        workspace / "profiles" / effective.value().profile_id);
    record.commit_strategy = "plan_backup_stage_replace_instance_profile_and_overrides";
    auto started = tx::TransactionSession::begin(workspace, std::move(record));
    if (!started) return failure("profile_transaction_failed", started.error().message, workspace);
    tx::TransactionSession session = started.take_value();
    const fs::path backup_root = workspace / "backups" / "profiles" /
        fs::u8path(session.record().transaction_id + "-" + request.instance_id);
    const fs::path backup = backup_root / "instance.v1.json";
    const fs::path manifest_stage = instance.value().root / (".profile-apply-" + session.record().transaction_id + ".json");
    const fs::path overrides_stage = instance.value().root / (".profile-overrides-" + session.record().transaction_id + ".json");
    const fs::path overrides_target = instance.value().root / "instance-overrides.v1.json";
    session.record().staging_roots = {manifest_stage, overrides_stage};
    if (!session.validated("profile_plan_and_reserved_argument_policy_validated") ||
        !session.planned("backup_manifest_and_overrides_replace_planned")) return failure(
            "profile_transaction_failed", session.detail(), workspace);
    auto current = stable_text(instance.value().source_path);
    if (!current) { session.failed(current.error().message); return failure(current.error().code, current.error().message, instance.value().source_path); }
    std::error_code error;
    fs::create_directories(backup_root, error);
    if (error) { session.failed(error.message()); return failure("profile_backup_failed", error.message(), backup_root); }
    auto digest = facman::core::Sha256Digest::parse(facman::base::sha256_hex_bytes(
        reinterpret_cast<const unsigned char*>(current.value().data()), current.value().size()));
    std::string detail;
    if (!digest || !tx::CrossVolumeCopyVerifyCommit::commit(
            instance.value().source_path, backup, digest.value(), current.value().size(), detail) ||
        !facman::base::write_text_new_atomic(manifest_stage, instance_manifest(instance.value(), effective.value().profile_id), detail) ||
        !facman::base::write_text_new_atomic(overrides_stage, overrides_json(request), detail) ||
        !session.staging("profile_plan_materialized") || !session.staged("backup_and_replacements_staged") ||
        !session.verified("effective_profile_and_reserved_arguments_verified") ||
        !session.committing("profile_apply_replace_started")) {
        session.failed(detail.empty() ? session.detail() : detail);
        return failure("profile_apply_failed", detail.empty() ? session.detail() : detail, instance.value().root);
    }
    auto status = facman::platform::replace_existing_durable(manifest_stage, instance.value().source_path);
    if (status.ok()) {
        if (fs::exists(overrides_target)) status = facman::platform::replace_existing_durable(overrides_stage, overrides_target);
        else status = facman::platform::commit_no_replace(overrides_stage, overrides_target);
    }
    if (!status.ok() || !session.committed("instance_profile_and_overrides_committed") || !session.complete()) {
        session.failed(status.ok() ? session.detail() : status.detail);
        return failure("profile_transaction_recovery_required", status.ok() ? session.detail() : status.detail,
            instance.value().root, facman::core::OutcomeKind::recovery_required, false);
    }
    return facman::core::Result<std::string>::success(effective_report(
        "profiles.apply", request, effective.value(), true, session.record().transaction_id));
}

facman::core::Result<std::string> profiles_archive(const fs::path& workspace, const IdRequest& request)
{
    if (request.id == "gui") return failure("profile_shipped_immutable", "Shipped profiles cannot be archived");
    auto profile = load_profile(workspace, request.id);
    if (!profile) return failure(profile.error().code, profile.error().message, fs::u8path(profile.error().path));
    if (tx::incomplete_count(workspace) != 0U) return failure(
        "profile_transaction_recovery_required", "Workspace transaction recovery is required", workspace,
        facman::core::OutcomeKind::recovery_required, false);
    const fs::path source = profile.value().source.parent_path();
    facman::platform::RandomIdGenerator random;
    const fs::path target = workspace / "trash" / "profiles" / fs::u8path(random.next("profile") + "-" + request.id);
    tx::Record record;
    record.command_id = "profiles.archive";
    record.target = target;
    record.sources = {source};
    record.commit_strategy = "owned_trash_move_no_delete";
    auto started = tx::TransactionSession::begin(workspace, std::move(record));
    if (!started) return failure("profile_transaction_failed", started.error().message, workspace);
    tx::TransactionSession session = started.take_value();
    if (!session.validated("profile_identity_and_references_validated") || !session.planned("owned_trash_move_planned") ||
        !session.staging("trash_parent_selected")) return failure("profile_transaction_failed", session.detail(), workspace);
    std::error_code error;
    fs::create_directories(target.parent_path(), error);
    if (error || !session.staged("trash_target_ready") || !session.verified("profile_document_verified") ||
        !session.committing("profile_archive_move_started")) {
        session.failed(error ? error.message() : session.detail());
        return failure("profile_archive_failed", error ? error.message() : session.detail(), target);
    }
    auto status = facman::platform::commit_no_replace(source, target);
    if (!status.ok() || !session.committed("profile_moved_to_owned_trash") || !session.complete()) {
        session.failed(status.ok() ? session.detail() : status.detail);
        return failure("profile_transaction_recovery_required", status.ok() ? session.detail() : status.detail, target,
            facman::core::OutcomeKind::recovery_required, false);
    }
    json::ObjectBuilder output;
    output.add_string("schema", "factorio.launch_profile_archive.v1");
    output.add_string("command", "profiles.archive");
    output.add_string("profile_id", request.id);
    output.add_string("path", facman::platform::path_to_utf8(target));
    output.add_bool("permanent_delete", false);
    output.add_bool("mutation_executed", true);
    return facman::core::Result<std::string>::success(output.serialize());
}

} // namespace facman::factorio::profiles
